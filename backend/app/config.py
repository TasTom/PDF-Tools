"""Application configuration."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

_BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-min-32-chars!")
    SITE_URL: str = os.getenv("SITE_URL", "https://pdf.warult-tools.com").strip()
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    ALGORITHM: str = "HS256"
    
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{_BASE_DIR / 'data' / 'app.db'}",
    ).strip()
    
    FREE_DAILY_LIMIT: int = int(os.getenv("FREE_DAILY_LIMIT", "10"))
    PRO_DAILY_LIMIT: int = int(os.getenv("PRO_DAILY_LIMIT", "500"))
    
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}
    
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "https://pdf.warult-tools.com,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]

settings = Settings()
