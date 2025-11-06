import json
import logging
from fastapi import APIRouter, HTTPException
from src.models.research_brief import ResearchBrief
from pydantic import BaseModel
from src.services.research_service import research_service

logger = logging.getLogger(__name__)

class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief

router = APIRouter()

@router.post("/start-research")
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
        
        # TODO: Implement actual research logic here
        search_params = await research_service.create_research_query(request.research_brief)
        #save search params to local json file
        with open("search_params.json", "w") as f:
            json.dump(search_params.model_dump(), f)
        logger.info(f"Search params saved to search_params.json")
    
        return {
            "status": "success",
            "message": "Research started successfully",
            "brief": request.research_brief.model_dump()
        }
    except Exception as e:
        logger.error(f"Error starting research: {e}")
        raise HTTPException(status_code=500, detail=str(e))
