"""Activity provider for the music plugin."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.core.activity import PluginActivity


async def music_activity_provider(session: AsyncSession, user_id: int) -> PluginActivity:
    from yoink_music.storage.models import MusicResolveLog  # noqa: PLC0415

    base = MusicResolveLog.user_id == user_id
    total = (await session.execute(
        select(func.count()).select_from(MusicResolveLog).where(base)
    )).scalar_one()
    last_at = (await session.execute(
        select(func.max(MusicResolveLog.created_at)).where(base)
    )).scalar_one()

    return PluginActivity(plugin="music", total=total, last_at=last_at, extra={})
