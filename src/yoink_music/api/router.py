"""Music plugin API routes.

Mounted at /api/v1/music/ by the core API factory.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.core.api.deps import get_current_user, get_db
from yoink.core.db.models import User
from yoink_music.storage.models import MusicResolveLog

router = APIRouter(tags=["music"], responses={401: {"description": "Not authenticated"}})


@router.get("/me/stats", summary="My music resolve usage stats")
async def get_my_music_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    thirty_days_ago = now - timedelta(days=30)

    base = select(func.count()).select_from(MusicResolveLog).where(
        MusicResolveLog.user_id == current_user.id,
    )
    total = (await session.execute(base)).scalar() or 0
    this_week = (await session.execute(
        base.where(MusicResolveLog.created_at >= week_start)
    )).scalar() or 0
    today = (await session.execute(
        base.where(MusicResolveLog.created_at >= today_start)
    )).scalar() or 0

    # Top platforms (source)
    platform_rows = (await session.execute(
        select(MusicResolveLog.source_platform, func.count().label("count"))
        .where(MusicResolveLog.user_id == current_user.id)
        .group_by(MusicResolveLog.source_platform)
        .order_by(func.count().desc())
        .limit(10)
    )).all()
    top_platforms = [{"platform": row[0], "count": row[1]} for row in platform_rows]

    # Top artists
    artist_rows = (await session.execute(
        select(MusicResolveLog.artist, func.count().label("count"))
        .where(MusicResolveLog.user_id == current_user.id, MusicResolveLog.artist.isnot(None))
        .group_by(MusicResolveLog.artist)
        .order_by(func.count().desc())
        .limit(10)
    )).all()
    top_artists = [{"artist": row[0], "count": row[1]} for row in artist_rows]

    # Daily history (last 30 days)
    day_rows = (await session.execute(
        select(
            cast(MusicResolveLog.created_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(
            MusicResolveLog.user_id == current_user.id,
            MusicResolveLog.created_at >= thirty_days_ago,
        )
        .group_by("date")
        .order_by("date")
    )).all()
    by_day = [{"date": str(row[0]), "count": row[1]} for row in day_rows]

    return {
        "total": total,
        "this_week": this_week,
        "today": today,
        "top_platforms": top_platforms,
        "top_artists": top_artists,
        "by_day": by_day,
    }
