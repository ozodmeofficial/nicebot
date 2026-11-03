"""Translations. Put ``locales/uz.json``, ``locales/ru.json``… next to your bot and call ``ctx.t("key")``."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("nicebot.i18n")

# Texts the library itself shows. Override any of them in your own locale files.
BUILTIN: dict[str, dict[str, str]] = {
    "uz": {
        "nb.yes": "✅ Ha",
        "nb.no": "❌ Yo'q",
        "nb.done": "✔️ Tayyor",
        "nb.cancel": "🚫 Bekor qilish",
        "nb.cancelled": "Bekor qilindi.",
        "nb.back": "⬅️ Orqaga",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Javob kutish vaqti tugadi.",
        "nb.invalid": "❗️ Noto'g'ri qiymat, qaytadan kiriting.",
        "nb.too_many_tries": "Juda ko'p urinish. Keyinroq qayta boshlang.",
        "nb.expired": "⌛️ Bu tugmaning muddati tugagan.",
        "nb.not_yours": "🙅 Bu tugma siz uchun emas.",
        "nb.used": "Bu tugma allaqachon ishlatilgan.",
        "nb.throttled": "⏳ Biroz kuting...",
        "nb.maintenance": "🛠 Botda texnik ishlar olib borilmoqda. Birozdan so'ng qaytib keling.",
        "nb.subscribe": "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        "nb.check": "✅ Tekshirish",
        "nb.not_subscribed": "❗️ Hali hamma kanallarga obuna bo'lmadingiz.",
        "nb.error": "😔 Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
        "nb.send_phone": "📞 Raqamni yuborish",
        "nb.send_location": "📍 Joylashuvni yuborish",
        "nb.choose_hint": "Variantlarni tanlang va «Tayyor» tugmasini bosing.",
        "nb.page": "Sahifa {page}/{pages}",
        "nb.empty": "Hech narsa topilmadi.",
        "nb.captcha": "{mention}, guruhga xush kelibsiz! Robot emasligingizni tasdiqlang ({seconds} soniya).",
        "nb.captcha_button": "🤖 Men robot emasman",
        "nb.captcha_ok": "✅ Rahmat, endi yozishingiz mumkin.",
        "nb.warned": "⚠️ {mention} ogohlantirildi ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} {limit} ta ogohlantirishdan so'ng chetlatildi.",
        "nb.support_sent": "✅ Xabaringiz yuborildi. Tez orada javob beramiz.",
        "nb.v.int": "Butun son kiriting.",
        "nb.v.float": "Son kiriting (masalan, 12.5).",
        "nb.v.min": "Qiymat {min} dan kichik bo'lmasin.",
        "nb.v.max": "Qiymat {max} dan katta bo'lmasin.",
        "nb.v.len_min": "Kamida {min} ta belgi kiriting.",
        "nb.v.len_max": "Ko'pi bilan {max} ta belgi kiriting.",
        "nb.v.phone": "Telefon raqamini to'g'ri kiriting: +998 90 123 45 67",
        "nb.v.email": "Email manzilni to'g'ri kiriting: ism@misol.uz",
        "nb.v.date": "Sanani {format} ko'rinishida kiriting.",
        "nb.v.url": "To'g'ri havola kiriting (https://...).",
        "nb.v.choice": "Quyidagilardan birini tanlang: {choices}",
        "nb.v.photo": "Iltimos, rasm yuboring.",
        "nb.v.text": "Iltimos, matn yuboring.",
        "nb.v.regex": "Format noto'g'ri.",
        "nb.v.location": "Iltimos, joylashuvni yuboring.",
        "nb.v.file": "Iltimos, fayl yuboring.",
    },
    "ru": {
        "nb.yes": "✅ Да",
        "nb.no": "❌ Нет",
        "nb.done": "✔️ Готово",
        "nb.cancel": "🚫 Отмена",
        "nb.cancelled": "Отменено.",
        "nb.back": "⬅️ Назад",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Время ожидания ответа истекло.",
        "nb.invalid": "❗️ Неверное значение, попробуйте ещё раз.",
        "nb.too_many_tries": "Слишком много попыток. Начните заново позже.",
        "nb.expired": "⌛️ Срок действия кнопки истёк.",
        "nb.not_yours": "🙅 Эта кнопка не для вас.",
        "nb.used": "Эта кнопка уже использована.",
        "nb.throttled": "⏳ Подождите немного...",
        "nb.maintenance": "🛠 В боте ведутся технические работы. Загляните чуть позже.",
        "nb.subscribe": "Чтобы пользоваться ботом, подпишитесь на каналы:",
        "nb.check": "✅ Проверить",
        "nb.not_subscribed": "❗️ Вы ещё не подписались на все каналы.",
        "nb.error": "😔 Произошла ошибка. Попробуйте чуть позже.",
        "nb.send_phone": "📞 Отправить номер",
        "nb.send_location": "📍 Отправить геолокацию",
        "nb.choose_hint": "Выберите варианты и нажмите «Готово».",
        "nb.page": "Страница {page}/{pages}",
        "nb.empty": "Ничего не найдено.",
        "nb.captcha": "{mention}, добро пожаловать! Подтвердите, что вы не робот ({seconds} сек).",
        "nb.captcha_button": "🤖 Я не робот",
        "nb.captcha_ok": "✅ Спасибо, теперь вы можете писать.",
        "nb.warned": "⚠️ {mention} получил предупреждение ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} исключён после {limit} предупреждений.",
        "nb.support_sent": "✅ Сообщение отправлено. Скоро ответим.",
        "nb.v.int": "Введите целое число.",
        "nb.v.float": "Введите число (например, 12.5).",
        "nb.v.min": "Значение должно быть не меньше {min}.",
        "nb.v.max": "Значение должно быть не больше {max}.",
        "nb.v.len_min": "Введите не менее {min} символов.",
        "nb.v.len_max": "Введите не более {max} символов.",
        "nb.v.phone": "Введите номер правильно: +998 90 123 45 67",
        "nb.v.email": "Введите корректный email: name@example.com",
        "nb.v.date": "Введите дату в формате {format}.",
        "nb.v.url": "Введите корректную ссылку (https://...).",
        "nb.v.choice": "Выберите один из вариантов: {choices}",
        "nb.v.photo": "Пожалуйста, отправьте фото.",
        "nb.v.text": "Пожалуйста, отправьте текст.",
        "nb.v.regex": "Неверный формат.",
        "nb.v.location": "Пожалуйста, отправьте геолокацию.",
        "nb.v.file": "Пожалуйста, отправьте файл.",
    },
    "en": {
        "nb.yes": "✅ Yes",
        "nb.no": "❌ No",
        "nb.done": "✔️ Done",
        "nb.cancel": "🚫 Cancel",
        "nb.cancelled": "Cancelled.",
        "nb.back": "⬅️ Back",
        "nb.prev": "◀️",
        "nb.next": "▶️",
        "nb.timeout": "⌛️ Time is up.",
        "nb.invalid": "❗️ Invalid value, please try again.",
        "nb.too_many_tries": "Too many attempts. Please start over later.",
        "nb.expired": "⌛️ This button has expired.",
        "nb.not_yours": "🙅 This button is not for you.",
        "nb.used": "This button was already used.",
        "nb.throttled": "⏳ Please wait a moment...",
        "nb.maintenance": "🛠 The bot is under maintenance. Please come back soon.",
        "nb.subscribe": "To use the bot, please subscribe to these channels:",
        "nb.check": "✅ Check",
        "nb.not_subscribed": "❗️ You haven't joined all channels yet.",
        "nb.error": "😔 Something went wrong. Please try again later.",
        "nb.send_phone": "📞 Share phone number",
        "nb.send_location": "📍 Share location",
        "nb.choose_hint": "Pick the options and press “Done”.",
        "nb.page": "Page {page}/{pages}",
        "nb.empty": "Nothing found.",
        "nb.captcha": "{mention}, welcome! Please confirm you are human ({seconds} seconds).",
        "nb.captcha_button": "🤖 I'm not a robot",
        "nb.captcha_ok": "✅ Thanks, you can chat now.",
        "nb.warned": "⚠️ {mention} was warned ({count}/{limit}). {reason}",
        "nb.banned_after_warns": "⛔️ {mention} was removed after {limit} warnings.",
        "nb.support_sent": "✅ Message sent. We'll reply soon.",
        "nb.v.int": "Please enter a whole number.",
        "nb.v.float": "Please enter a number (e.g. 12.5).",
        "nb.v.min": "The value must be at least {min}.",
        "nb.v.max": "The value must be at most {max}.",
        "nb.v.len_min": "Enter at least {min} characters.",
        "nb.v.len_max": "Enter at most {max} characters.",
        "nb.v.phone": "Please enter a valid phone: +998 90 123 45 67",
        "nb.v.email": "Please enter a valid email: name@example.com",
        "nb.v.date": "Please enter the date as {format}.",
        "nb.v.url": "Please enter a valid link (https://...).",
        "nb.v.choice": "Please choose one of: {choices}",
        "nb.v.photo": "Please send a photo.",
        "nb.v.text": "Please send text.",
        "nb.v.regex": "Wrong format.",
        "nb.v.location": "Please send a location.",
        "nb.v.file": "Please send a file.",
    },
}


class I18n:
    """Loads ``<folder>/<lang>.json`` (or ``.toml``) files. Missing keys fall back to the default language, then to the key itself."""

    def __init__(self, folder: str | Path | None = "locales", default: str = "uz", languages: tuple[str, ...] | None = None):
        self.default = default
        self.texts: dict[str, dict[str, str]] = {k: dict(v) for k, v in BUILTIN.items()}
        self.folder = Path(folder) if folder else None
        if self.folder and self.folder.is_dir():
            self.load(self.folder)
        self.languages = languages or tuple(sorted(self.texts))

    def load(self, folder: str | Path) -> None:
        for path in sorted(Path(folder).iterdir()):
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".toml":
                import tomllib

                data = tomllib.loads(path.read_text(encoding="utf-8"))
            else:
                continue
            self.add(path.stem, data)
        log.debug("Tarjimalar yuklandi: %s", sorted(self.texts))

    def add(self, lang: str, data: dict[str, Any], prefix: str = "") -> None:
        bucket = self.texts.setdefault(lang, {})
        for k, v in data.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                self.add(lang, v, key + ".")
            else:
                bucket[key] = str(v)

    def resolve(self, code: str | None) -> str:
        """Map a Telegram ``language_code`` (``"ru-RU"``) to a loaded language."""
        if not code:
            return self.default
        code = code.lower().split("-")[0]
        if code in self.texts:
            return code
        return self.default

    def t(self, key: str, lang: str | None = None, /, **kwargs: Any) -> str:
        lang = lang or self.default
        text = self.texts.get(lang, {}).get(key)
        if text is None:
            text = self.texts.get(self.default, {}).get(key)
        if text is None:
            text = self.texts.get("en", {}).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text
