from datetime import datetime
from typing import Optional, Dict, Any
from prisma import Json
from src.services.database_service import db
import logging

logger = logging.getLogger(__name__)


class ResearchSessionRepository:
    """Repository for ResearchSession database operations"""
    
    def __init__(self):
        self.prisma = db.prisma
    
    async def create(
        self,
        thread_id: str,
        user_id: Optional[str],
        research_brief: Optional[Dict[str, Any]] = None,
        task_ids: Optional[Dict[str, str]] = None,
        status: str = 'pending'
    ) -> dict:
        """Create a new research session"""
        try:
            session = await self.prisma.researchsession.create(
                data={
                    'userId': user_id,
                    'status': status,
                    'researchBrief': Json(research_brief) if research_brief is not None else None,
                    'taskIds': Json(task_ids) if task_ids is not None else None,
                    'chatSession': {
                        'connect': {
                            'threadId': thread_id,
                        }
                    },
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error creating research session: {e}")
            raise
    
    async def find_by_id(self, session_id: str) -> Optional[dict]:
        """Find research session by ID"""
        try:
            session = await self.prisma.researchsession.find_unique(
                where={'id': session_id}
            )
            return session
        except Exception as e:
            logger.error(f"Error finding research session by ID: {e}")
            raise
    
    async def find_by_thread_id(self, thread_id: str) -> Optional[dict]:
        """Find latest research session by thread ID"""
        try:
            session = await self.prisma.researchsession.find_first(
                where={'threadId': thread_id},
                order={'createdAt': 'desc'}
            )
            return session
        except Exception as e:
            logger.error(f"Error finding research session by thread ID: {e}")
            raise
    
    async def update_status(
        self,
        session_id: str,
        status: str,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> dict:
        """Update research session status"""
        try:
            update_data = {
                'status': status,
                'updatedAt': datetime.utcnow(),
            }
            
            # error_message is not in the schema, we can put it in 'meta' if needed
            if error_message:
                update_data['meta'] = Json({'errorMessage': error_message})
            
            if completed_at:
                update_data['completedAt'] = completed_at
            
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data=update_data
            )
            return session
        except Exception as e:
            logger.error(f"Error updating session status: {e}")
            raise

    async def update_search_params(
        self,
        session_id: str,
        search_params: Dict[str, Any]
    ) -> dict:
        """Update search params"""
        try:
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data={
                    'searchParams': Json(search_params) if search_params is not None else None,
                    'updatedAt': datetime.utcnow(),
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error updating search params: {e}")
            raise
    
    async def update_search_results(
        self,
        session_id: str,
        search_results: Dict[str, Any]
    ) -> dict:
        """Update search results"""
        try:
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data={
                    'searchResults': Json(search_results) if search_results is not None else None,
                    'updatedAt': datetime.utcnow(),
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error updating search results: {e}")
            raise
    
    async def update_processed_results(
        self,
        session_id: str,
        processed_results: Dict[str, Any]
    ) -> dict:
        """Update processed results"""
        try:
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data={
                    'processedResults': Json(processed_results) if processed_results is not None else None,
                    'updatedAt': datetime.utcnow(),
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error updating processed results: {e}")
            raise
    
    async def update_report(
        self,
        session_id: str,
        report: Dict[str, Any]
    ) -> dict:
        """Update final report"""
        try:
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data={
                    'report': Json(report) if report is not None else None,
                    'updatedAt': datetime.utcnow(),
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error updating report: {e}")
            raise
    
    async def update_task_ids(
        self,
        session_id: str,
        task_ids: Dict[str, str]
    ) -> dict:
        """Update task IDs"""
        try:
            session = await self.prisma.researchsession.update(
                where={'id': session_id},
                data={
                    'taskIds': Json(task_ids) if task_ids is not None else None,
                    'updatedAt': datetime.utcnow(),
                }
            )
            return session
        except Exception as e:
            logger.error(f"Error updating task IDs: {e}")
            raise
    
    async def delete(self, session_id: str) -> None:
        """Delete a research session"""
        try:
            await self.prisma.researchsession.delete(where={'id': session_id})
        except Exception as e:
            logger.error(f"Error deleting research session: {e}")
            raise


# Singleton instance
research_session_repository = ResearchSessionRepository()
