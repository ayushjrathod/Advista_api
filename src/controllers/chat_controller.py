from fastapi import APIRouter, Depends, HTTPException
from src.services.chatbot_service import chatbot_service
from src.models.research_brief import ResearchBrief
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from src.controllers.auth_controller import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatStreamRequest(BaseModel):
    thread_id: str
    message: str


class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    async def event_generator():
        async for chunk in chatbot_service.stream(request.thread_id, request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/research-brief/{thread_id}")
async def get_research_brief(thread_id: str):
    """Get the current research brief for a thread"""
    brief = chatbot_service.get_research_brief(thread_id)
    return {
        "brief": brief.model_dump(),
        "completion_percentage": brief.get_completion_percentage(),
        "missing_fields": brief.get_missing_fields(),
        "is_complete": brief.is_complete()
    }
