"""MusicPlugin settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class MusicConfig(BaseSettings):
    model_config = {"env_prefix": "MUSIC_", "extra": "ignore"}

    request_timeout: float = 10.0
    cache_ttl: int = 3600

    # Spotify optional: Client Credentials for official API (title + artist).
    # Without these, falls back to oEmbed (title only) + Deezer artist hint.
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None

    # Proxy URL for platforms that block direct requests (e.g. http://user:pass@host:port).
    proxy_url: str | None = None
    # Comma-separated list of platform keys to route through proxy_url.
    # Example: MUSIC_PROXY_PLATFORMS=spotify,soundcloud
    proxy_platforms: str = ""

    # Download feature: send MP3 after the link card. Requires yoink-dl installed.
    # Source priority: YouTube Music → YouTube search fallback.
    download_enabled: bool = False

    def proxy_for(self, platform_key: str) -> str | None:
        """Return proxy URL if this platform should use it, else None."""
        if not self.proxy_url:
            return None
        keys = {k.strip() for k in self.proxy_platforms.split(",") if k.strip()}
        return self.proxy_url if platform_key in keys else None
