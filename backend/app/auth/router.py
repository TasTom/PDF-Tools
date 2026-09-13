"""Auth routes: inscription, connexion, profil.

NE PAS ajouter `from __future__ import annotations` dans ce module. Meme piege que
dans `app/main.py` : `@limiter.limit` enveloppe l'endpoint, et FastAPI resout
alors les annotations textuelles dans les globales de slowapi, ou `UserCreate`
n'existe pas. Consequence mesuree : `payload` n'est plus reconnu comme un corps
Pydantic et FastAPI le reclame en parametre de requete — l'inscription repond
`422 {"loc":["query","payload"]}` au lieu de creer le compte.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserCreate, UserLogin, UserResponse
from app.auth.utils import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import DailyUsage, User, get_db
from app.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


def _user_response(user: User, daily_usage: int = 0) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        daily_usage=daily_usage,
        daily_limit=settings.DAILY_LIMIT,
        created_at=str(user.created_at),
    )


async def _get_daily_usage(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_date == date.today(),
        )
    )
    usage = result.scalar_one_or_none()
    return usage.operations_count if usage else 0


@router.post("/register", response_model=Token, status_code=201, summary="Créer un compte")
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Créer un compte utilisateur.

    Retourne un jeton JWT et les informations du compte, quota du jour inclus.
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email déjà utilisé")

    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà pris")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        auth_provider="local",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token, user=_user_response(user, 0))


@router.post("/login", response_model=Token, summary="Se connecter")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(request: Request, payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Se connecter avec email et mot de passe.

    Retourne un jeton à placer dans l'en-tête `Authorization: Bearer <jeton>`.
    Il est requis par tous les outils.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        # Message identique pour un email inconnu et un mot de passe faux :
        # préciser lequel des deux est en cause permettrait d'énumérer les comptes.
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Ce compte est désactivé")

    token = create_access_token({"sub": str(user.id)})
    usage = await _get_daily_usage(db, user.id)
    return Token(access_token=token, user=_user_response(user, usage))


@router.get("/me", response_model=UserResponse, summary="Profil et quota du jour")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Profil du compte connecté, avec sa consommation du jour."""
    usage = await _get_daily_usage(db, user.id)
    return _user_response(user, usage)
