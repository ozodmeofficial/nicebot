"""Free HTTPS for local development: ``bot.start(tunnel=True)``.

Telegram opens Mini Apps (and sends webhooks) only over HTTPS. Instead of buying a domain and setting up
certificates while you develop, nicebot can expose your local server through a free tunnel:

* ``cloudflared`` (Cloudflare Quick Tunnels, no account) — used when the ``cloudflared`` program is installed
* ``localhost.run`` (needs only ``ssh``, which macOS, Linux and Windows 10+ already have)

Example::

    bot.webapp("webapp")                       # serves webapp/index.html
    bot.start(tunnel=True)                     # → Mini App: https://random-words.trycloudflare.com/

The address changes on every start, so use it for development only; in production run behind your own
HTTPS domain and pass ``Nicebot(public_url="https://my-domain.uz")``.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import sys
from typing import Sequence

log = logging.getLogger("nicebot.tunnel")

_URL_RE = re.compile(r"https://[a-zA-Z0-9.-]+\.(?:trycloudflare\.com|lhr\.life|localhost\.run|[a-z]{2,})\b")
_IGNORE = ("https://www.cloudflare.com", "https://developers.cloudflare.com", "https://localhost.run", "https://admin.localhost.run",
           "https://twitter.com", "https://github.com")


class TunnelError(RuntimeError):
    """The tunnel could not be opened (program missing, no internet, timeout…).

    Example::

        try:
            url = await tunnel.open(8080)
        except TunnelError as e:
            print(e)
    """


def provider_command(provider: str, port: int) -> list[str]:
    """The command line used for a provider (``"cloudflared"`` or ``"localhost.run"``).

    Example::

        provider_command("cloudflared", 8080)
        # ['cloudflared', 'tunnel', '--no-autoupdate', '--url', 'http://localhost:8080']
    """
    if provider == "cloudflared":
        return ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"]
    if provider in ("localhost.run", "ssh"):
        return ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes",
                "-R", f"80:localhost:{port}", "nokey@localhost.run"]
    raise TunnelError(f"Unknown tunnel provider {provider!r}. Use True, 'cloudflared', 'localhost.run' or a command list.")


def pick_provider() -> str:
    """Choose the first available provider: ``cloudflared``, then ``localhost.run`` (ssh).

    Example::

        pick_provider()   # "cloudflared" if it is installed, else "localhost.run"
    """
    if shutil.which("cloudflared"):
        return "cloudflared"
    if shutil.which("ssh"):
        return "localhost.run"
    raise TunnelError(
        "No tunnel program found. Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) "
        "or OpenSSH, or deploy behind your own HTTPS domain: Nicebot(public_url='https://...')."
    )


def find_url(line: str) -> str | None:
    """Extract the public HTTPS address from a line of tunnel output.

    Example::

        find_url("|  https://red-cat-42.trycloudflare.com  |")   # "https://red-cat-42.trycloudflare.com"
    """
    for m in _URL_RE.finditer(line):
        url = m.group(0)
        if not url.startswith(_IGNORE):
            return url
    return None


class Tunnel:
    """A running tunnel process. ``await tunnel.close()`` stops it (done for you when the bot stops).

    Example::

        tunnel = await Tunnel.open(8080)
        print(tunnel.url)        # https://….trycloudflare.com
        await tunnel.close()
    """

    def __init__(self, url: str, process: asyncio.subprocess.Process, provider: str):
        self.url = url
        self.process = process
        self.provider = provider

    @classmethod
    async def open(cls, port: int, provider: "bool | str | Sequence[str]" = True, *, timeout: float = 40.0) -> "Tunnel":
        """Start a tunnel to ``http://localhost:<port>`` and wait for its public HTTPS address.

        ``provider`` is ``True`` (auto), ``"cloudflared"``, ``"localhost.run"`` or your own command as a list,
        where ``{port}`` is replaced (the first ``https://`` address it prints is used).

        Example::

            tunnel = await Tunnel.open(8080, "localhost.run")
            tunnel = await Tunnel.open(8080, ["ngrok", "http", "{port}", "--log", "stdout"])
        """
        if isinstance(provider, (list, tuple)):
            cmd = [str(c).replace("{port}", str(port)) for c in provider]
            name = cmd[0]
        else:
            name = pick_provider() if provider is True else str(provider)
            cmd = provider_command(name, port)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as e:
            raise TunnelError(f"{cmd[0]!r} is not installed or not on PATH") from e
        assert proc.stdout is not None
        seen: list[str] = []

        async def read_url() -> str:
            assert proc.stdout is not None
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    raise TunnelError(f"{name} exited before giving an address:\n" + "".join(seen[-15:]))
                line = raw.decode(errors="replace")
                seen.append(line)
                url = find_url(line)
                if url:
                    return url

        try:
            url = await asyncio.wait_for(read_url(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TunnelError(f"{name} gave no address within {timeout:.0f}s. Check your internet connection.") from None
        except TunnelError:
            if proc.returncode is None:
                proc.kill()
            raise
        tunnel = cls(url, proc, name)
        asyncio.get_running_loop().create_task(tunnel._drain())
        log.info("🔐 Tunnel (%s): %s → http://localhost:%d", name, url, port)
        return tunnel

    async def _drain(self) -> None:
        # keep reading so the process never blocks on a full pipe
        assert self.process.stdout is not None
        try:
            while await self.process.stdout.readline():
                pass
        except Exception:  # noqa: BLE001
            pass

    async def close(self) -> None:
        """Stop the tunnel process.

        Example::

            await tunnel.close()
        """
        if self.process.returncode is None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), 5)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
        if sys.platform != "win32":
            await asyncio.sleep(0)

    def __repr__(self) -> str:
        return f"<Tunnel {self.provider} {self.url}>"
