import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from firebase_admin._auth_utils import UserNotFoundError
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class FirebaseService:
    def __init__(self):
        self._initialized = False

    def _ensure_initialized(self):
        if not self._initialized:
            try:
                if not firebase_admin._apps:
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
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized")
                self._initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {str(e)}")
                raise e

    def verify_id_token(self, token: str) -> dict:
        """Verify a Firebase ID token and return its claims."""
        try:
            self._ensure_initialized()
            return firebase_auth.verify_id_token(token)
        except Exception as e:
            logger.error(f"Failed to verify Firebase ID token: {str(e)}")
            raise e

    def get_user_by_email(self, email: str):
        """Get a Firebase user by email if it exists."""
        try:
            self._ensure_initialized()
            return firebase_auth.get_user_by_email(email)
        except UserNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to fetch Firebase user by email: {str(e)}")
            raise e

# Global instance
firebase_service = FirebaseService()
