"""Music plugin ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from yoink.core.db.base import Base, _now


class MusicResolveLog(Base):
    """Tracks every music link resolve (platform card sent in chat)."""
    __tablename__ = "music_resolve_log"
    __table_args__ = (
        Index("idx_music_resolve_user_date", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "spotify"
    artist: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    platforms_found: Mapped[int] = mapped_column(default=0)  # number of cross-platform links found
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
