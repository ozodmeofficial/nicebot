"""Validators for ``ctx.ask`` and ``ctx.form``. Each one turns a message into a clean value or raises ``ValidationError``."""
from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .errors import ValidationError

if TYPE_CHECKING:
    from .context import Context
    from .types import Message


class Validator:
    """Base: override ``check(ctx, message) -> value``. ``prompt`` is the question shown."""

    error_key = "nb.invalid"
    keyboard: Any = None  # reply keyboard shown while asking (e.g. "send phone")

    def __init__(self, prompt: str | None = None, *, error: str | None = None, optional: bool = False):
        self.prompt = prompt
        self.error = error
        self.optional = optional

    def fail(self, ctx: "Context", key: str | None = None, **kw: Any) -> ValidationError:
        return ValidationError(self.error or ctx.t(key or self.error_key, **kw))

    async def check(self, ctx: "Context", message: "Message") -> Any:
        return message.text

    async def __call__(self, ctx: "Context", message: "Message") -> Any:
        return await self.check(ctx, message)


class Text(Validator):
    error_key = "nb.v.text"

    def __init__(self, prompt: str | None = None, *, min: int | None = None, max: int | None = None, strip: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.min, self.max, self.strip = min, max, strip

    async def check(self, ctx: "Context", message: "Message") -> str:
        text = message.text if message.text is not None else message.caption
        if text is None:
            raise self.fail(ctx)
        if self.strip:
            text = text.strip()
        if self.min is not None and len(text) < self.min:
            raise self.fail(ctx, "nb.v.len_min", min=self.min)
        if self.max is not None and len(text) > self.max:
            raise self.fail(ctx, "nb.v.len_max", max=self.max)
        return text


class Int(Validator):
    error_key = "nb.v.int"

    def __init__(self, prompt: str | None = None, *, min: int | None = None, max: int | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.min, self.max = min, max

    async def check(self, ctx: "Context", message: "Message") -> int:
        raw = (message.text or "").replace(" ", "").replace("_", "").replace(",", "")
        if not re.fullmatch(r"[-+]?\d+", raw):
            raise self.fail(ctx)
        v = int(raw)
        if self.min is not None and v < self.min:
            raise self.fail(ctx, "nb.v.min", min=self.min)
        if self.max is not None and v > self.max:
            raise self.fail(ctx, "nb.v.max", max=self.max)
        return v


class Float(Int):
    error_key = "nb.v.float"

    async def check(self, ctx: "Context", message: "Message") -> float:  # type: ignore[override]
        raw = (message.text or "").replace(" ", "").replace(",", ".")
        try:
            v = float(raw)
        except ValueError:
            raise self.fail(ctx) from None
        if self.min is not None and v < self.min:
            raise self.fail(ctx, "nb.v.min", min=self.min)
        if self.max is not None and v > self.max:
            raise self.fail(ctx, "nb.v.max", max=self.max)
        return v


_UZ_CODES = ("33", "50", "55", "61", "62", "65", "66", "67", "69", "70", "71", "72", "73", "74", "75", "76", "77", "78", "79", "87", "88", "90", "91", "93", "94", "95", "97", "98", "99", "20")


def normalize_phone(raw: str, default_country: str = "998") -> str | None:
    """``"90 123-45-67"`` → ``"+998901234567"``. Returns ``None`` if it doesn't look like a phone."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if len(digits) == 9 and default_country == "998":
        digits = "998" + digits
    if digits.startswith("8") and len(digits) == 10 and default_country == "998":
        digits = "998" + digits[1:]  # old domestic format: 8 90 123 45 67
    if not 10 <= len(digits) <= 15:
        return None
    if digits.startswith("998") and (len(digits) != 12 or digits[3:5] not in _UZ_CODES):
        return None
    return "+" + digits


def format_phone(phone: str) -> str:
    """``"+998901234567"`` → ``"+998 90 123 45 67"``."""
    d = re.sub(r"\D", "", phone)
    if d.startswith("998") and len(d) == 12:
        return f"+998 {d[3:5]} {d[5:8]} {d[8:10]} {d[10:12]}"
    return "+" + d


class Phone(Validator):
    """Accepts a shared contact or a typed number. Uzbek numbers are checked by operator code."""

    error_key = "nb.v.phone"

    def __init__(self, prompt: str | None = None, *, button: bool = True, own: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.button, self.own = button, own

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        if not self.button:
            return None
        from .keyboards import ReplyButton

        return _LazyText("nb.send_phone", lambda text: [ReplyButton(text, contact=True)])

    async def check(self, ctx: "Context", message: "Message") -> str:
        if message.contact is not None:
            if self.own and message.contact.user_id and ctx.user_id and message.contact.user_id != ctx.user_id:
                raise self.fail(ctx)
            phone = normalize_phone(message.contact.phone_number)
        else:
            phone = normalize_phone(message.text or "")
        if not phone:
            raise self.fail(ctx)
        return phone


class Email(Validator):
    error_key = "nb.v.email"
    _rx = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")

    async def check(self, ctx: "Context", message: "Message") -> str:
        v = (message.text or "").strip().lower()
        if not self._rx.match(v):
            raise self.fail(ctx)
        return v


class Url(Validator):
    error_key = "nb.v.url"
    _rx = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)

    async def check(self, ctx: "Context", message: "Message") -> str:
        v = (message.text or "").strip()
        if not self._rx.match(v):
            raise self.fail(ctx)
        return v


class Date(Validator):
    """Parses dates like ``25.12.2026`` (``format`` uses strftime codes)."""

    error_key = "nb.v.date"

    def __init__(self, prompt: str | None = None, *, format: str = "%d.%m.%Y", min: dt.date | None = None, max: dt.date | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.format, self.min, self.max = format, min, max

    async def check(self, ctx: "Context", message: "Message") -> dt.date:
        human = self.format.replace("%d", "KK").replace("%m", "OO").replace("%Y", "YYYY")
        try:
            v = dt.datetime.strptime((message.text or "").strip(), self.format).date()
        except ValueError:
            raise self.fail(ctx, format=human) from None
        if self.min and v < self.min:
            raise self.fail(ctx, "nb.v.min", min=self.min.strftime(self.format))
        if self.max and v > self.max:
            raise self.fail(ctx, "nb.v.max", max=self.max.strftime(self.format))
        return v


class Choice(Validator):
    """One of the given options (shown as reply buttons)."""

    error_key = "nb.v.choice"

    def __init__(self, prompt: str | None = None, choices: Iterable[str] = (), *, ignore_case: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.choices = list(choices)
        self.ignore_case = ignore_case

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        return self.choices

    async def check(self, ctx: "Context", message: "Message") -> str:
        v = (message.text or "").strip()
        for c in self.choices:
            if v == c or (self.ignore_case and v.lower() == c.lower()):
                return c
        raise self.fail(ctx, choices=", ".join(self.choices))


class Regex(Validator):
    error_key = "nb.v.regex"

    def __init__(self, pattern: str, prompt: str | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.rx = re.compile(pattern)

    async def check(self, ctx: "Context", message: "Message") -> str:
        v = (message.text or "").strip()
        if not self.rx.fullmatch(v):
            raise self.fail(ctx)
        return v


class Photo(Validator):
    """Returns the largest ``PhotoSize`` (use ``.file_id``)."""

    error_key = "nb.v.photo"

    async def check(self, ctx: "Context", message: "Message") -> Any:
        if not message.photo:
            raise self.fail(ctx)
        return message.photo[-1]


class File(Validator):
    """Any document/photo/video/audio/voice. Returns the media object."""

    error_key = "nb.v.file"

    async def check(self, ctx: "Context", message: "Message") -> Any:
        for attr in ("document", "video", "audio", "voice", "video_note", "animation"):
            v = getattr(message, attr, None)
            if v is not None:
                return v
        if message.photo:
            return message.photo[-1]
        raise self.fail(ctx)


class Location(Validator):
    error_key = "nb.v.location"

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        from .keyboards import ReplyButton

        return _LazyText("nb.send_location", lambda text: [ReplyButton(text, location=True)])

    async def check(self, ctx: "Context", message: "Message") -> Any:
        if message.location is None:
            raise self.fail(ctx)
        return message.location


class Custom(Validator):
    """Wrap any function: ``Custom(lambda text: text.upper())``. Raise ``ValueError`` with the message to show."""

    def __init__(self, func: Callable[[str], Any], prompt: str | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.func = func

    async def check(self, ctx: "Context", message: "Message") -> Any:
        from .utils import maybe_await

        try:
            return await maybe_await(self.func(message.text or ""))
        except ValidationError:
            raise
        except (ValueError, TypeError) as e:
            raise ValidationError(str(e) or ctx.t("nb.invalid")) from None


class _LazyText:
    """A keyboard whose label depends on the user's language."""

    def __init__(self, key: str, make: Callable[[str], Any]):
        self.key, self.make = key, make

    def resolve(self, ctx: "Context") -> Any:
        return self.make(ctx.t(self.key))


TYPE_MAP: dict[Any, type[Validator]] = {str: Text, int: Int, float: Float, dt.date: Date}


def as_validator(spec: Any, prompt: str | None = None) -> Validator:
    """``int`` → Int(), ``Phone`` (class) → Phone(), ``["a","b"]`` → Choice, callable → Custom."""
    if isinstance(spec, Validator):
        if prompt and not spec.prompt:
            spec.prompt = prompt
        return spec
    if isinstance(spec, type) and issubclass(spec, Validator):
        return spec(prompt)
    if spec in TYPE_MAP:
        return TYPE_MAP[spec](prompt)
    if isinstance(spec, (list, tuple)) and all(isinstance(x, str) for x in spec):
        return Choice(prompt, spec)
    if callable(spec):
        return Custom(spec, prompt)
    if spec is None:
        return Text(prompt)
    raise TypeError(f"Validator emas: {spec!r}")
