"""Shared types for yoink-music."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrackInfo:
    title: str
    artist: str
    thumbnail_url: str | None
    source_url: str
    # list of (platform_key, display_name, url)
    links: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class ArtistTrack:
    title: str
    # list of (platform_key, display_name, url)
    links: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class ArtistInfo:
    name: str
    genres: list[str]
    thumbnail_url: str | None
    source_url: str
    # list of (platform_key, display_name, url) for the artist page itself
    platform_links: list[tuple[str, str, str]] = field(default_factory=list)
    top_tracks: list[ArtistTrack] = field(default_factory=list)


class ResolverError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
