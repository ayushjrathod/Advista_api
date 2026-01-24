from datetime import datetime
from typing import Optional
from src.services.database_service import db
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User database operations"""
    
    def __init__(self):
        self.prisma = db.prisma
    
    async def find_by_email(self, email: str) -> Optional[dict]:
        """Find user by email"""
        try:
            user = await self.prisma.user.find_unique(where={"email": email})
            return user
        except Exception as e:
            logger.error(f"Error finding user by email: {e}")
            raise
    
    async def find_by_id(self, user_id: str) -> Optional[dict]:
        """Find user by ID"""
        try:
            user = await self.prisma.user.find_unique(where={"id": user_id})
            return user
        except Exception as e:
            logger.error(f"Error finding user by ID: {e}")
            raise
    
    async def create(
        self,
        email: str,
        hashed_password: str,
        firebase_uid: str,
        verification_code: str,
        verification_expires_at: datetime
    ) -> dict:
        """Create a new user"""
        try:
            user = await self.prisma.user.create(
                data={
                    "email": email,
                    "password": hashed_password,
                    "firebaseUid": firebase_uid,
                    "verifyCode": verification_code,
                    "verifyCodeExpiresAt": verification_expires_at,
                    "isVerified": False
                }
            )
            return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def update_verification_status(self, email: str, is_verified: bool) -> dict:
        """Update user verification status"""
        try:
            user = await self.prisma.user.update(
                where={"email": email},
                data={
                    "isVerified": is_verified,
                    "verifyCode": None,
                    "verifyCodeExpiresAt": None
                }
            )
            return user
        except Exception as e:
            logger.error(f"Error updating verification status: {e}")
            raise
    
    async def update_verification_code(
        self,
        email: str,
        verification_code: str,
        expires_at: datetime
    ) -> dict:
        """Update user verification code"""
        try:
            user = await self.prisma.user.update(
                where={"email": email},
                data={
                    "verifyCode": verification_code,
                    "verifyCodeExpiresAt": expires_at
                }
            )
            return user
        except Exception as e:
            logger.error(f"Error updating verification code: {e}")
            raise
    
    async def update_password(self, email: str, hashed_password: str) -> dict:
        """Update user password"""
        try:
            user = await self.prisma.user.update(
                where={"email": email},
                data={
                    "password": hashed_password,
                    "verifyCode": None,
                    "verifyCodeExpiresAt": None
                }
            )
            return user
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            raise
    
    async def delete(self, user_id: str) -> None:
        """Delete a user"""
        try:
            await self.prisma.user.delete(where={"id": user_id})
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise


# Singleton instance
user_repository = UserRepository()
