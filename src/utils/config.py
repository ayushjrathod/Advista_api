# setup config 

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
load_dotenv()

model_config = SettingsConfigDict(env_file=".env")
class Config(BaseSettings):
  ASTRA_DB_TOKEN: str = os.getenv("ASTRA_DB_TOKEN")
  ASTRA_DB_ENDPOINT: str = os.getenv("ASTRA_DB_ENDPOINT")
  GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
  GROQ_API_KEY2: str = os.getenv("GROQ_API_KEY2")
  YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY")
  HF_TOKEN: str = os.getenv("HF_TOKEN")
  LLM_MODEL: str = os.getenv("LLM_MODEL")

  if not ASTRA_DB_TOKEN or not ASTRA_DB_ENDPOINT or not GROQ_API_KEY or not GROQ_API_KEY2 or not YOUTUBE_API_KEY or not HF_TOKEN:
    raise ValueError("Missing environment variables")
