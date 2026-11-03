"""Pretty, colourful console logs (no extra dependency)."""
from __future__ import annotations

import logging
import sys

_COLORS = {"DEBUG": "\033[90m", "INFO": "\033[36m", "WARNING": "\033[33m", "ERROR": "\033[31m", "CRITICAL": "\033[41;97m"}
_RESET = "\033[0m"


class _Formatter(logging.Formatter):
    def __init__(self, color: bool):
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        if self.color:
            c = _COLORS.get(record.levelname, "")
            record.levelname = f"{c}{record.levelname:<7}{_RESET}"
        return super().format(record)


def setup_logging(level: str | int = "INFO") -> None:
    root = logging.getLogger()
    if any(getattr(h, "_nicebot", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter(color=sys.stderr.isatty()))
    handler._nicebot = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level if isinstance(level, int) else level.upper())
    for noisy in ("aiohttp.access", "asyncio", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
