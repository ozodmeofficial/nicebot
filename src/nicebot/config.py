"""``.env`` loading and a small typed config object."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_env(path: str | os.PathLike = ".env", override: bool = False) -> dict[str, str]:
    """Read ``KEY=value`` lines into ``os.environ`` (no extra dependency). Returns what was read."""
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
    """Dict with attribute access and typed getters.

    >>> cfg.ADMIN_GROUP          # str
    >>> cfg.int("PRICE", 1000)   # int with default
    >>> cfg.list("ADMINS")       # "1,2,3" -> ["1","2","3"]
    """

    def __getattr__(self, item: str) -> Any:
        for k in (item, item.upper(), item.lower()):
            if k in self:
                return self[k]
        raise AttributeError(f"Config'da '{item}' yo'q")

    def str(self, key: str, default: str = "") -> str:  # noqa: A003
        return self.get(key, os.environ.get(key, default))

    def int(self, key: str, default: int = 0) -> int:  # noqa: A003
        v = self.str(key, "")
        return int(v) if v.strip() else default

    def float(self, key: str, default: float = 0.0) -> float:  # noqa: A003
        v = self.str(key, "")
        return float(v) if v.strip() else default

    def bool(self, key: str, default: bool = False) -> bool:  # noqa: A003
        v = self.str(key, "")
        return v.strip().lower() in ("1", "true", "yes", "on", "ha") if v.strip() else default

    def list(self, key: str, default: list | None = None, sep: str = ",") -> list:  # noqa: A003
        v = self.str(key, "")
        return [x.strip() for x in v.split(sep) if x.strip()] if v.strip() else list(default or [])

    def ints(self, key: str, sep: str = ",") -> list[int]:
        return [int(x) for x in self.list(key, sep=sep)]
