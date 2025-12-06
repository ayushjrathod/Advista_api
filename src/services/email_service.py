from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from src.utils.config import settings
import logging
import secrets
import string
from pydantic import SecretStr
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self._setup_mail_config()
    
    def _setup_mail_config(self):
        """Setup FastAPI-Mail configuration"""
        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=(
                settings.MAIL_STARTTLS
                if settings.MAIL_STARTTLS is not None
                else bool(settings.MAIL_TLS)
            ),
            MAIL_SSL_TLS=(
                settings.MAIL_SSL_TLS
                if settings.MAIL_SSL_TLS is not None
                else bool(settings.MAIL_SSL)
            ),
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True
        )
        self.fastmail = FastMail(self.conf)
    
    def generate_verification_code(self) -> str:
        """Generate a 6-digit verification code"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    async def send_welcome_email(self, email: str, name: Optional[str] = None) -> bool:
        """Send welcome email to new user"""
        try:
            message = MessageSchema(
                subject="Welcome to Advista!",
                recipients=[email],
                body=f"""
                <html>
                <body>
                    <h2>Welcome to Advista!</h2>
                    <p>Hello {name or 'there'},</p>
                    <p>Thank you for joining Advista - your Advertisement Research Engine!</p>
                    <p>We're excited to have you on board. You can now start exploring our platform and discover amazing advertisement insights.</p>
                    <p>If you have any questions, feel free to reach out to our support team.</p>
                    <br>
                    <p>Best regards,<br>The Advista Team</p>
                </body>
                </html>
                """,
                subtype=MessageType.html
            )
            await self.fastmail.send_message(message)
            logger.info(f"Welcome email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False
    
    async def send_verification_email(self, email: str, verification_code: str) -> bool:
        """Send email verification code"""
        try:
            message = MessageSchema(
                subject="Verify Your Email - Advista",
                recipients=[email],
                body=f"""
                <html>
                <body>
                    <h2>Email Verification</h2>
                    <p>Hello,</p>
                    <p>Please use the following code to verify your email address:</p>
                    <h3 style="background-color: #f0f0f0; padding: 10px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 3px;">{verification_code}</h3>
                    <p>This code will expire in 10 minutes.</p>
                    <p>If you didn't request this verification, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>The Advista Team</p>
                </body>
                </html>
                """,
                subtype=MessageType.html
            )
            await self.fastmail.send_message(message)
            logger.info(f"Verification email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            return False
    
    async def send_password_reset_email(self, email: str, reset_code: str) -> bool:
        """Send password reset code"""
        try:
            message = MessageSchema(
                subject="Password Reset - Advista",
                recipients=[email],
                body=f"""
                <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>Hello,</p>
                    <p>You requested to reset your password. Please use the following code:</p>
                    <h3 style="background-color: #f0f0f0; padding: 10px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 3px;">{reset_code}</h3>
                    <p>This code will expire in 15 minutes.</p>
                    <p>If you didn't request this password reset, please ignore this email and your password will remain unchanged.</p>
                    <br>
                    <p>Best regards,<br>The Advista Team</p>
                </body>
                </html>
                """,
                subtype=MessageType.html
            )
            await self.fastmail.send_message(message)
            logger.info(f"Password reset email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return False
    
    async def send_password_reset_success_email(self, email: str) -> bool:
        """Send password reset success notification"""
        try:
            message = MessageSchema(
                subject="Password Reset Successful - Advista",
                recipients=[email],
                body=f"""
                <html>
                <body>
                    <h2>Password Reset Successful</h2>
                    <p>Hello,</p>
                    <p>Your password has been successfully reset.</p>
                    <p>If you didn't make this change, please contact our support team immediately.</p>
                    <br>
                    <p>Best regards,<br>The Advista Team</p>
                </body>
                </html>
                """,
                subtype=MessageType.html
            )
            await self.fastmail.send_message(message)
            logger.info(f"Password reset success email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset success email: {str(e)}")
            return False

# Global instance
email_service = EmailService()
