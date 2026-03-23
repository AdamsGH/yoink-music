"""Command handler registration for the music plugin."""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any

from telegram.ext import BaseHandler

from yoink.core.plugin import HandlerSpec

logger = logging.getLogger(__name__)

_PKG_DIR = Path(__file__).parent
_SKIP = {"__init__", "inline"}


class _AppShim:
    def __init__(self) -> None:
        self._specs: list[HandlerSpec] = []

    def add_handler(self, handler: BaseHandler, group: int = 0, **_: Any) -> None:
        self._specs.append(HandlerSpec(handler=handler, group=group))

    @property
    def specs(self) -> list[HandlerSpec]:
        return self._specs


def get_handler_specs() -> list[HandlerSpec]:
    shim = _AppShim()
    for module_info in pkgutil.iter_modules([str(_PKG_DIR)]):
        name = module_info.name
        if name.startswith("_") or name in _SKIP:
            continue
        try:
            module = importlib.import_module(f"yoink_music.commands.{name}")
            if hasattr(module, "register"):
                module.register(shim)
                logger.debug("Registered music command module: %s", name)
        except Exception:
            logger.exception("Failed to register music command module: %s", name)
    return shim.specs
