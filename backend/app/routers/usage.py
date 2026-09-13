"""Route d'usage — expose le quota quotidien (anti-abus) au compte connecté."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UsageInfo
from app.auth.utils import get_current_user
from app.database import User, get_db
from app.services.usage import get_usage_info

router = APIRouter(prefix="/api", tags=["Utilisation"])


@router.get("/usage", response_model=UsageInfo, summary="Utilisation et quota du jour")
async def usage_info(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quota quotidien du compte connecté.

    - **daily_usage** : opérations effectuées aujourd'hui
    - **daily_limit** : quota quotidien (`DAILY_LIMIT`)
    - **remaining** : opérations restantes avant la réinitialisation
    """
    return await get_usage_info(db, user)
