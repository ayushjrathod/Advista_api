import logging
from datetime import datetime
from typing import Optional, Dict, Any
from src.repositories.research_session_repository import research_session_repository
from src.services.database_service import db

logger = logging.getLogger(__name__)

class ResearchSessionService:
    """Service for managing research session state using repository pattern"""
    
    def __init__(self):
        self.research_repo = research_session_repository
    
    async def create_session(
        self, 
        thread_id: str, 
        user_id: Optional[str],
        research_brief: Optional[Dict[str, Any]],
        task_ids: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Create a new research session"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.create(
                thread_id=thread_id,
                user_id=user_id,
                research_brief=research_brief,
                task_ids=task_ids,
                status='pending'
            )
            logger.info(f"Created research session {session.id} for thread {thread_id}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error creating research session: {e}")
            raise
    
    async def update_status(
        self, 
        session_id: str, 
        status: str,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update research session status"""
        try:
            if not db.is_connected():
                await db.connect()
            
            completed_at = datetime.utcnow() if status == 'completed' else None
            
            session = await self.research_repo.update_status(
                session_id=session_id,
                status=status,
                error_message=error_message,
                completed_at=completed_at
            )
            logger.info(f"Updated session {session_id} to status: {status}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error updating session status: {e}")
            raise
    
    async def save_search_results(
        self,
        session_id: str,
        search_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save raw search results to database"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.update_search_results(
                session_id=session_id,
                search_results=search_results
            )
            logger.info(f"Saved search results for session {session_id}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error saving search results: {e}")
            raise
    
    async def save_processed_results(
        self,
        session_id: str,
        processed_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save processed results to database"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.update_processed_results(
                session_id=session_id,
                processed_results=processed_results
            )
            logger.info(f"Saved processed results for session {session_id}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error saving processed results: {e}")
            raise
    
    async def save_report(
        self,
        session_id: str,
        report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save final report to database"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.update_report(
                session_id=session_id,
                report=report
            )
            logger.info(f"Saved report for session {session_id}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get research session by ID"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.find_by_id(session_id)
            return session.model_dump() if session else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            raise
    
    async def get_session_by_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get latest research session by thread ID"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.find_by_thread_id(thread_id)
            return session.model_dump() if session else None
        except Exception as e:
            logger.error(f"Error getting session by thread: {e}")
            raise
    
    async def save_task_ids(
        self,
        session_id: str,
        task_ids: Dict[str, str]
    ) -> Dict[str, Any]:
        """Save task IDs to database"""
        try:
            if not db.is_connected():
                await db.connect()
            
            session = await self.research_repo.update_task_ids(
                session_id=session_id,
                task_ids=task_ids
            )
            logger.info(f"Saved task IDs for session {session_id}")
            return session.model_dump()
        except Exception as e:
            logger.error(f"Error saving task IDs: {e}")
            raise

# Singleton instance
research_session_service = ResearchSessionService()
