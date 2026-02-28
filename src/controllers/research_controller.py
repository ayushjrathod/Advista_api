import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.models.research_brief import ResearchBrief
from src.models.research_insights import ProcessedSearchResults
from src.services.research_service import research_service
from src.services.analysis_service import analysis_service
from src.services.synthesis_service import synthesis_service
from src.services.research_session_service import research_session_service
from src.services.database_service import db
from src.utils.config import settings
from src.services.serpapi_service import run_serp_search_async
from src.services.youtube_service import run_youtube_research_async

logger = logging.getLogger(__name__)
# Disable by default for Lambda (ephemeral filesystem); set ENABLE_DEBUG_FILES=true locally
save_to_json = os.environ.get("ENABLE_DEBUG_FILES", "false").lower() == "true"

class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief
    threadId: str
    userId: Optional[str] = None

research_router = APIRouter()

# Category labels for resources display
RESOURCE_SOURCE_FOR_CATEGORY = {
    "audience": "reddit_forums",
    "competitor": "reddit_forums",
    "product": "google",
    "campaign": "google",
    "platform": "google",
}


def _build_resources_used(processed_results, source_for_category):
    """Build resources_used payload for frontend Resources tab."""
    categories_resources = []
    for insights in processed_results.get_all_insights():
        source_label = source_for_category.get(insights.category, "google")
        resources = [
            {"title": r.title, "link": r.link, "source": r.source, "snippet": (r.snippet or "")[:200]}
            for r in (insights.top_results or [])
        ]
        categories_resources.append({
            "category": insights.category,
            "query": insights.query,
            "source": source_label,
            "resources": resources,
        })
    youtube_data = None
    if processed_results.youtube_insights:
        youtube_data = {
            "query": processed_results.youtube_insights.query,
            "videos": [
                {
                    "title": v.title,
                    "link": v.link,
                    "channel": v.channel,
                    "video_id": v.video_id,
                    "published_date": v.published_date,
                    "transcript": v.transcript,
                }
                for v in processed_results.youtube_insights.videos
            ],
            "shorts": [
                {
                    "title": s.title,
                    "link": s.link,
                    "video_id": s.video_id,
                    "views_original": s.views_original,
                    "transcript": s.transcript,
                }
                for s in processed_results.youtube_insights.shorts
            ],
        }
    return {"categories": categories_resources, "youtube": youtube_data}


@research_router.post("/start-research")
async def start_research(request: StartResearchRequest):
    """
    Endpoint to start research with the completed brief.
    This will be called by the frontend after user confirms the brief.
    """
    session = None
    try:
        # Validate that the brief has required fields
        if not request.research_brief.is_complete():
            raise HTTPException(
                status_code=400,
                detail=f"Research brief is incomplete. Missing required fields: {request.research_brief.get_missing_fields()}"
            )
        print(request.research_brief)
        
        # Create research session in database
        logger.info(f"Starting research for thread {request.threadId}")
        user_id = request.userId if request.userId else None
        session = await research_session_service.create_session(
            thread_id=request.threadId,
            user_id=user_id,
            research_brief=request.research_brief.model_dump(),
            task_ids={}
        )
        session_id = session['id']   
        
        # Generate search params from research brief
        search_params = await research_service.create_research_query(
            request.research_brief, 
            threadId=request.threadId
        )
        
        # Define query types and their corresponding queries
        query_mapping = {
            "product": search_params.product_search_query,
            "competitor": search_params.competitor_search_query,
            "audience": search_params.audience_insight_query,
            "campaign": search_params.campaign_strategy_query,
            "platform": search_params.platform_specific_query,
        }

        # Per-query engine mapping: audience & competitor use forums for sentiment; others use general search
        ENGINE_FOR_QUERY_TYPE = {
            "audience": "google_forums",
            "competitor": "google_forums",
            "product": "google",
            "campaign": "google",
            "platform": "google",
        }
        # TODO: remove after debugging
        forum_types = [qt for qt, eng in ENGINE_FOR_QUERY_TYPE.items() if eng == "google_forums"]
        qm_preview = {k: (v[:50] + "..." if v and len(str(v)) > 50 else v) for k, v in query_mapping.items()}
        logger.info(f"[REDDIT/FORUMS] Engine mapping | forum_types={forum_types} | query_mapping={qm_preview}")

        successful_results = {}
        
        # Use Celery if enabled, otherwise use async approach (Lambda-friendly)
        if settings.ENABLE_CELERY:
            # Celery task submission approach
            from worker.celery_app import celery_app
            
            await research_session_service.update_status(session_id, 'researching')
            logger.info("Submitting SerpAPI searches to Celery...")
            
            # Submit tasks to Celery (worker must accept query, query_type, engine)
            query_task_ids = {}
            for query_type, query in query_mapping.items():
                if not query:
                    logger.info(f"Skipping empty query for type: {query_type}")
                    continue
                engine = ENGINE_FOR_QUERY_TYPE.get(query_type, "google")
                task_data = celery_app.send_task("serpapi_search", args=[query, query_type, engine])
                query_task_ids[query_type] = task_data.id
                logger.info(f"Submitted SerpAPI search task for {query_type} (engine={engine}) with task ID: {task_data.id}")
            
            # Save task_id to db
            await research_session_service.save_task_ids(
                session_id,
                query_task_ids
            )
            
            # Poll for task completion and gather results
            logger.info("Polling for SerpAPI search task completion...")
            max_wait_time = 60
            poll_interval = 2
            elapsed_time = 0
            
            pending_tasks = set(query_task_ids.keys())
            
            while pending_tasks and elapsed_time < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
                
                for query_type in list(pending_tasks):
                    task_id = query_task_ids[query_type]
                    result = celery_app.AsyncResult(task_id)
                    
                    if result.ready():
                        if result.successful():
                            task_result = result.result
                            successful_results[query_type] = task_result
                            logger.info(f"Celery task completed for {query_type}")
                        else:
                            logger.error(f"Celery task failed for {query_type}: {result.result}")
                        pending_tasks.discard(query_type)
            
            if pending_tasks:
                logger.warning(f"Some tasks did not complete within timeout: {pending_tasks}")
        else:
            # Async approach (Lambda-friendly)
            await research_session_service.update_status(session_id, 'researching')
            logger.info("Running SerpAPI searches concurrently (async)...")
            
            tasks = [
                run_serp_search_async(query, query_type, ENGINE_FOR_QUERY_TYPE.get(query_type, "google"))
                for query_type, query in query_mapping.items()
                if query
            ]
            # TODO: remove after debugging
            logger.info(f"[REDDIT/FORUMS] Submitting {len(tasks)} SerpAPI tasks | forum_tasks={[qt for qt,q in query_mapping.items() if q and ENGINE_FOR_QUERY_TYPE.get(qt)=='google_forums']}")
            if not tasks:
                await research_session_service.update_status(
                    session_id, 'failed', error_message="No search queries generated"
                )
                raise HTTPException(status_code=400, detail="No search queries generated from brief.")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"SerpAPI search failed: {result}")
                    continue
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"SerpAPI search error for {result.get('query_type', '?')}: {result['error']}")
                    continue
                query_type = result.get("query_type")
                engine_used = ENGINE_FOR_QUERY_TYPE.get(query_type, "google")
                successful_results[query_type] = {
                    "query": result["query"],
                    "results": result["results"],
                }
                logger.info(f"SerpAPI search completed for {query_type}")
                # TODO: remove after debugging
                if engine_used == "google_forums":
                    organic = result.get("results", {}).get("organic_results", [])
                    logger.info(f"[REDDIT/FORUMS] Forum result saved | category={query_type} | organic_count={len(organic)} | sources={list(set(r.get('source','') for r in organic[:5]))}")
        
        if not successful_results:
            await research_session_service.update_status(
                session_id,
                'failed',
                error_message="All SerpAPI searches failed or timed out"
            )
            raise HTTPException(
                status_code=500,
                detail="All SerpAPI searches failed or timed out."
            )

        # Run YouTube research: top 3 videos + top 5 shorts with transcripts
        youtube_query = request.research_brief.product_name or search_params.product_search_query or "advertising"
        # TODO: remove after debugging
        logger.info(f"[YT] Starting YouTube research | session_id={session_id} | query={youtube_query} | product_name={request.research_brief.product_name}")
        try:
            logger.info(f"Running YouTube research for: {youtube_query}")
            youtube_results = await run_youtube_research_async(youtube_query)
            if youtube_results and "error" not in youtube_results:
                successful_results["youtube"] = youtube_results
                vcount = len(youtube_results.get("videos", []))
                scount = len(youtube_results.get("shorts", []))
                transcripts_with_content = sum(1 for v in youtube_results.get("videos", []) if v.get("transcript")) + sum(1 for s in youtube_results.get("shorts", []) if s.get("transcript"))
                logger.info(f"YouTube: {vcount} videos, {scount} shorts")
                # TODO: remove after debugging
                logger.info(f"[YT] YouTube research done | videos={vcount} | shorts={scount} | transcripts_with_content={transcripts_with_content}")
            else:
                logger.warning("YouTube research returned no results or error")
                # TODO: remove after debugging
                logger.warning(f"[YT] YouTube skipped | has_error={'error' in (youtube_results or {})} | empty={not youtube_results}")
        except Exception as e:
            logger.warning(f"YouTube research failed (continuing without): {e}")
            # TODO: remove after debugging
            logger.warning(f"[YT] YouTube exception | error={e}", exc_info=True)
        
        # Save search results to database
        await research_session_service.save_search_results(session_id, successful_results)
        
        # Save to file for debugging (optional)
        if save_to_json:
            with open("search_results.json", "w") as f:
                json.dump(successful_results, f, indent=2)
            logger.info(f"Search results saved ({len(successful_results)} queries)")
        
        # Update status to processing
        await research_session_service.update_status(session_id, 'processing')
        
        # Process and analyze the search results
        # TODO: Implement analysis service
        processed_results = analysis_service.process_search_results(successful_results)
        
        # Save processed results to database
        await research_session_service.save_processed_results(
            session_id,
            processed_results.model_dump()
        )
        
        # Save to file for debugging (optional)
        if save_to_json:
            with open("processed_results.json", "w") as f:
                json.dump(processed_results.model_dump(), f, indent=2)
            logger.info(f"Processed results saved")
        
        # Generate combined context for reference
        # TODO: Implment analysis service
        combined_context = analysis_service.get_combined_context(processed_results)
        if save_to_json:
            with open("research_context.txt", "w") as f:
                f.write(combined_context)
            logger.info("Research context saved")
        
        # Update status to synthesizing
        await research_session_service.update_status(session_id, 'synthesizing')
        
        # Synthesize insights using LLM
        logger.info("Starting LLM synthesis...")
        research_report = await synthesis_service.synthesize_all(
            processed_results, 
            research_brief=request.research_brief.model_dump()
        )
        
        # Save final report to database
        await research_session_service.save_report(session_id, research_report.model_dump())

        # Build resources_used for frontend Resources tab and DB
        resources_used = _build_resources_used(processed_results, RESOURCE_SOURCE_FOR_CATEGORY)
        await research_session_service.save_resources_used(session_id, resources_used)
        
        # Update status to completed
        await research_session_service.update_status(session_id, 'completed')
        
        # Save to file for debugging (optional)
        if save_to_json:
            with open("research_report.json", "w") as f:
                json.dump(research_report.model_dump(), f, indent=2)
            logger.info("Research report saved")
        
        # Build response with processing summary
        category_summaries = {}
        for insights in processed_results.get_all_insights():
            category_summaries[insights.category] = analysis_service.get_category_summary(insights)

        return {
            "status": "success",
            "message": "Research completed successfully",
            "session_id": session_id,
            "brief": request.research_brief.model_dump(),
            "processing_summary": processed_results.processing_summary,
            "category_summaries": category_summaries,
            "total_sources": processed_results.total_sources,
            "report": research_report.model_dump(),
            "resources_used": resources_used,
        }
        
    except Exception as e:
        logger.error(f"Error starting research: {e}")
        
        # Update session status to failed if session was created
        if session:
            try:
                await research_session_service.update_status(
                    session['id'],
                    'failed',
                    error_message=str(e)
                )
            except Exception as update_error:
                logger.error(f"Failed to update session status: {update_error}")
        
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/processed-results")
async def get_processed_results():
    """
    Get the processed research results.
    """
    try:
        try:
            with open("processed_results.json", "r") as f:
                processed = json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="processed_results.json not found. Run /start-research or /process-existing first."
            )
        
        return {
            "status": "success",
            "data": processed
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processed results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/report")
async def get_research_report(session_id: Optional[str] = None):
    """
    Get the synthesized research report. When session_id is provided, fetches from DB.
    When omitted, tries file fallback (local dev) or latest completed session from DB.
    """
    try:
        if session_id:
            session = await research_session_service.get_session(session_id)
            if not session:
                raise HTTPException(
                    status_code=404,
                    detail="Research session not found."
                )
            report_data = session.get("report")
            resources_used = session.get("resourcesUsed")
            if not report_data:
                raise HTTPException(
                    status_code=404,
                    detail="Report not found for this session."
                )
            return {
                "status": "success",
                "report": report_data,
                "resources_used": resources_used
            }

        # Fallback: try local file (dev) or latest completed session from DB
        try:
            with open("research_report.json", "r") as f:
                report = json.load(f)
            return {
                "status": "success",
                "report": report,
                "resources_used": None
            }
        except FileNotFoundError:
            pass

        # No file: try to get latest completed session from DB
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.find_first(
            where={"status": "completed"},
            order={"completedAt": "desc"}
        )
        if session:
            session_dict = session.model_dump()
            return {
                "status": "success",
                "report": session_dict.get("report"),
                "resources_used": session_dict.get("resourcesUsed")
            }

        raise HTTPException(
            status_code=404,
            detail="No report found. Run /start-research first."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
