from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from src.utils.config import settings
from src.services.firebase_service import firebase_service
from src.services.email_service import email_service
from src.repositories.user_repository import user_repository
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.user_repo = user_repository
    
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
            # Check if user already exists
            existing_user = await self.user_repo.find_by_email(email)
            if existing_user:
                raise ValueError("User with this email already exists")
            
            # Create Firebase user first
            firebase_user = firebase_service.create_user(email, password)
            
            # Hash password for local storage
            hashed_password = self.get_password_hash(password)
            
            # Generate verification code
            verification_code = email_service.generate_verification_code()
            verification_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            
            # Create user in database with Firebase UID
            user = await self.user_repo.create(
                email=email,
                hashed_password=hashed_password,
                firebase_uid=firebase_user["uid"],
                verification_code=verification_code,
                verification_expires_at=verification_expires_at
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
            # Get user from database
            user = await self.user_repo.find_by_email(email)
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
            user = await self.user_repo.find_by_email(email)
            if not user:
                return False
            
            # Check if verification code matches and is not expired
            if (user.verifyCode != verification_code or 
                not user.verifyCodeExpiresAt or 
                user.verifyCodeExpiresAt < datetime.now(timezone.utc)):
                return False
            
            # Update user as verified
            await self.user_repo.update_verification_status(email, True)
            
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
            user = await self.user_repo.find_by_email(email)
            if not user:
                return False
            
            # Generate reset code
            reset_code = email_service.generate_verification_code()
            reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            
            # Update user with reset code
            await self.user_repo.update_verification_code(email, reset_code, reset_expires_at)
            
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
            user = await self.user_repo.find_by_email(email)
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
            await self.user_repo.update_password(email, hashed_password)
            
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
            user = await self.user_repo.find_by_email(email)
            if not user:
                return False
            
            # Check if user is already verified
            if user.isVerified:
                return False
            
            # Generate new verification code
            verification_code = email_service.generate_verification_code()
            verification_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            
            # Update user with new verification code
            await self.user_repo.update_verification_code(email, verification_code, verification_expires_at)
            
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
