from typing import Any
from src.services.firebase_service import firebase_service
from src.repositories.user_repository import user_repository
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.user_repo = user_repository

    @staticmethod
    def _fallback_email(firebase_uid: str) -> str:
        return f"anonymous-{firebase_uid}@advista.local"

    async def sync_firebase_user(self, claims: dict[str, Any]) -> Any:
        """Create or update the local app user from verified Firebase claims."""
        firebase_uid = claims.get("uid")
        email = claims.get("email") or self._fallback_email(firebase_uid) if firebase_uid else None

        if not firebase_uid or not email:
            raise ValueError("Firebase token is missing required identity claims")

        is_verified = bool(claims.get("email_verified", False))

        user = await self.user_repo.find_by_firebase_uid(firebase_uid)
        if user:
            return await self.user_repo.update_from_firebase(
                user_id=user.id,
                email=email,
                firebase_uid=firebase_uid,
                is_verified=is_verified,
            )

        user_by_email = await self.user_repo.find_by_email(email)
        if user_by_email:
            return await self.user_repo.update_from_firebase(
                user_id=user_by_email.id,
                email=email,
                firebase_uid=firebase_uid,
                is_verified=is_verified,
            )

        return await self.user_repo.create(
            email=email,
            firebase_uid=firebase_uid,
            is_verified=is_verified,
        )

    def is_email_available(self, email: str) -> bool:
        """Check email availability against Firebase Auth."""
        return firebase_service.get_user_by_email(email) is None

# Global instance
auth_service = AuthService()
