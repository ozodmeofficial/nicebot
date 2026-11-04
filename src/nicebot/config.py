"""Settings from ``.env``: ``load_env()`` and the ``Config`` dict behind ``bot.config``.

Example::

    bot = Nicebot.from_env()
    price = bot.config.int("PRICE", 50_000)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_env(path: str | os.PathLike = ".env", override: bool = False) -> dict[str, str]:
    """Read ``KEY=value`` lines of a ``.env`` file into ``os.environ`` (no extra dependency). Returns what was read.

    Existing variables win unless ``override=True``.

    Example::

        load_env(".env")
        token = os.environ["BOT_TOKEN"]
    """
    p = Path(path)
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return out


class Config(dict):
    """A dict of settings with attribute access and typed getters (``bot.config``).

    Example::

        # .env: SHOP_NAME=Tezbaraka  PRICE=50000  DEBUG=true  MANAGERS=1,2
        bot.config.SHOP_NAME          # "Tezbaraka"
        bot.config.int("PRICE")       # 50000
        bot.config.bool("DEBUG")      # True
        bot.config.ints("MANAGERS")   # [1, 2]
    """

    def __getattr__(self, item: str) -> Any:
        for k in (item, item.upper(), item.lower()):
            if k in self:
                return self[k]
        raise AttributeError(f"Config has no {item!r} (add it to your .env)")

    def str(self, key: str, default: str = "") -> str:  # noqa: A003
        """A value as ``str``.

        Example::

            bot.config.str("SHOP_NAME", "My shop")
        """
        return self.get(key, os.environ.get(key, default))

    def int(self, key: str, default: int = 0) -> int:  # noqa: A003
        """A value as ``int``.

        Example::

            bot.config.int("PRICE", 0)
        """
        v = self.str(key, "")
        return int(v) if v.strip() else default

    def float(self, key: str, default: float = 0.0) -> float:  # noqa: A003
        """A value as ``float``.

        Example::

            bot.config.float("FEE", 0.5)
        """
        v = self.str(key, "")
        return float(v) if v.strip() else default

    def bool(self, key: str, default: bool = False) -> bool:  # noqa: A003
        """A value as ``bool`` (``1/true/yes/on`` are true).

        Example::

            bot.config.bool("DEBUG")
        """
        v = self.str(key, "")
        return v.strip().lower() in ("1", "true", "yes", "on", "ha") if v.strip() else default

    def list(self, key: str, default: list | None = None, sep: str = ",") -> list:  # noqa: A003
        """A comma separated value as a list of strings.

        Example::

            bot.config.list("CITIES")   # ["Tashkent", "Samarkand"]
        """
        v = self.str(key, "")
        return [x.strip() for x in v.split(sep) if x.strip()] if v.strip() else list(default or [])

    def ints(self, key: str, sep: str = ",") -> list[int]:
        """A comma separated value as a list of ints.

        Example::

            bot.config.ints("ADMINS")   # [111, 222]
        """
        return [int(x) for x in self.list(key, sep=sep)]
