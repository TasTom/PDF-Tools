"""Database setup via SQLAlchemy async — supports SQLite (dev) and PostgreSQL (prod)."""
from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, UniqueConstraint,
)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Prefixes d'URL acceptes -> prefixe avec pilote asynchrone.
#
# `DATABASE_URL` est un secret defini ailleurs (Railway, Neon, reglages du Space)
# et il y est presque toujours fourni sous sa forme synchrone, `postgresql://`.
# SQLAlchemy en deduit le pilote `psycopg2` : un moteur asynchrone le refuse, et
# le service ne demarre pas du tout sur un
# « ModuleNotFoundError: No module named 'psycopg2' » — un message qui ne dit ni
# que la base est en cause, ni que seul le prefixe pose probleme.
#
# Le choix du pilote decrit une contrainte de CE code, pas de la base : il est
# donc decide ici plutot que demande a celui qui remplit le secret. Une URL qui
# nomme deja son pilote (`postgresql+asyncpg://`) n'est pas touchee.
_PILOTES_ASYNCES = {
    "postgres://": "postgresql+asyncpg://",
    "postgresql://": "postgresql+asyncpg://",
    "sqlite://": "sqlite+aiosqlite://",
}


def url_asynchrone(url: str) -> str:
    """Ajoute le pilote asynchrone a une URL de connexion si elle n'en a pas."""
    url = url.strip()
    for prefixe, remplacement in _PILOTES_ASYNCES.items():
        if url.startswith(prefixe):
            return remplacement + url[len(prefixe):]
    return url


# Options de requete que libpq (psycopg2) comprend et qu'asyncpg refuse.
#
# asyncpg traite tout parametre inconnu comme un argument de `connect()`, et
# echoue sur « connect() got an unexpected keyword argument 'sslmode' ». Or les
# hebergeurs de base les ajoutent d'office : Neon livre son URL avec
# `?sslmode=require&channel_binding=require`.
_OPTIONS_LIBPQ_IGNOREES = ("channel_binding", "options", "target_session_attrs")


def _nettoyer(url: str) -> tuple[str, dict]:
    """Separe l'URL Postgres des options qu'asyncpg n'accepte pas."""
    if not url.startswith("postgres"):
        # SQLite : aucune option de ce genre, et `make_url` rejetterait un
        # chemin relatif mal forme.
        return url, {}

    propre = make_url(url)
    parametres = dict(propre.query)
    options: dict = {}

    # « disable » et « allow » autorisent une connexion en clair ; tout le reste
    # (« prefer », « require », « verify-ca », « verify-full ») veut du TLS.
    mode = parametres.pop("sslmode", None)
    if mode is not None:
        options["ssl"] = mode not in ("disable", "allow")

    for nom in _OPTIONS_LIBPQ_IGNOREES:
        parametres.pop(nom, None)

    propre = propre.set(query=parametres).render_as_string(hide_password=False)
    return propre, options


DATABASE_URL, _OPTIONS_BASE = _nettoyer(url_asynchrone(settings.DATABASE_URL))

# Journal de demarrage : l'hote et le nom de la base, jamais le mot de passe.
# C'est ce qui manquait pour diagnostiquer l'echec de demarrage en production.
CIBLE_BASE = "?"
try:
    _url = make_url(DATABASE_URL)
    CIBLE_BASE = f"{_url.drivername} {_url.host or ''}{_url.database or ''}".strip()
except Exception:
    CIBLE_BASE = DATABASE_URL.split("://", 1)[0]

# Réglage du pool : plus petit pour SQLite, dimensionné pour PostgreSQL.
_engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True
    # asyncpg attend « ssl » (et non « sslmode ») pour une connexion TLS, comme
    # Neon ou Railway. Une URL sans indication explicite est traitee comme
    # devant etre chiffree : ces bases sont toutes distantes.
    _engine_kwargs["connect_args"] = {"ssl": True, **_OPTIONS_BASE}

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Compte utilisateur.

    Les tables portent le prefixe `pdf_` volontairement. Ce service peut etre
    deploye sur une base PostgreSQL deja utilisee par un autre produit (c'est le
    cas ici : le Space a herite d'une variable DATABASE_URL existante). Sans ce
    prefixe, il ecrirait dans les tables `users` et `daily_usage` de l'autre
    produit : les comptes seraient interchangeables entre les deux sites, et le
    quota quotidien serait partage — une operation sur l'un consommerait le
    quota de l'autre.

    Avec le prefixe, les deux produits cohabitent dans une meme base sans jamais
    se melanger.
    """

    __tablename__ = "pdf_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    auth_provider: str = Column(String(50), default="local")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyUsage(Base):
    """Compteur d'operations par utilisateur et par jour.

    La contrainte d'unicite (user_id, usage_date) est ce qui rend l'increment
    atomique possible : une seule ligne par utilisateur et par jour, donc un
    seul compteur a verrouiller.
    """

    __tablename__ = "pdf_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_pdf_user_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("pdf_users.id"), nullable=False, index=True)
    usage_date = Column(Date, nullable=False, default=date.today)
    operations_count = Column(Integer, default=0)


async def init_db() -> None:
    """Crée les tables au démarrage.

    Le dossier parent est créé au passage quand la base est un fichier SQLite :
    sans cela, la toute première exécution échoue avec « unable to open database
    file », un message qui ne dit pas que le dossier manque.

    Une base injoignable fait echouer le demarrage, volontairement : sans elle,
    aucune inscription ni aucun decompte de quota ne fonctionne, et servir des
    outils en apparence operationnels mais incapables de verifier une session
    serait pire qu'une indisponibilite annoncee.
    """
    if DATABASE_URL.startswith("sqlite"):
        chemin = DATABASE_URL.split("///", 1)[-1]
        if chemin and chemin != ":memory:":
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Fournit une session de base de données pour l'injection de dépendance."""
    async with async_session() as session:
        yield session
