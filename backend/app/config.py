"""Application configuration."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

class Settings:
    # --- Uploads ---
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}

    # --- Rate limiting (protection anti-abus, par IP) ---
    # LIGHT : opérations peu coûteuses. HEAVY : conversions gourmandes en CPU.
    RATE_LIMIT_LIGHT: str = os.getenv("RATE_LIMIT_LIGHT", "20/minute")
    RATE_LIMIT_HEAVY: str = os.getenv("RATE_LIMIT_HEAVY", "10/minute")

    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "https://pdf.warult-tools.com,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]

settings = Settings()
