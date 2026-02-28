from datetime import datetime
from typing import Optional
from src.services.database_service import db
import logging

logger = logging.getLogger(__name__)


class ChatSessionRepository:
    """Repository for ChatSession database operations"""
    
    def __init__(self):
        self.prisma = db.prisma
    
    async def create(
        self,
        thread_id: str,
        user_id: Optional[str],
        status: str,
        last_activity: datetime,
        expires_at: datetime
    ) -> dict:
        """Create a new chat session"""
        try:
            session = await self.prisma.chatsession.create(
                data={
                    "threadId": thread_id,
                    "userId": user_id,
                    "status": status,
                    "lastActivity": last_activity,
                    "expiresAt": expires_at,
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise
    
    async def find_by_id(self, session_id: str) -> Optional[dict]:
        """Find chat session by ID"""
        try:
            session = await self.prisma.chatsession.find_unique(
                where={"id": session_id}
            )
            return session
        except Exception as e:
            logger.error(f"Error finding chat session by ID: {e}")
            raise
    
    async def find_by_thread_id(self, thread_id: str) -> Optional[dict]:
        """Find chat session by thread ID"""
        try:
            session = await self.prisma.chatsession.find_unique(
                where={"threadId": thread_id}
            )
            return session
        except Exception as e:
            logger.error(f"Error finding chat session by thread ID: {e}")
            raise
    
    async def update_status(
        self,
        thread_id: str,
        status: str,
        research_brief: Optional[str] = None
    ) -> dict:
        """Update chat session status"""
        try:
            update_data = {"status": status}
            if research_brief:
                update_data["researchBrief"] = research_brief
            
            session = await self.prisma.chatsession.update(
                where={"threadId": thread_id},
                data=update_data
            )
            return session
        except Exception as e:
            logger.error(f"Error updating chat session status: {e}")
            raise
    
    async def update_last_activity(self, thread_id: str, last_activity: datetime) -> dict:
        """Update last activity timestamp"""
        try:
            session = await self.prisma.chatsession.update(
                where={"threadId": thread_id},
                data={"lastActivity": last_activity}
            )
            return session
        except Exception as e:
            logger.error(f"Error updating last activity: {e}")
            raise
    
    async def delete(self, thread_id: str) -> None:
        """Delete a chat session"""
        try:
            await self.prisma.chatsession.delete(where={"threadId": thread_id})
        except Exception as e:
            logger.error(f"Error deleting chat session: {e}")
            raise


# Singleton instance
chat_session_repository = ChatSessionRepository()
