"""Exceptions raised by nicebot."""
from __future__ import annotations


class NicebotError(Exception):
    """Base class of every nicebot exception."""


class TelegramError(NicebotError):
    """Telegram returned ``ok: false``."""

    def __init__(self, method: str, description: str, error_code: int = 0, parameters: dict | None = None):
        self.method = method
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}
        super().__init__(f"[{error_code}] {method}: {description}")


class BadRequest(TelegramError):
    """400 — wrong parameters (message not modified, chat not found, ...)."""

    @property
    def not_modified(self) -> bool:
        return "message is not modified" in self.description.lower()


class Unauthorized(TelegramError):
    """401 — the token is wrong or revoked."""


class Forbidden(TelegramError):
    """403 — the bot was blocked by the user or kicked from the chat."""


class NotFound(TelegramError):
    """404 — method or object not found."""


class Conflict(TelegramError):
    """409 — another getUpdates/webhook is running for this token."""


class RetryAfter(TelegramError):
    """429 — flood control. ``retry_after`` seconds to wait."""

    @property
    def retry_after(self) -> float:
        return float(self.parameters.get("retry_after", 1))


class ServerError(TelegramError):
    """5xx — Telegram side problem (retried automatically)."""


class NetworkError(NicebotError):
    """Connection problem (retried automatically)."""


def make_error(method: str, description: str, code: int, parameters: dict | None) -> TelegramError:
    cls = {400: BadRequest, 401: Unauthorized, 403: Forbidden, 404: NotFound, 409: Conflict, 429: RetryAfter}.get(code)
    if cls is None:
        cls = ServerError if code >= 500 else TelegramError
    return cls(method, description, code, parameters)


# ---------------------------------------------------------------- flow control
class FlowSignal(NicebotError):
    """Internal signals that end a handler quietly."""


class Cancelled(FlowSignal):
    """The user cancelled a conversation (``/cancel`` or the cancel button)."""


class AskTimeout(FlowSignal):
    """The user did not answer ``ctx.ask`` in time."""


class StopHandling(FlowSignal):
    """Raise inside a middleware/handler to stop processing the update."""


class SkipHandler(FlowSignal):
    """Raise inside a handler to let the next matching handler run."""


class ValidationError(NicebotError):
    """A validator rejected the user's input. ``str(e)`` is shown to the user."""


class DoesNotExist(NicebotError):
    """ORM: ``Model.get()`` found nothing."""


class MultipleObjectsReturned(NicebotError):
    """ORM: ``Model.get()`` found more than one row."""


class IntegrityError(NicebotError):
    """ORM: unique/constraint violation."""
