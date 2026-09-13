"""Application configuration."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

_BASE_DIR = Path(__file__).resolve().parent.parent

# Valeurs de SECRET_KEY refusees : celles des exemples, ou trop courtes pour
# resister a une attaque par force brute.
_INSECURE_KEYS = {"CHANGE-ME-in-production-use-a-real-secret", "", "secret", "changeme"}

class Settings:
    # --- Authentification ---
    # Le service REFUSE de demarrer si SECRET_KEY est absente ou trop faible :
    # un JWT signe avec une cle devinable laisserait n'importe qui se faire
    # passer pour n'importe quel compte.
    _raw_secret: str = os.getenv("SECRET_KEY", "").strip()
    if _raw_secret in _INSECURE_KEYS or len(_raw_secret) < 32:
        raise ValueError(
            "SECRET_KEY manquante ou trop faible. Definir une variable "
            "d'environnement SECRET_KEY de 32 caracteres minimum."
        )
    SECRET_KEY: str = _raw_secret
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Emetteur et destinataire des jetons.
    #
    # Ces deux champs sont verifies a la lecture. Ils protegent d'un cas precis
    # et realiste : ce service a ete deploye sur un Space qui portait deja la
    # SECRET_KEY d'un autre produit. Tant que les deux cles sont identiques, un
    # jeton emis par l'un est dechiffrable par l'autre. Exiger un `aud` propre a
    # ce service fait echouer ces jetons etrangers, meme si la cle fuite ou
    # reste partagee. Le champ ne remplace pas une cle dediee, il limite les
    # degats en attendant.
    TOKEN_ISSUER: str = os.getenv("TOKEN_ISSUER", "pdf-tools")
    TOKEN_AUDIENCE: str = os.getenv("TOKEN_AUDIENCE", "pdf-tools-api")

    # --- Base de donnees ---
    # SQLite pour le developpement local, PostgreSQL en production (Neon,
    # Railway...). Le disque d'un Space HuggingFace est EPHEMERE : un fichier
    # SQLite y serait efface a chaque redeploiement et a chaque reveil, donc le
    # quota quotidien se reinitialiserait tout seul.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{_BASE_DIR / 'data' / 'app.db'}",
    ).strip()

    # --- Quota quotidien (anti-abus) ---
    # Identique pour tous les comptes, et GLOBAL : il couvre toutes les
    # operations, pas une seule. Un quota par outil se contournerait en
    # changeant d'outil.
    DAILY_LIMIT: int = int(os.getenv("DAILY_LIMIT", "20"))

    # --- Uploads ---
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}

    # --- Rate limiting (protection anti-abus, par IP) ---
    # LIGHT : opérations peu coûteuses. HEAVY : conversions gourmandes en CPU.
    RATE_LIMIT_LIGHT: str = os.getenv("RATE_LIMIT_LIGHT", "20/minute")
    RATE_LIMIT_HEAVY: str = os.getenv("RATE_LIMIT_HEAVY", "10/minute")
    RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "10/minute")
    RATE_LIMIT_REGISTER: str = os.getenv("RATE_LIMIT_REGISTER", "5/minute")

    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "https://pdf.warult-tools.com,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]

settings = Settings()
