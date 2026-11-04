"""Hot reload: ``bot.start(reload=True)`` restarts the bot when a ``.py``/``.json``/``.toml``/``.env`` file changes.

Example::

    bot.start(reload=True)
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("nicebot.reload")
ENV = "NICEBOT_RELOAD_CHILD"
WATCH = (".py", ".json", ".toml", ".env")
SKIP = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", ".mypy_cache", ".pytest_cache", "site-packages", "dist", "build"}


def _snapshot(root: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for f in filenames:
            if f.endswith(WATCH) or f == ".env":
                p = os.path.join(dirpath, f)
                try:
                    out[p] = os.stat(p).st_mtime
                except OSError:
                    pass
    return out


def supervise(root: str | os.PathLike | None = None, interval: float = 0.7) -> bool:
    """Run the bot in a child process and restart it when a watched file changes.

    Returns ``False`` inside the child (keep running the bot) and ``True`` in the parent once it exits.

    Example::

        if not supervise():     # what bot.start(reload=True) does
            asyncio.run(bot.run())
    """
    if os.environ.get(ENV) == "1":
        return False
    base = Path(root or os.getcwd())
    env = {**os.environ, ENV: "1"}
    log.info("♻️  Hot reload is on — watching %s", base)
    while True:
        snap = _snapshot(base)
        child = subprocess.Popen([sys.executable, *sys.argv], env=env)
        try:
            while True:
                time.sleep(interval)
                if child.poll() is not None:
                    log.warning("The bot process exited (code %s). Waiting for a change...", child.returncode)
                    while _snapshot(base) == snap:
                        time.sleep(interval)
                    break
                new = _snapshot(base)
                if new != snap:
                    changed = sorted(set(new.items()) ^ set(snap.items()))
                    log.info("♻️  %s changed — restarting", Path(changed[0][0]).name if changed else "a file")
                    break
        except KeyboardInterrupt:
            child.terminate()
            try:
                child.wait(10)
            except subprocess.TimeoutExpired:
                child.kill()
            return True
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(10)
            except subprocess.TimeoutExpired:
                child.kill()
