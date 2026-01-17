from fastapi import APIRouter, Depends, HTTPException
from src.services.chatbot_service import chatbot_service
from src.models.research_brief import ResearchBrief
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from src.controllers.auth_controller import get_current_user

logger = logging.getLogger(__name__)

chat_router = APIRouter()

class ChatStreamRequest(BaseModel):
    thread_id: str
    message: str


class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief


@chat_router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    async def event_generator():
        async for chunk in chatbot_service.stream(request.thread_id, request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@chat_router.get("/research-brief/{thread_id}")
async def get_research_brief(thread_id: str):
    """Get the current research brief for a thread"""
    brief = chatbot_service.get_research_brief_for_thread(thread_id)
    return {
        "brief": brief.model_dump(),
        "completion_percentage": brief.get_completion_percentage(),
        "missing_fields": brief.get_missing_fields(),
        "is_complete": brief.is_complete()
    }

@chat_router.post("/initilize-thread")
async def initilize_thread():
    thread_id = await chatbot_service.create_thread()
    return {"thread_id": thread_id}
