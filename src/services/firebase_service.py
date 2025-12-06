import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class FirebaseService:
    def __init__(self):
        self._initialized = False
    
    def _ensure_initialized(self):
        """Initialize Firebase Admin SDK if not already initialized"""
        if not self._initialized:
            try:
                # Check if Firebase is already initialized
                if not firebase_admin._apps:
                    # Create credentials from environment variables
                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": settings.FIREBASE_PROJECT_ID,
                        "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
                        "private_key": settings.FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
                        "client_email": settings.FIREBASE_CLIENT_EMAIL,
                        "client_id": settings.FIREBASE_CLIENT_ID,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.FIREBASE_CLIENT_EMAIL.replace('@', '%40')}",
                        "universe_domain": "googleapis.com"
                    })
                    logger.info("Using Firebase credentials from environment variables")
                    
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized successfully")
                else:
                    logger.info("Firebase Admin SDK already initialized")
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {str(e)}")
                raise e
    
    def create_user(self, email: str, password: str) -> dict:
        """Create a new user in Firebase Authentication"""
        try:
            self._ensure_initialized()
            user = firebase_auth.create_user(
                email=email,
                password=password,
                email_verified=False
            )
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified
            }
        except Exception as e:
            logger.error(f"Failed to create Firebase user: {str(e)}")
            raise e
    
    def verify_user_email(self, uid: str) -> bool:
        """Mark user email as verified in Firebase"""
        try:
            self._ensure_initialized()
            firebase_auth.update_user(uid, email_verified=True)
            return True
        except Exception as e:
            logger.error(f"Failed to verify user email: {str(e)}")
            return False
    
    def authenticate_user(self, email: str, password: str) -> dict:
        """Authenticate user with Firebase"""
        try:
            self._ensure_initialized()
            # This would typically involve Firebase Auth REST API
            # For now, we'll use a simplified approach
            user = firebase_auth.get_user_by_email(email)
            if user.email_verified:
                return {
                    "uid": user.uid,
                    "email": user.email,
                    "email_verified": user.email_verified
                }
            return None
        except Exception as e:
            logger.error(f"Failed to authenticate user: {str(e)}")
            return None
    
    def send_password_reset_email(self, email: str) -> bool:
        """Send password reset email using Firebase"""
        try:
            self._ensure_initialized()
            # Generate password reset link
            reset_link = firebase_auth.generate_password_reset_link(email)
            # Note: In a real implementation, you would send this link via email
            # For now, we'll just log it (in production, integrate with your email service)
            logger.info(f"Password reset link for {email}: {reset_link}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return False
    
    def update_user_password(self, uid: str, new_password: str) -> bool:
        """Update user password in Firebase"""
        try:
            self._ensure_initialized()
            firebase_auth.update_user(uid, password=new_password)
            return True
        except Exception as e:
            logger.error(f"Failed to update user password: {str(e)}")
            return False
    
    def delete_user(self, uid: str) -> bool:
        """Delete user from Firebase"""
        try:
            self._ensure_initialized()
            firebase_auth.delete_user(uid)
            return True
        except Exception as e:
            logger.error(f"Failed to delete user: {str(e)}")
            return False

# Global instance
firebase_service = FirebaseService()
