"""Suivi d'usage — applique le quota quotidien partage par tous les comptes."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import DailyUsage, User


async def get_or_create_usage(db: AsyncSession, user_id: int) -> DailyUsage:
    """Récupère ou crée la ligne d'usage du jour pour cet utilisateur."""
    today = date.today()
    result = await db.execute(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_date == today,
        )
    )
    usage = result.scalar_one_or_none()
    if usage is None:
        usage = DailyUsage(user_id=user_id, usage_date=today, operations_count=0)
        db.add(usage)
        await db.flush()
    return usage


async def check_and_increment_usage(db: AsyncSession, user: User) -> int:
    """Vérifie le quota restant, incrémente, et renvoie le nouveau compte.

    L'incrément se fait en UNE requête `UPDATE ... RETURNING` conditionnée par
    `operations_count < limit`. C'est ce qui évite la course entre deux requêtes
    simultanées : deux appels concurrents ne peuvent pas lire le même compte
    puis l'incrémenter chacun de leur côté, ce qui laisserait passer une
    opération de trop.

    Lève une HTTPException 429 si le quota est atteint.
    """
    limit = settings.DAILY_LIMIT
    today = date.today()

    stmt = (
        sql_update(DailyUsage)
        .where(
            DailyUsage.user_id == user.id,
            DailyUsage.usage_date == today,
            DailyUsage.operations_count < limit,
        )
        .values(operations_count=DailyUsage.operations_count + 1)
        .returning(DailyUsage.operations_count)
    )
    result = await db.execute(stmt)
    new_count = result.scalar_one_or_none()

    if new_count is not None:
        await db.commit()
        return new_count

    # Aucune ligne mise à jour : soit elle n'existe pas encore, soit le quota
    # est atteint.
    usage = await get_or_create_usage(db, user.id)
    if usage.operations_count >= limit:
        await db.commit()
        # « 1 opérations » se lit mal : l'accord est fait ici plutot que dans le
        # front, pour que le message reste correct quel que soit l'appelant.
        unite = "opération" if limit == 1 else "opérations"
        raise HTTPException(
            status_code=429,
            detail=(
                f"Limite quotidienne atteinte ({limit} {unite} par jour). "
                "Le quota se réinitialise à minuit."
            ),
        )
    usage.operations_count += 1
    await db.commit()
    return usage.operations_count


async def get_usage_info(db: AsyncSession, user: User) -> dict:
    """Renvoie l'état du quota du jour pour cet utilisateur."""
    usage = await get_or_create_usage(db, user.id)
    await db.commit()
    limit = settings.DAILY_LIMIT
    return {
        "daily_usage": usage.operations_count,
        "daily_limit": limit,
        "remaining": max(0, limit - usage.operations_count),
    }
