from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # App environment
    ENVIRONMENT: str = "production"

    # Server settings
    PORT: int = 8000
    
    # Database settings
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/advista"
    DIRECT_URL: Optional[str] = None
    
    # JWT settings
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Cookie settings
    COOKIE_SECURE: bool = True  # Will be overridden in __init__
    COOKIE_SAMESITE: str = "lax"
    COOKIE_MAX_AGE: int = 3600  # 1 hour in seconds
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set secure to False for development
        if self.ENVIRONMENT == "development":
            self.COOKIE_SECURE = False
    
    # Email settings
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: Optional[bool] = True
    MAIL_SSL_TLS: Optional[bool] = False
    MAIL_TLS: Optional[bool] = None
    MAIL_SSL: Optional[bool] = None
    
    # Firebase settings
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_CLIENT_ID: str = ""
    
    #LLM API keys 
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_KEY1: str = ""
    GROQ_API_KEY2: str = ""
    GROQ_API_KEY3: str = ""
    GROQ_API_KEY4: str = ""
    GROQ_API_KEY5: str = ""

    SERPAPI_API_KEY: str = ""
    
    # Feature flags for Celery and Redis
    # Set to False for Lambda (ephemeral filesystem, no background workers)
    # Set to True for development/production with workers
    ENABLE_CELERY: bool = False
    ENABLE_REDIS: bool = False

settings = Settings()
