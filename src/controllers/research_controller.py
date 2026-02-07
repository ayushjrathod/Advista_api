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
from src.utils.config import settings
from src.services.serpapi_service import run_serp_search_async

logger = logging.getLogger(__name__)
# Disable by default for Lambda (ephemeral filesystem); set ENABLE_DEBUG_FILES=true locally
save_to_json = os.environ.get("ENABLE_DEBUG_FILES", "false").lower() == "true"

class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief
    threadId: str
    userId: Optional[str] = None

research_router = APIRouter()

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
        
        # Run SerpAPI searches concurrently (no Celery/Redis; Lambda-friendly)
        await research_session_service.update_status(session_id, 'researching')
        logger.info("Running SerpAPI searches...")
        
        tasks = [
            run_serp_search_async(query, query_type)
            for query_type, query in query_mapping.items()
            if query
        ]
        if not tasks:
            await research_session_service.update_status(
                session_id, 'failed', error_message="No search queries generated"
            )
            raise HTTPException(status_code=400, detail="No search queries generated from brief.")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_results = {}
        for i, result in enumerate(results):
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
                session_id,
                'failed',
                error_message="All SerpAPI searches failed or timed out"
            )
            raise HTTPException(
                status_code=500,
                detail="All SerpAPI searches failed or timed out."
            )
        
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
async def get_research_report():
    """
    Get the synthesized research report.
    """
    try:
        try:
            with open("research_report.json", "r") as f:
                report = json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="research_report.json not found. Run /start-research or /process-existing first."
            )
        
        return {
            "status": "success",
            "report": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
