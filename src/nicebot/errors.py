"""Exceptions raised by nicebot. Everything inherits from ``NicebotError``.

Example::

    from nicebot import BadRequest, Forbidden

    try:
        await bot.send_message(user_id, "Hi")
    except Forbidden:
        print("the user blocked the bot")
"""
from __future__ import annotations


class NicebotError(Exception):
    """Base class of every nicebot exception — catch it to handle anything the library raises.

    Example::

        try:
            await ctx.photo("menu.jpg")
        except NicebotError as e:
            log.warning("could not send: %s", e)
    """


class TelegramError(NicebotError):
    """Telegram answered ``ok: false``. Has ``method``, ``description``, ``error_code`` and ``parameters``.

    Example::

        try:
            await bot.send_message(chat_id, "hi")
        except TelegramError as e:
            print(e.error_code, e.description)
    """

    def __init__(self, method: str, description: str, error_code: int = 0, parameters: dict | None = None):
        self.method = method
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}
        super().__init__(f"[{error_code}] {method}: {description}")


class BadRequest(TelegramError):
    """400 — wrong parameters (chat not found, message is not modified, bad HTML…).

    Example::

        try:
            await bot.get_chat("@no_such_channel")
        except BadRequest:
            await ctx.reply("Channel not found")
    """

    @property
    def not_modified(self) -> bool:
        """``True`` for "message is not modified" (``ctx.edit`` already ignores it).

        Example::

            except BadRequest as e:
                if not e.not_modified:
                    raise
        """
        return "message is not modified" in self.description.lower()


class Unauthorized(TelegramError):
    """401 — the token is wrong or revoked.

    Example::

        except Unauthorized:
            print("Get a new token from @BotFather")
    """


class Forbidden(TelegramError):
    """403 — the user blocked the bot, or the bot was removed from the chat.

    Example::

        try:
            await bot.send_message(user_id, "news")
        except Forbidden:
            await User.filter(id=user_id).update(is_blocked=True)
    """


class NotFound(TelegramError):
    """404 — method or object not found.

    Example::

        except NotFound:
            ...
    """


class Conflict(TelegramError):
    """409 — another process uses the same token (polling twice, or polling while a webhook is set).

    Example::

        except Conflict:
            print("Stop the other copy of the bot")
    """


class RetryAfter(TelegramError):
    """429 — flood control; nicebot waits and retries automatically up to ``flood_wait_max``.

    Example::

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
    """

    @property
    def retry_after(self) -> float:
        """Seconds Telegram asked to wait.

        Example::

            e.retry_after   # 14.0
        """
        return float(self.parameters.get("retry_after", 1))


class ServerError(TelegramError):
    """5xx — a problem on Telegram's side (retried automatically).

    Example::

        except ServerError:
            ...
    """


class NetworkError(NicebotError):
    """Connection problem after all retries.

    Example::

        except NetworkError:
            await asyncio.sleep(5)
    """


class FileTooBig(NicebotError):
    """The file is bigger than the 20 MB download limit of the cloud Bot API.

    Run a local Bot API server (https://github.com/tdlib/telegram-bot-api) and pass
    ``Nicebot(api_url="http://localhost:8081")`` to download files up to 2 GB.

    Example::

        try:
            await ctx.media.save()
        except FileTooBig:
            await ctx.reply("The file is too big (max 20 MB)")
    """

    def __init__(self, size: int | None = None):
        self.size = size
        mb = f" ({size / 1024 / 1024:.1f} MB)" if size else ""
        super().__init__(
            f"File is too big to download{mb}: the cloud Bot API allows up to 20 MB. "
            "Use a local Bot API server and Nicebot(api_url=...) for bigger files."
        )


def make_error(method: str, description: str, code: int, parameters: dict | None) -> TelegramError:
    """Create the right ``TelegramError`` subclass for an error code.

    Example::

        make_error("sendMessage", "Forbidden: bot was blocked by the user", 403, None)   # Forbidden(...)
    """
    cls = {400: BadRequest, 401: Unauthorized, 403: Forbidden, 404: NotFound, 409: Conflict, 429: RetryAfter}.get(code)
    if cls is None:
        cls = ServerError if code >= 500 else TelegramError
    return cls(method, description, code, parameters)


# ---------------------------------------------------------------- flow control
class FlowSignal(NicebotError):
    """Base of the internal signals that end a handler quietly (not logged as errors).

    Example::

        except FlowSignal:
            raise
    """


class Cancelled(FlowSignal):
    """The user cancelled a conversation (``/cancel`` or the cancel button). Handled for you; catch it to clean up.

    Example::

        try:
            data = await ctx.form(name="Name?", phone=Phone)
        except Cancelled:
            await ctx.clear_state()
            raise
    """


class AskTimeout(FlowSignal):
    """The user did not answer ``ctx.ask`` in time (``Nicebot(ask_timeout=...)``, default 10 minutes).

    Example::

        try:
            code = await ctx.ask("SMS code?", timeout="2m")
        except AskTimeout:
            await ctx.reply("Too slow, try /login again")
    """


class StopHandling(FlowSignal):
    """Raise in a middleware or handler to stop processing this update silently.

    Example::

        @bot.middleware
        async def banned(ctx: Context, next):
            if ctx.user_id in BANNED:
                raise StopHandling
            await next()
    """


class SkipHandler(FlowSignal):
    """Raise in a handler to let the next matching handler run instead.

    Example::

        @bot.text()
        async def maybe(ctx: Context):
            if not ctx.text.startswith("#"):
                raise SkipHandler
    """


class ValidationError(NicebotError):
    """A validator rejected the answer; ``str(e)`` is shown to the user and the question is asked again.

    Example::

        def even(text: str) -> int:
            if int(text) % 2:
                raise ValidationError("Please send an even number")
            return int(text)
    """


class DoesNotExist(NicebotError):
    """ORM: ``Model.get()`` found nothing.

    Example::

        try:
            order = await Order.get(id=5)
        except DoesNotExist:
            await ctx.reply("No such order")
    """


class MultipleObjectsReturned(NicebotError):
    """ORM: ``Model.get()`` found more than one row.

    Example::

        except MultipleObjectsReturned:
            order = await Order.filter(phone=phone).first()
    """


class IntegrityError(NicebotError):
    """ORM: a unique or NOT NULL constraint was violated.

    Example::

        try:
            await Promo.create(code="NICE")
        except IntegrityError:
            await ctx.reply("This code already exists")
    """
