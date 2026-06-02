import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.models.research_brief import ResearchBrief
from src.models.research_insights import ProcessedSearchResults
from src.services.research_service import research_service
from src.services.analysis_service import analysis_service
from src.services.synthesis_service import synthesis_service
from src.services.research_session_service import research_session_service
from src.services.database_service import db
from src.services.serpapi_service import run_serp_search_async
from src.services.youtube_service import run_youtube_research_async
from src.utils.config import settings
from src.controllers.auth_controller import UNAUTHENTICATED_MESSAGE, get_optional_user

logger = logging.getLogger(__name__)


class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief
    threadId: str

research_router = APIRouter()

# Category labels for resources display
RESOURCE_SOURCE_FOR_CATEGORY = {
    "customer_sentiment": "reddit_forums",
    "competitor_landscape": "reddit_forums",
    "company_product": "google",
    "strategic_gap": "google",
    "battlecard": "google",
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
async def start_research(request: StartResearchRequest, current_user = Depends(get_optional_user)):
    session = None
    try:
        if not request.research_brief.is_complete():
            raise HTTPException(
                status_code=400,
                detail=f"Research brief is incomplete. Missing required fields: {request.research_brief.get_missing_fields()}"
            )

        logger.info(f"Starting research for thread {request.threadId}")
        chat_session = await db.prisma.chatsession.find_unique(where={"threadId": request.threadId})
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        if chat_session.userId and current_user and chat_session.userId != current_user.id:
            raise HTTPException(status_code=403, detail="You do not have access to this thread")

        user_id = current_user.id if current_user else chat_session.userId
        session = await research_session_service.create_session(
            thread_id=request.threadId,
            user_id=user_id,
            research_brief=request.research_brief.model_dump(),
            task_ids={}
        )
        session_id = session['id']

        search_params = await research_service.create_research_query(
            request.research_brief,
            threadId=request.threadId
        )

        query_mapping = {
            "company_product": search_params.company_product_query,
            "competitor_landscape": search_params.competitor_landscape_query,
            "customer_sentiment": search_params.customer_sentiment_query,
            "strategic_gap": search_params.strategic_gap_query,
            "battlecard": search_params.battlecard_query,
        }

        ENGINE_FOR_QUERY_TYPE = {
            "customer_sentiment": "google_forums",
            "competitor_landscape": "google_forums",
            "company_product": "google",
            "strategic_gap": "google",
            "battlecard": "google",
        }

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
            if not tasks:
                await research_session_service.update_status(
                    session_id, 'failed', error_message="No search queries generated"
                )
                raise HTTPException(status_code=400, detail="No search queries generated from brief.")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"SerpAPI search failed: {result}")
                    continue
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"SerpAPI search error for {result.get('query_type', '?')}: {result['error']}")
                    continue
                query_type = result.get("query_type")
                successful_results[query_type] = {
                    "query": result["query"],
                    "results": result["results"],
                }
                logger.info(f"SerpAPI search completed for {query_type}")
        
        if not successful_results:
            await research_session_service.update_status(
                session_id, 'failed', error_message="All SerpAPI searches failed or timed out"
            )
            raise HTTPException(status_code=500, detail="All SerpAPI searches failed or timed out.")

        youtube_query = request.research_brief.company_name or search_params.company_product_query or "competitive intelligence"
        try:
            logger.info(f"Running YouTube research for: {youtube_query}")
            youtube_results = await run_youtube_research_async(youtube_query)
            if youtube_results and "error" not in youtube_results:
                successful_results["youtube"] = youtube_results
                logger.info(f"YouTube: {len(youtube_results.get('videos', []))} videos, {len(youtube_results.get('shorts', []))} shorts")
            else:
                logger.warning("YouTube research returned no results or error")
        except Exception as e:
            logger.warning(f"YouTube research failed (continuing without): {e}")

        await research_session_service.save_search_results(session_id, successful_results)
        await research_session_service.update_status(session_id, 'processing')

        processed_results = analysis_service.process_search_results(successful_results)
        await research_session_service.save_processed_results(session_id, processed_results.model_dump())

        await research_session_service.update_status(session_id, 'synthesizing')

        logger.info("Starting LLM synthesis...")
        research_report = await synthesis_service.synthesize_all(
            processed_results,
            research_brief=request.research_brief.model_dump()
        )

        await research_session_service.save_report(session_id, research_report.model_dump())

        resources_used = _build_resources_used(processed_results, RESOURCE_SOURCE_FOR_CATEGORY)
        await research_session_service.save_resources_used(session_id, resources_used)
        await research_session_service.update_status(session_id, 'completed')

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
        if session:
            try:
                await research_session_service.update_status(
                    session['id'], 'failed', error_message=str(e)
                )
            except Exception as update_error:
                logger.error(f"Failed to update session status: {update_error}")
        raise HTTPException(status_code=500, detail=str(e))


@research_router.get("/sessions")
async def get_research_sessions(current_user = Depends(get_optional_user)):
    """Get all research sessions for the current user, newest first."""
    if not current_user:
        return {
            "status": "success",
            "authenticated": False,
            "message": UNAUTHENTICATED_MESSAGE,
            "sessions": [],
        }

    if not db.is_connected():
        await db.connect()
    sessions = await db.prisma.researchsession.find_many(
        where={"userId": current_user.id},
        order={"createdAt": "desc"},
    )
    return {
        "status": "success",
        "authenticated": True,
        "sessions": [
            {
                "id": s.id,
                "status": s.status,
                "createdAt": s.createdAt.isoformat() if s.createdAt else None,
                "completedAt": s.completedAt.isoformat() if s.completedAt else None,
                "researchBrief": s.researchBrief,
            }
            for s in sessions
        ],
    }


@research_router.get("/report")
async def get_research_report(session_id: Optional[str] = None, current_user = Depends(get_optional_user)):
    """Get the synthesized research report by session_id, or the latest completed session."""
    try:
        if session_id:
            session = await research_session_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Research session not found.")
            if current_user and session.get("userId") and session.get("userId") != current_user.id:
                raise HTTPException(status_code=403, detail="You do not have access to this report.")
            report_data = session.get("report")
            resources_used = session.get("resourcesUsed")
            if not report_data:
                raise HTTPException(status_code=404, detail="Report not found for this session.")
            return {
                "status": "success",
                "authenticated": bool(current_user),
                "message": None if current_user else UNAUTHENTICATED_MESSAGE,
                "report": report_data,
                "resources_used": resources_used,
            }

        if not current_user:
            return {
                "status": "success",
                "authenticated": False,
                "message": UNAUTHENTICATED_MESSAGE,
                "report": None,
                "resources_used": None,
            }

        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.find_first(
            where={"status": "completed", "userId": current_user.id},
            order={"completedAt": "desc"}
        )
        if session:
            session_dict = session.model_dump()
            return {
                "status": "success",
                "authenticated": True,
                "report": session_dict.get("report"),
                "resources_used": session_dict.get("resourcesUsed"),
            }

        raise HTTPException(status_code=404, detail="No report found. Run /start-research first.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
