
from fastapi import APIRouter, Depends
from src.services.chatbot_service import chatbot_service
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import logging
from src.controllers.auth_controller import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatStreamRequest(BaseModel):
    thread_id: str
    message: str


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    async def event_generator():
        async for chunk in chatbot_service.stream(request.thread_id, request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
