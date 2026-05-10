from typing import Any
from src.services.firebase_service import firebase_service
from src.services.database_service import db
import logging

logger = logging.getLogger(__name__)

class AuthService:
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

        user = await db.prisma.user.find_unique(where={"firebaseUid": firebase_uid})
        if user:
            return await db.prisma.user.update(
                where={"id": user.id},
                data={"email": email, "firebaseUid": firebase_uid, "isVerified": is_verified},
            )

        user_by_email = await db.prisma.user.find_unique(where={"email": email})
        if user_by_email:
            return await db.prisma.user.update(
                where={"id": user_by_email.id},
                data={"email": email, "firebaseUid": firebase_uid, "isVerified": is_verified},
            )

        return await db.prisma.user.create(
            data={"email": email, "password": "", "firebaseUid": firebase_uid, "isVerified": is_verified}
        )

    def is_email_available(self, email: str) -> bool:
        """Check email availability against Firebase Auth."""
        return firebase_service.get_user_by_email(email) is None

auth_service = AuthService()
