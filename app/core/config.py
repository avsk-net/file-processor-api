# app/core/config.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file into environment variables
load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "FileProcessorAPI")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "storage/uploads")
    PROCESSED_DIR: str = os.getenv("PROCESSED_DIR", "storage/processed")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", 50))
    FILE_EXPIRY_HOURS: int = int(os.getenv("FILE_EXPIRY_HOURS", 24))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "files.db")

    # Derived — computed from the above
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

settings = Settings()
