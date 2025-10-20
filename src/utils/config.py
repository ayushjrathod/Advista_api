from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, Field
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
    
    # Frontend URL for email links and CORS
    FRONTEND_URL: str = ""

    #LLM API keys 
    OPENAI_API_KEY1: str = ""
    GROQ_API_KEY1: str = ""
    GROQ_API_KEY2: str = ""

settings = Settings()
