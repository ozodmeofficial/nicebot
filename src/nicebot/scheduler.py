"""Scheduled jobs: ``@bot.every("1h")`` and ``@bot.at("09:00")``.

Days are ``0``–``6``, ``mon``…``sun`` or Uzbek ``du se chor pay ju shan yak``.

Example::

    @bot.every("10m")
    async def heartbeat(bot: Nicebot):
        await bot.storage.set("alive", True, ttl=900)

    @bot.at("21:00", days=["fri"], tz="Asia/Tashkent")
    async def weekly(bot: Nicebot):
        await bot.broadcast("🎉 Weekend sale starts now!")
"""
from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import logging
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .utils import maybe_await

if TYPE_CHECKING:
    from .bot import Nicebot

log = logging.getLogger("nicebot.scheduler")

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
         "du": 0, "se": 1, "chor": 2, "pay": 3, "ju": 4, "shan": 5, "yak": 6}


def _day(d: int | str) -> int:
    if isinstance(d, int):
        return d % 7
    s = str(d).lower()
    for k, v in _DAYS.items():
        if s.startswith(k):
            return v
    raise ValueError(f"Unknown day {d!r}: use 0-6, mon..sun, or Uzbek du, se, chor, pay, ju, shan, yak")


def _zone(tz: str | None) -> Any:
    if not tz:
        return None
    from zoneinfo import ZoneInfo

    return ZoneInfo(tz)


class Job:
    """A scheduled function: every N seconds, or daily at ``HH:MM`` (optionally on some weekdays, in a time zone).

    Created by ``@bot.every`` and ``@bot.at``.

    Example::

        job = Job(cleanup, every=3600)
        job = Job(report, at="09:00", days=["mon", "fri"], tz="Asia/Tashkent")
    """
    def __init__(self, func: Callable[..., Any], *, every: float | None = None, first: float | None = None, at: str | None = None,
                 days: Iterable[int | str] | None = None, tz: str | None = None):
        self.func = func
        self.every = every
        self.first = first
        self.at = None
        if at:
            h, _, m = at.partition(":")
            self.at = (int(h), int(m or 0))
        self.days = None if days is None else {_day(d) for d in days}
        self.tz = tz
        self.name = getattr(func, "__name__", "job")

    def next_delay(self, now: dt.datetime | None = None) -> float:
        """Seconds until the next run.

        Example::

            Job(report, at="09:00").next_delay()   # e.g. 3600.0
        """
        if self.at is None:
            return float(self.every or 60)
        zone = _zone(self.tz)
        now = now or (dt.datetime.now(zone) if zone else dt.datetime.now().astimezone())
        target = now.replace(hour=self.at[0], minute=self.at[1], second=0, microsecond=0)
        while target <= now or (self.days is not None and target.weekday() not in self.days):
            target += dt.timedelta(days=1)
        return (target - now).total_seconds()

    async def call(self, bot: "Nicebot") -> None:
        """Run the function once (``func()`` or ``func(bot)``); errors are logged, not raised.

        Example::

            await job.call(bot)
        """
        try:
            takes = len(inspect.signature(self.func).parameters) >= 1
            await maybe_await(self.func(bot) if takes else self.func())
        except Exception:  # noqa: BLE001
            log.exception("Scheduled job %r failed", self.name)


async def _run(bot: "Nicebot", job: Job) -> None:
    if job.every is not None and job.at is None:
        await asyncio.sleep(job.first if job.first is not None else job.every)
        while True:
            started = asyncio.get_running_loop().time()
            await job.call(bot)
            await asyncio.sleep(max(job.every - (asyncio.get_running_loop().time() - started), 0.01))
    while True:
        await asyncio.sleep(job.next_delay())
        await job.call(bot)
        await asyncio.sleep(1)


async def run_jobs(bot: "Nicebot", jobs: list[Job]) -> None:
    """Run all jobs until cancelled (started by ``bot.run()``).

    Example::

        await run_jobs(bot, bot._jobs)
    """
    if not jobs:
        return
    tasks = [asyncio.create_task(_run(bot, j)) for j in jobs]
    try:
        await asyncio.gather(*tasks)
    finally:
        for t in tasks:
            t.cancel()
