"""Validators for ``ctx.ask`` and ``ctx.form``: each one checks the user's answer and turns it into a clean value.

A wrong answer raises ``ValidationError``; ``ctx.ask`` shows its text and asks again.

Example::

    from nicebot import Date, Document, Email, Integer, Phone, Photo, Text

    name  = await ctx.ask("Name?", Text(min=2, max=40))
    age   = await ctx.ask("Age?", Integer(min=14, max=99))
    phone = await ctx.ask("Phone?", Phone)                         # shows a "Share phone" button
    birth = await ctx.ask("Birthday? (DD.MM.YYYY)", Date)
    cv    = await ctx.ask("Send your CV (PDF, max 5 MB)", Document(mime="application/pdf", max_size="5MB"))
"""
from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .errors import ValidationError

if TYPE_CHECKING:
    from .context import Context
    from .media import Media as MediaFile
    from .types import Location as LocationT
    from .types import Message, PhotoSize


class Validator:
    """Base class: override ``check(ctx, message)`` and return the clean value (or ``raise self.fail(ctx)``).

    Arguments every validator accepts: ``prompt`` (the question, used by ``ctx.form``),
    ``error`` (your own error text) and ``optional``.

    Example::

        class EvenNumber(Validator):
            async def check(self, ctx, message):
                n = int(message.text or "1")
                if n % 2:
                    raise self.fail(ctx)          # shows error= or the default text
                return n

        n = await ctx.ask("Send an even number", EvenNumber(error="That is odd!"))
    """

    error_key = "nb.invalid"
    keyboard: Any = None  # reply keyboard shown while asking (e.g. "Share phone")

    def __init__(self, prompt: str | None = None, *, error: str | None = None, optional: bool = False):
        self.prompt = prompt
        self.error = error
        self.optional = optional

    def fail(self, ctx: "Context", key: str | None = None, **kw: Any) -> ValidationError:
        """Build the ``ValidationError`` to raise (your ``error=`` text, or a translated default).

        Example::

            raise self.fail(ctx, "nb.v.min", min=10)
        """
        return ValidationError(self.error or ctx.t(key or self.error_key, **kw))

    async def check(self, ctx: "Context", message: "Message") -> Any:
        """Validate one answer. The base version returns the message text.

        Example::

            value = await Text().check(ctx, ctx.message)
        """
        return message.text

    async def __call__(self, ctx: "Context", message: "Message") -> Any:
        return await self.check(ctx, message)


class Text(Validator):
    """Text with an optional length limit (captions count as text).

    Example::

        comment = await ctx.ask("Your comment?", Text(min=10, max=500))
    """

    error_key = "nb.v.text"

    def __init__(self, prompt: str | None = None, *, min: int | None = None, max: int | None = None, strip: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.min, self.max, self.strip = min, max, strip

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
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
    """A whole number; spaces and separators are allowed (``1 000 000``). Exported as ``Integer``.

    Example::

        qty = await ctx.ask("How many?", Integer(min=1, max=100))
    """

    error_key = "nb.v.int"

    def __init__(self, prompt: str | None = None, *, min: int | None = None, max: int | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.min, self.max = min, max

    async def check(self, ctx: "Context", message: "Message") -> int:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
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
    """A decimal number; a comma works as the decimal point (``12,5``). Exported as ``Number``.

    Example::

        weight = await ctx.ask("Weight, kg?", Number(min=0.1))
    """

    error_key = "nb.v.float"

    async def check(self, ctx: "Context", message: "Message") -> float:  # type: ignore[override]
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
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
    """Normalize a phone number to ``+<digits>``; ``None`` if it does not look like a phone.

    Uzbek numbers are checked by operator code; 9-digit local numbers get ``+998``.

    Example::

        normalize_phone("90 123-45-67")        # "+998901234567"
        normalize_phone("+7 (912) 345-67-89")  # "+79123456789"
        normalize_phone("hello")               # None
    """
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
    """Pretty-print a phone number.

    Example::

        format_phone("+998901234567")   # "+998 90 123 45 67"
    """
    d = re.sub(r"\D", "", phone)
    if d.startswith("998") and len(d) == 12:
        return f"+998 {d[3:5]} {d[5:8]} {d[8:10]} {d[10:12]}"
    return "+" + d


class Phone(Validator):
    """A shared contact or a typed phone number, returned as ``"+998901234567"``.

    ``button=True`` shows a "Share phone" button; ``own=True`` rejects other people's contacts.

    Example::

        phone = await ctx.ask("Your phone number?", Phone)
        phone = await ctx.ask("Phone?", Phone(button=False))
    """

    error_key = "nb.v.phone"

    def __init__(self, prompt: str | None = None, *, button: bool = True, own: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.button, self.own = button, own

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        """The reply keyboard shown while asking (e.g. a "Share phone" button).

        Example::

            Phone().keyboard
        """
        if not self.button:
            return None
        from .keyboards import ReplyButton

        return _LazyText("nb.send_phone", lambda text: [ReplyButton(text, contact=True)])

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
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
    """An e-mail address (lower-cased).

    Example::

        email = await ctx.ask("Your e-mail?", Email)
    """

    error_key = "nb.v.email"
    _rx = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        v = (message.text or "").strip().lower()
        if not self._rx.match(v):
            raise self.fail(ctx)
        return v


class Url(Validator):
    """A link starting with ``http://`` or ``https://``.

    Example::

        site = await ctx.ask("Your website?", Url)
    """

    error_key = "nb.v.url"
    _rx = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        v = (message.text or "").strip()
        if not self._rx.match(v):
            raise self.fail(ctx)
        return v


class Date(Validator):
    """A date such as ``25.12.2026``, returned as ``datetime.date`` (``format`` uses strftime codes).

    Example::

        birthday = await ctx.ask("Birthday? (DD.MM.YYYY)", Date(max=dt.date.today()))
        day = await ctx.ask("Date? (2026-12-25)", Date(format="%Y-%m-%d"))
    """

    error_key = "nb.v.date"

    def __init__(self, prompt: str | None = None, *, format: str = "%d.%m.%Y", min: dt.date | None = None, max: dt.date | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.format, self.min, self.max = format, min, max

    async def check(self, ctx: "Context", message: "Message") -> dt.date:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        human = self.format.replace("%d", ctx.t("nb.date.d")).replace("%m", ctx.t("nb.date.m")).replace("%Y", ctx.t("nb.date.y"))
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
    """One of the given options, shown as reply-keyboard buttons.

    Example::

        size = await ctx.ask("Size?", Choice(choices=["S", "M", "L"]))
        size = await ctx.ask("Size?", ["S", "M", "L"])      # the same, shorter
    """

    error_key = "nb.v.choice"

    def __init__(self, prompt: str | None = None, choices: Iterable[str] = (), *, ignore_case: bool = True, **kw: Any):
        super().__init__(prompt, **kw)
        self.choices = list(choices)
        self.ignore_case = ignore_case

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        """The reply keyboard shown while asking (e.g. a "Share phone" button).

        Example::

            Phone().keyboard
        """
        return self.choices

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        v = (message.text or "").strip()
        for c in self.choices:
            if v == c or (self.ignore_case and v.lower() == c.lower()):
                return c
        raise self.fail(ctx, choices=", ".join(self.choices))


class Regex(Validator):
    """Text that fully matches a regular expression.

    Example::

        passport = await ctx.ask("Passport series?", Regex(r"[A-Z]{2}\\d{7}"))
    """

    error_key = "nb.v.regex"

    def __init__(self, pattern: str, prompt: str | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.rx = re.compile(pattern)

    async def check(self, ctx: "Context", message: "Message") -> str:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        v = (message.text or "").strip()
        if not self.rx.fullmatch(v):
            raise self.fail(ctx)
        return v


class Photo(Validator):
    """A photo; returns the largest ``PhotoSize`` (``.file_id``, ``.width``, ``.height``).

    Example::

        photo = await ctx.ask("Send a photo of the product", Photo)
        await Product.create(photo_id=photo.file_id)
    """

    error_key = "nb.v.photo"

    async def check(self, ctx: "Context", message: "Message") -> "PhotoSize":
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        if not message.photo:
            raise self.fail(ctx)
        return max(message.photo, key=lambda p: (p.width or 0) * (p.height or 0))


class File(Validator):
    """Any file (photo, video, document, audio, voice…) as a ``Media`` object, with optional limits.

    * ``kinds`` — allowed kinds: ``"photo"``, ``"video"``, ``"document"``, ``"audio"``, ``"voice"``, ``"animation"``, ``"video_note"``, ``"sticker"``
    * ``max_size`` — ``"10MB"``, ``"500KB"`` or bytes
    * ``mime`` — ``"application/pdf"``, ``"image/*"`` or a list of them

    Example::

        f = await ctx.ask("Send any file", File)
        cv = await ctx.ask("Send your CV as PDF (max 5 MB)", File(kinds=["document"], mime="application/pdf", max_size="5MB"))
        path = await cv.save("cvs/")

        pic = await ctx.ask("Send a picture", File(mime="image/*"))   # photo or image document
    """

    error_key = "nb.v.file"

    def __init__(self, prompt: str | None = None, *, kinds: Iterable[str] | None = None, max_size: int | str | None = None,
                 mime: str | Iterable[str] | None = None, **kw: Any):
        from .media import parse_size

        super().__init__(prompt, **kw)
        self.kinds = set(kinds) if kinds else None
        self.max_size = parse_size(max_size)
        self.mime = [mime] if isinstance(mime, str) else list(mime) if mime else None

    def _mime_ok(self, mime: str | None) -> bool:
        if not self.mime:
            return True
        if not mime:
            return False
        for pattern in self.mime:
            if pattern.endswith("/*") and mime.startswith(pattern[:-1]):
                return True
            if mime == pattern:
                return True
        return False

    async def check(self, ctx: "Context", message: "Message") -> "MediaFile":
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        from .media import Media as MediaObj
        from .media import human_size

        m = MediaObj.of(message, ctx.bot)
        if m is None or (self.kinds is not None and m.kind not in self.kinds):
            raise self.fail(ctx)
        if self.max_size is not None and m.size is not None and m.size > self.max_size:
            raise self.fail(ctx, "nb.v.too_big", max=human_size(self.max_size))
        if not self._mime_ok(m.mime):
            raise self.fail(ctx, "nb.v.mime")
        return m


class Video(File):
    """A video (``File`` with ``kinds=["video"]``).

    Example::

        clip = await ctx.ask("Send a video (max 50 MB)", Video(max_size="50MB"))
    """

    error_key = "nb.v.video"

    def __init__(self, prompt: str | None = None, **kw: Any):
        kw.setdefault("kinds", ["video"])
        super().__init__(prompt, **kw)


class Document(File):
    """A file sent as a document (``File`` with ``kinds=["document"]``).

    Example::

        report = await ctx.ask("Send the Excel report", Document(mime=["application/vnd.ms-excel",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]))
    """

    error_key = "nb.v.document"

    def __init__(self, prompt: str | None = None, **kw: Any):
        kw.setdefault("kinds", ["document"])
        super().__init__(prompt, **kw)


class Audio(File):
    """A music file (``File`` with ``kinds=["audio"]``).

    Example::

        song = await ctx.ask("Send a song", Audio)
    """

    error_key = "nb.v.audio"

    def __init__(self, prompt: str | None = None, **kw: Any):
        kw.setdefault("kinds", ["audio"])
        super().__init__(prompt, **kw)


class Voice(File):
    """A voice message (``File`` with ``kinds=["voice"]``).

    Example::

        note = await ctx.ask("Record a voice message", Voice)
        await note.save("voices/")
    """

    error_key = "nb.v.voice"

    def __init__(self, prompt: str | None = None, **kw: Any):
        kw.setdefault("kinds", ["voice"])
        super().__init__(prompt, **kw)


class Location(Validator):
    """A shared location (shows a "Share location" button). Returns ``Location`` with ``.latitude``/``.longitude``.

    Example::

        where = await ctx.ask("Where should we deliver?", Location)
        await ctx.reply(f"{where.latitude}, {where.longitude}")
    """

    error_key = "nb.v.location"

    @property
    def keyboard(self) -> Any:  # type: ignore[override]
        """The reply keyboard shown while asking (e.g. a "Share phone" button).

        Example::

            Phone().keyboard
        """
        from .keyboards import ReplyButton

        return _LazyText("nb.send_location", lambda text: [ReplyButton(text, location=True)])

    async def check(self, ctx: "Context", message: "Message") -> "LocationT":
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
        if message.location is None:
            raise self.fail(ctx)
        return message.location


class Custom(Validator):
    """Wrap any function of the text. Raise ``ValueError`` with the message to show the user.

    Example::

        def promo(text: str) -> str:
            if text.upper() not in CODES:
                raise ValueError("Unknown promo code")
            return text.upper()

        code = await ctx.ask("Promo code?", promo)        # functions are wrapped automatically
    """

    def __init__(self, func: Callable[[str], Any], prompt: str | None = None, **kw: Any):
        super().__init__(prompt, **kw)
        self.func = func

    async def check(self, ctx: "Context", message: "Message") -> Any:
        """Validate one answer and return the clean value (raises ``ValidationError`` otherwise).

        Example::

            value = await validator.check(ctx, ctx.message)
        """
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
    """Turn what you pass to ``ctx.ask`` into a validator.

    ``int`` → ``Integer()``, ``Phone`` (class) → ``Phone()``, ``["a", "b"]`` → ``Choice``, a function → ``Custom``.

    Example::

        as_validator(int)            # Int()
        as_validator(["S", "M"])     # Choice(choices=["S", "M"])
    """
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
    raise TypeError(f"Not a validator: {spec!r}. Use str, int, float, a Validator, a list of choices or a function.")
