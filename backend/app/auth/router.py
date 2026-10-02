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

from app.auth.schemas import Token, UserCreate, UserLogin, UserResponse, GoogleLoginRequest
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


async def _infos_jeton_google(credential: str) -> dict:
    """Fait vérifier un jeton d'identité Google et renvoie ses informations.

    Isolé dans sa propre fonction pour deux raisons : l'endpoint reste lisible,
    et les tests peuvent remplacer cet appel sans dépendre du réseau ni de
    Google. Un test qui appellerait vraiment Google ne serait ni déterministe ni
    exécutable hors ligne.

    Lève une `HTTPException` : 503 si Google est injoignable (ce n'est pas la
    faute de l'utilisateur), 401 si le jeton est refusé.
    """
    try:
        import httpx
    except ImportError:
        # Import tardif volontaire : httpx ne sert qu'ici. En import global, son
        # absence ferait échouer le démarrage de TOUTE l'API, y compris les
        # outils PDF qui n'en ont aucun besoin.
        raise HTTPException(
            status_code=503,
            detail="La connexion Google est momentanément indisponible",
        )

    try:
        async with httpx.AsyncClient() as client:
            reponse = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
                timeout=10.0,
            )
    except httpx.HTTPError:
        # Google injoignable : ce n'est pas un jeton invalide, et le dire évite
        # à l'utilisateur de croire que son compte a un problème.
        raise HTTPException(
            status_code=503,
            detail="Google est injoignable pour le moment. Réessayez dans un instant.",
        )

    if reponse.status_code != 200:
        raise HTTPException(status_code=401, detail="Jeton Google invalide")

    return reponse.json()


@router.post("/google", response_model=Token, summary="Se connecter avec Google")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def google_login(request: Request, payload: GoogleLoginRequest,
                       db: AsyncSession = Depends(get_db)):
    """Se connecter (ou créer un compte) avec Google.

    Le site envoie le jeton d'identité Google obtenu par redirection. Ce jeton
    est vérifié **auprès de Google** avant toute création de compte : le client
    ne décide donc pas de l'adresse email qu'il prétend avoir.

    Trois contrôles, chacun fermant une porte précise :

    - la signature et la validité, établies par Google via `tokeninfo` ;
    - `aud` : le jeton a bien été émis pour CE site. Sans ce contrôle, un jeton
      obtenu par n'importe quelle autre application utilisant le même compte
      Google serait accepté ici ;
    - `email_verified` : Google certifie que l'adresse lui appartient. C'est ce
      qui autorise à rattacher le jeton à un compte existant portant le même
      email. Sans ce contrôle, une adresse non vérifiée permettrait de réclamer
      le compte d'autrui.
    """
    if not settings.GOOGLE_CLIENT_ID:
        # Configuration absente : on le dit franchement plutôt que de laisser
        # croire à un problème d'identifiants.
        raise HTTPException(
            status_code=503,
            detail="La connexion Google n'est pas configurée sur ce service",
        )

    infos = await _infos_jeton_google(payload.credential)

    if infos.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=401,
            detail="Jeton Google non autorisé pour ce site",
        )

    email = (infos.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Adresse email absente du jeton Google")

    # Google renvoie la valeur sous forme de chaîne ("true") sur cet endpoint.
    if str(infos.get("email_verified", "")).lower() != "true":
        raise HTTPException(
            status_code=401,
            detail="Cette adresse email Google n'est pas vérifiée",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Ce compte est désactivé")

        # Compte créé par mot de passe, rouvert ici avec Google : Google certifie
        # que l'adresse appartient bien à la personne qui se connecte, le compte
        # lui revient donc. Le mot de passe est retiré au passage — sinon
        # quiconque aurait enregistré cette adresse avant son propriétaire
        # conserverait un accès parallèle au compte.
        #
        # Conséquence assumée : après une première connexion Google, le mot de
        # passe ne fonctionne plus. Le site n'a pas de « mot de passe oublié »,
        # l'accès passe donc désormais par Google.
        if user.auth_provider == "local":
            user.auth_provider = "google"
            user.hashed_password = None
            await db.commit()
    else:
        # Google fournit un nom d'affichage, pas un identifiant : il faut en
        # fabriquer un, unique, en respectant les règles du site (alphanumérique,
        # au moins 3 caractères).
        base = infos.get("name") or email.split("@")[0]
        base = "".join(c for c in base if c.isalnum()).lower()[:30] or "utilisateur"
        if len(base) < 3:
            base = f"{base}pdf"

        username = base
        suffixe = 1
        while True:
            existe = await db.execute(select(User).where(User.username == username))
            if existe.scalar_one_or_none() is None:
                break
            suffixe += 1
            username = f"{base}{suffixe}"

        user = User(
            email=email,
            username=username,
            hashed_password=None,  # aucun mot de passe : l'accès passe par Google
            auth_provider="google",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return Token(
        access_token=create_access_token({"sub": str(user.id)}),
        user=_user_response(user, await _get_daily_usage(db, user.id)),
    )
