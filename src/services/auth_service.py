from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from prisma import Prisma
from src.utils.config import settings
from src.services.firebase_service import firebase_service
from src.services.email_service import email_service
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.prisma = None
    
    async def _ensure_prisma_connected(self):
        """Ensure Prisma client is connected"""
        if self.prisma is None:
            self.prisma = Prisma()
        if not self.prisma.is_connected():
            await self.prisma.connect()
    
    async def _cleanup_prisma(self):
        """Clean up Prisma connection"""
        if self.prisma and self.prisma.is_connected():
            await self.prisma.disconnect()
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[str]:
        """Verify JWT token and return email"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            return email
        except JWTError:
            return None
    
    async def create_user(self, email: str, password: str) -> dict:
        """Create a new user"""
        firebase_user = None
        try:
            await self._ensure_prisma_connected()
            # Check if user already exists
            existing_user = await self.prisma.user.find_unique(where={"email": email})
            if existing_user:
                raise ValueError("User with this email already exists")
            
            # Create Firebase user first
            firebase_user = firebase_service.create_user(email, password)
            
            # Hash password for local storage
            hashed_password = self.get_password_hash(password)
            
            # Generate verification code
            verification_code = email_service.generate_verification_code()
            
            # Create user in database with Firebase UID
            user = await self.prisma.user.create(
                data={
                    "email": email,
                    "password": hashed_password,
                    "firebaseUid": firebase_user["uid"],
                    "verifyCode": verification_code,
                    "verifyCodeExpiresAt": datetime.now(timezone.utc) + timedelta(minutes=10),
                    "isVerified": False
                }
            )
            
            # Send verification email (non-blocking)
            try:
                await email_service.send_verification_email(email, verification_code)
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
            
            # Send welcome email (non-blocking)
            try:
                await email_service.send_welcome_email(email)
            except Exception as e:
                logger.error(f"Failed to send welcome email: {str(e)}")
            
            return {
                "id": user.id,
                "email": user.email,
                "is_verified": user.isVerified,
                "message": "User created successfully. Please check your email for verification code."
            }
            
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            # If Firebase user was created but Prisma failed, clean up Firebase user
            if firebase_user:
                try:
                    firebase_service.delete_user(firebase_user["uid"])
                except:
                    pass
            raise e
    
    async def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        """Authenticate user"""
        try:
            await self._ensure_prisma_connected()
            # Get user from database
            user = await self.prisma.user.find_unique(where={"email": email})
            if not user:
                return None
            
            # Verify password
            if not self.verify_password(password, user.password):
                return None
            
            # Check if user is verified
            if not user.isVerified:
                return {"error": "Please verify your email before signing in"}
            
            # Create access token
            access_token = self.create_access_token(data={"sub": user.email})
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "is_verified": user.isVerified
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to authenticate user: {str(e)}")
            return None
    
    async def verify_email(self, email: str, verification_code: str) -> bool:
        """Verify user email with code"""
        try:
            await self._ensure_prisma_connected()
            user = await self.prisma.user.find_unique(where={"email": email})
            if not user:
                return False
            
            # Check if verification code matches and is not expired
            if (user.verifyCode != verification_code or 
                not user.verifyCodeExpiresAt or 
                user.verifyCodeExpiresAt < datetime.now(timezone.utc)):
                return False
            
            # Update user as verified
            await self.prisma.user.update(
                where={"email": email},
                data={
                    "isVerified": True,
                    "verifyCode": None,
                    "verifyCodeExpiresAt": None
                }
            )
            
            # Update Firebase user
            if user.firebaseUid:
                firebase_service.verify_user_email(user.firebaseUid)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify email: {str(e)}")
            return False
    
    async def forgot_password(self, email: str) -> bool:
        """Initiate forgot password process"""
        try:
            await self._ensure_prisma_connected()
            user = await self.prisma.user.find_unique(where={"email": email})
            if not user:
                return False
            
            # Generate reset code
            reset_code = email_service.generate_verification_code()
            
            # Update user with reset code
            await self.prisma.user.update(
                where={"email": email},
                data={
                    "verifyCode": reset_code,
                    "verifyCodeExpiresAt": datetime.now(timezone.utc) + timedelta(minutes=15)
                }
            )
            
            # Send reset email (non-blocking)
            try:
                await email_service.send_password_reset_email(email, reset_code)
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process forgot password: {str(e)}")
            return False
    
    async def reset_password(self, email: str, reset_code: str, new_password: str) -> bool:
        """Reset user password"""
        try:
            await self._ensure_prisma_connected()
            user = await self.prisma.user.find_unique(where={"email": email})
            if not user:
                return False
            
            # Check if reset code matches and is not expired
            if (user.verifyCode != reset_code or 
                not user.verifyCodeExpiresAt or 
                user.verifyCodeExpiresAt < datetime.now(timezone.utc)):
                return False
            
            # Hash new password
            hashed_password = self.get_password_hash(new_password)
            
            # Update user password
            await self.prisma.user.update(
                where={"email": email},
                data={
                    "password": hashed_password,
                    "verifyCode": None,
                    "verifyCodeExpiresAt": None
                }
            )
            
            # Update Firebase password
            if user.firebaseUid:
                try:
                    firebase_service.update_user_password(user.firebaseUid, new_password)
                except Exception as e:
                    logger.error(f"Failed to update Firebase password: {str(e)}")
            
            # Send success email (non-blocking)
            try:
                await email_service.send_password_reset_success_email(email)
            except Exception as e:
                logger.error(f"Failed to send password reset success email: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset password: {str(e)}")
            return False
    
    async def resend_verification_code(self, email: str) -> bool:
        """Resend verification code to user email"""
        try:
            await self._ensure_prisma_connected()
            user = await self.prisma.user.find_unique(where={"email": email})
            if not user:
                return False
            
            # Check if user is already verified
            if user.isVerified:
                return False
            
            # Generate new verification code
            verification_code = email_service.generate_verification_code()
            
            # Update user with new verification code
            await self.prisma.user.update(
                where={"email": email},
                data={
                    "verifyCode": verification_code,
                    "verifyCodeExpiresAt": datetime.now(timezone.utc) + timedelta(minutes=10)
                }
            )
            
            # Send verification email (non-blocking)
            try:
                await email_service.send_verification_email(email, verification_code)
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to resend verification code: {str(e)}")
            return False

# Global instance
auth_service = AuthService()
