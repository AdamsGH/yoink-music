"""MusicPlugin - implements YoinkPlugin protocol."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from yoink.core.plugin import HandlerSpec, InlineHandlerSpec, PluginContext


class MusicPlugin:
    name = "music"
    version = "0.1.0"

    def __init__(self) -> None:
        from yoink_music.config import MusicConfig
        self._config = MusicConfig()

    def get_config_class(self):
        from yoink_music.config import MusicConfig
        return MusicConfig

    def get_models(self) -> list:
        from yoink_music.storage.models import MusicResolveLog
        return [MusicResolveLog]

    def get_handlers(self) -> list[HandlerSpec]:
        from yoink_music.commands import get_handler_specs
        return get_handler_specs()

    def get_inline_handlers(self) -> list[InlineHandlerSpec]:
        from yoink_music.commands.inline import handle_inline
        from yoink.core.bot.access import AccessPolicy
        from yoink.core.db.models import UserRole
        return [InlineHandlerSpec(
            callback=handle_inline,
            priority=10,
            # No prefix/pattern: catch-all so music shows its hint on empty query
            # before dl's "Type at least 2 characters" message. handler returns
            # False for non-music queries so dl still handles YouTube searches.
            access_policy=AccessPolicy(
                min_role=UserRole.user,
                plugin="music",
                feature="inline",
                check_group_enabled=False,
                check_thread_policy=False,
                silent_deny=True,
            ),
        )]

    def get_features(self):
        from yoink.core.plugin import FeatureSpec
        return [
            FeatureSpec(
                plugin="music",
                feature="inline",
                label="Music Inline Search",
                description="Search and share music links via inline queries (@bot query)",
                default_min_role="user",
            ),
        ]

    def get_routes(self) -> APIRouter | None:
        from yoink_music.api.router import router
        return router

    def get_locale_dir(self) -> Path | None:
        loc = Path(__file__).parent / "i18n" / "locales"
        return loc if loc.exists() else None

    def get_web_manifest(self):
        return None

    def get_jobs(self):
        return None

    def get_commands(self) -> list:
        return []

    def get_help_section(self, role: str, lang: str, granted_features: set[str] | None = None) -> str:
        return ""

    async def setup(self, ctx: PluginContext) -> None:
        from yoink_music.resolver import MusicResolver
        from yoink_music import downloader as _dl_mod

        resolver = MusicResolver(cfg=self._config)
        resolver._session_factory = ctx.session_factory
        await resolver.start()
        ctx.bot_data["music_resolver"] = resolver
        ctx.bot_data["music_config"] = self._config

        from yoink.core.activity import register_activity_provider  # noqa: PLC0415
        from yoink_music.activity import music_activity_provider  # noqa: PLC0415
        register_activity_provider("music", music_activity_provider)

        if self._config.download_enabled:
            if _dl_mod.is_available():
                import logging
                logging.getLogger(__name__).info(
                    "Music download enabled (yoink-dl available)"
                )
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "MUSIC_DOWNLOAD_ENABLED=true but yoink-dl is not installed - downloads disabled"
                )
