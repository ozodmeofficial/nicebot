"""Chat previews shown next to code samples ("code → what the user sees").

Each entry matches a snippet in snippets.py with the same name. The strings are the
ones the code sends, so they stay the same in every language of the docs.

    {"u": text}                user message
    {"b": text, "kb": rows}    bot message, optional inline keyboard (list of rows)
    {"click": label}           the user taps a button
    {"edit": True, ...}        the bot edits its previous message in place
"""

CHATS: dict[str, list[dict]] = {}

CHATS["hello"] = [
    {"u": "/start"},
    {"b": "Salom, Ali!"},
]

CHATS["nicebot_same"] = [
    {"u": "/start"},
    {"b": "Ismingiz?"},
    {"u": "Ali"},
    {"b": "Yoshingiz?"},
    {"u": "yigirma"},
    {"b": "Butun son kiriting."},
    {"u": "20"},
    {"b": "Ali, 20 yosh"},
]

CHATS["buttons"] = [
    {"u": "/shop"},
    {"b": "Mahsulot: Kitob — 50 000 so'm", "kb": [["🛒 Sotib olish"], ["🌐 Sayt ↗", "📋 Promo"], ["📱 Ilova"]]},
    {"click": "🛒 Sotib olish"},
    {"b": "✅ Sotib olindi", "edit": True},
]

CHATS["ask"] = [
    {"u": "/register"},
    {"b": "Ismingiz?"},
    {"u": "Ali"},
    {"b": "Yoshingiz?"},
    {"u": "20"},
    {"b": "Raqamingiz?"},
    {"u": "90 123 45 67"},
    {"b": "O'lcham?", "kb": [["S", "M", "L"]]},
    {"click": "M"},
    {"b": "Rahmat, Ali!"},
]

CHATS["confirm"] = [
    {"b": "Buyurtmani tasdiqlaysizmi?", "kb": [["✅ Ha", "❌ Yo'q"]]},
    {"click": "✅ Ha"},
    {"b": "✅ Qabul qilindi"},
]

CHATS["menu"] = [
    {"u": "/menu"},
    {"b": "🏠 Bosh menyu", "kb": [["🛍 Do'kon", "📞 Aloqa", "🌐 Sayt ↗"]]},
    {"click": "🛍 Do'kon"},
    {"b": "Bo'limni tanlang", "kb": [["👕 Kiyim", "📚 Kitoblar"], ["⬅️ Orqaga"]], "edit": True},
]

CHATS["toggle"] = [
    {"u": "/sozlamalar"},
    {"b": "⚙️ Sozlamalar", "kb": [["✅ Bildirishnomalar"], ["⬜️ Kechki rejim"]]},
    {"click": "⬜️ Kechki rejim"},
    {"b": "⚙️ Sozlamalar", "kb": [["✅ Bildirishnomalar"], ["✅ Kechki rejim"]], "edit": True},
]
