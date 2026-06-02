import logging
from datetime import datetime
from typing import Optional, Dict, Any
from prisma import Json
from src.services.database_service import db

logger = logging.getLogger(__name__)


class ResearchSessionService:
    async def create_session(self, thread_id: str, user_id: Optional[str], research_brief: Optional[Dict[str, Any]], task_ids: Optional[Dict[str, str]]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.create(
            data={
                'userId': user_id,
                'status': 'pending',
                'researchBrief': Json(research_brief) if research_brief is not None else None,
                'taskIds': Json(task_ids) if task_ids is not None else None,
                'chatSession': {'connect': {'threadId': thread_id}},
            }
        )
        return session.model_dump()

    async def update_status(self, session_id: str, status: str, error_message: Optional[str] = None) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        update_data: Dict[str, Any] = {'status': status, 'updatedAt': datetime.utcnow()}
        if error_message:
            update_data['meta'] = Json({'errorMessage': error_message})
        if status == 'completed':
            update_data['completedAt'] = datetime.utcnow()
        session = await db.prisma.researchsession.update(where={'id': session_id}, data=update_data)
        return session.model_dump()

    async def save_search_results(self, session_id: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.update(
            where={'id': session_id},
            data={'searchResults': Json(search_results) if search_results is not None else None, 'updatedAt': datetime.utcnow()},
        )
        return session.model_dump()

    async def save_processed_results(self, session_id: str, processed_results: Dict[str, Any]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.update(
            where={'id': session_id},
            data={'processedResults': Json(processed_results) if processed_results is not None else None, 'updatedAt': datetime.utcnow()},
        )
        return session.model_dump()

    async def save_report(self, session_id: str, report: Dict[str, Any]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.update(
            where={'id': session_id},
            data={'report': Json(report) if report is not None else None, 'updatedAt': datetime.utcnow()},
        )
        return session.model_dump()

    async def save_resources_used(self, session_id: str, resources_used: Dict[str, Any]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.update(
            where={'id': session_id},
            data={'resourcesUsed': Json(resources_used) if resources_used is not None else None, 'updatedAt': datetime.utcnow()},
        )
        return session.model_dump()

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.find_unique(where={'id': session_id})
        return session.model_dump() if session else None

    async def get_session_by_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.find_first(where={'threadId': thread_id}, order={'createdAt': 'desc'})
        return session.model_dump() if session else None

    async def save_task_ids(self, session_id: str, task_ids: Dict[str, str]) -> Dict[str, Any]:
        if not db.is_connected():
            await db.connect()
        session = await db.prisma.researchsession.update(
            where={'id': session_id},
            data={'taskIds': Json(task_ids) if task_ids is not None else None, 'updatedAt': datetime.utcnow()},
        )
        return session.model_dump()


research_session_service = ResearchSessionService()
