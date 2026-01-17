import json
import logging
import asyncio
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException
from src.models.research_brief import ResearchBrief
from src.models.research_insights import ProcessedSearchResults
from src.services.research_service import research_service
from src.services.analysis_service import analysis_service
from src.services.synthesis_service import synthesis_service
from src.utils.config import settings
from src.services.serpapi_service import run_serp_search_async

logger = logging.getLogger(__name__)

class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief

research_router = APIRouter()

@research_router.post("/start-research")
async def start_research(request: StartResearchRequest):
    """
    Endpoint to start research with the completed brief.
    This will be called by the frontend after user confirms the brief.
    """
    try:
        
        # Validate that the brief has required fields
        if not request.research_brief.is_complete():
            raise HTTPException(
                status_code=400,
                detail=f"Research brief is incomplete. Missing required fields: {request.research_brief.get_missing_fields()}"
            )
        
        # Generate search params from research brief
        search_params = await research_service.create_research_query(request.research_brief, threadId = request.threadId)
        
        # Define query types and their corresponding queries
        query_mapping = {
            "product": search_params.product_search_query,
            "competitor": search_params.competitor_search_query,
            "audience": search_params.audience_insight_query,
            "campaign": search_params.campaign_strategy_query,
            "platform": search_params.platform_specific_query,
        }
       # TODO: integrate the task queue here, set status to 'researching' in db and store the results when done
        # Filter out empty queries and run all searches concurrently
        search_tasks = [
            run_serp_search_async(query, query_type)
            for query_type, query in query_mapping.items()
            if query  # Only include non-empty queries
        ]
        
        # Execute all searches in parallel
        all_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        #TODO: process results like embeddings, analysis, synthesis etc.
        # Process results and handle any exceptions
        successful_results = {}
        for item in all_results:
            if isinstance(item, Exception):
                logger.error(f"Search failed: {item}")
                continue
            if isinstance(item, dict):
                successful_results[item["query_type"]] = {
                    "query": item["query"],
                    "results": item["results"]
                }
        
        # Save all results to file
        # TODO: store results in db if needed in later stage
        with open("search_results.json", "w") as f:
            json.dump(successful_results, f, indent=2)
        logger.info(f"Search results saved to search_results.json ({len(successful_results)} queries)")
        
        # Process and analyze the search results
        processed_results = analysis_service.process_search_results(successful_results)
        
        # Save processed results
        with open("processed_results.json", "w") as f:
            json.dump(processed_results.model_dump(), f, indent=2)
        logger.info(f"Processed results saved to processed_results.json")
        
        # Generate combined context for reference
        combined_context = analysis_service.get_combined_context(processed_results)
        with open("research_context.txt", "w") as f:
            f.write(combined_context)
        logger.info("Research context saved to research_context.txt")
        
        # Synthesize insights using LLM
        logger.info("Starting LLM synthesis...")
        research_report = await synthesis_service.synthesize_all(
            processed_results, 
            research_brief=request.research_brief.model_dump()
        )
        
        # Save synthesized report
        with open("research_report.json", "w") as f:
            json.dump(research_report.model_dump(), f, indent=2)
        logger.info("Research report saved to research_report.json")
        
        # Build response with processing summary
        category_summaries = {}
        for insights in processed_results.get_all_insights():
            category_summaries[insights.category] = analysis_service.get_category_summary(insights)
        
        return {
            "status": "success",
            "message": "Research completed successfully",
            "brief": request.research_brief.model_dump(),
            "processing_summary": processed_results.processing_summary,
            "category_summaries": category_summaries,
            "total_sources": processed_results.total_sources,
            "report": research_report.model_dump(),
        }
    except Exception as e:
        logger.error(f"Error starting research: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@research_router.post("/process-existing")
async def process_existing_results():
    """
    Process existing search_results.json file without re-running SerpAPI searches.
    Useful for development and testing the analysis pipeline.
    """
    try:
        # Load existing search results
        try:
            with open("search_results.json", "r") as f:
                raw_results = json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="search_results.json not found. Run /start-research first."
            )
        
        # Process the results
        processed_results = analysis_service.process_search_results(raw_results)
        
        # Save processed results
        with open("processed_results.json", "w") as f:
            json.dump(processed_results.model_dump(), f, indent=2)
        logger.info("Processed results saved to processed_results.json")
        
        # Generate combined context
        combined_context = analysis_service.get_combined_context(processed_results)
        with open("research_context.txt", "w") as f:
            f.write(combined_context)
        logger.info("Research context saved to research_context.txt")
        
        # Synthesize insights using LLM
        logger.info("Starting LLM synthesis...")
        research_report = await synthesis_service.synthesize_all(processed_results)
        
        # Save synthesized report
        with open("research_report.json", "w") as f:
            json.dump(research_report.model_dump(), f, indent=2)
        logger.info("Research report saved to research_report.json")
        
        # Build response
        category_summaries = {}
        for insights in processed_results.get_all_insights():
            category_summaries[insights.category] = analysis_service.get_category_summary(insights)
        
        return {
            "status": "success",
            "message": "Existing results processed and synthesized successfully",
            "processing_summary": processed_results.processing_summary,
            "category_summaries": category_summaries,
            "total_sources": processed_results.total_sources,
            "report": research_report.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing existing results: {e}")
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


@research_router.get("/research-context")
async def get_research_context():
    """
    Get the combined research context (text format for LLM synthesis).
    """
    try:
        try:
            with open("research_context.txt", "r") as f:
                context = f.read()
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="research_context.txt not found. Run /start-research or /process-existing first."
            )
        
        return {
            "status": "success",
            "context": context,
            "length": len(context)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting research context: {e}")
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


@research_router.post("/synthesize")
async def synthesize_only():
    """
    Run LLM synthesis on existing processed results without re-processing.
    Useful for testing synthesis with different prompts.
    """
    try:
        # Load existing processed results
        try:
            with open("processed_results.json", "r") as f:
                processed_data = json.load(f)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="processed_results.json not found. Run /process-existing first."
            )
        
        # Convert to ProcessedSearchResults model
        processed_results = ProcessedSearchResults(**processed_data)
        
        # Synthesize insights using LLM
        logger.info("Starting LLM synthesis...")
        research_report = await synthesis_service.synthesize_all(processed_results)
        
        # Save synthesized report
        with open("research_report.json", "w") as f:
            json.dump(research_report.model_dump(), f, indent=2)
        logger.info("Research report saved to research_report.json")
        
        return {
            "status": "success",
            "message": "Synthesis completed successfully",
            "report": research_report.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during synthesis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
