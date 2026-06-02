from fastapi import APIRouter, Depends, HTTPException
from src.services.chatbot_service import chatbot_service
from src.services.database_service import db
from src.models.research_brief import ResearchBrief
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from src.controllers.auth_controller import get_optional_user

logger = logging.getLogger(__name__)

chat_router = APIRouter()

class ChatStreamRequest(BaseModel):
    thread_id: str
    message: str


class StartResearchRequest(BaseModel):
    research_brief: ResearchBrief


async def _require_thread_owner(thread_id: str, current_user):
    session = await db.prisma.chatsession.find_unique(where={"threadId": thread_id})
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")
    if session.userId and current_user and session.userId != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this thread")
    return session


@chat_router.post("/stream")
async def chat_stream(request: ChatStreamRequest, current_user = Depends(get_optional_user)):
    await _require_thread_owner(request.thread_id, current_user)

    async def event_generator():
        async for chunk in chatbot_service.stream(request.thread_id, request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@chat_router.get("/research-brief/{thread_id}")
async def get_research_brief(thread_id: str, current_user = Depends(get_optional_user)):
    """Get the current research brief for a thread"""
    await _require_thread_owner(thread_id, current_user)
    brief = chatbot_service.get_research_brief_for_thread(thread_id)
    return {
        "brief": brief.model_dump(),
        "completion_percentage": brief.get_completion_percentage(),
        "missing_fields": brief.get_missing_fields(),
        "is_complete": brief.is_complete()
    }

@chat_router.post("/initialize-thread")
@chat_router.get("/initialize-thread")
async def initialize_thread(current_user = Depends(get_optional_user)):
    user_id = current_user.id if current_user else None
    thread_id = await chatbot_service.create_thread(user_id)
    return {"thread_id": thread_id}
