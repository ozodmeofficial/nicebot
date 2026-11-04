"""Generate nicebot/types.py and nicebot/api.py from the Telegram Bot API spec.

Spec source: https://github.com/PaulSonOfLars/telegram-bot-api-spec (api.json)
Run:  python tools/gen_api.py
"""
from __future__ import annotations

import json
import keyword
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "tools" / "api.json").read_text(encoding="utf-8"))
TYPES = SPEC["types"]
METHODS = SPEC["methods"]

PRIMS = {"Integer": "int", "String": "str", "Boolean": "bool", "Float": "float", "True": "bool"}
TAG_RE = [
    re.compile(r"always [“\"]([^”\"]+)[”\"]"),
    re.compile(r"must be ([a-z_0-9]+)\b"),
]

# ---------------------------------------------------------------- unions
UNIONS: dict[str, list[str]] = {}
TAGS: dict[str, tuple[str, str]] = {}  # struct -> (tag_field, tag_value)
ANY_UNIONS: set[str] = set()

for name, t in TYPES.items():
    subs = t.get("subtypes")
    if not subs:
        continue
    if not all(s in TYPES and not TYPES[s].get("subtypes") for s in subs):
        ANY_UNIONS.add(name)
        continue
    common = None
    values: dict[str, dict[str, str]] = {}
    for s in subs:
        found = {}
        for f in TYPES[s].get("fields", []):
            for rx in TAG_RE:
                m = rx.search(f["description"])
                if m:
                    found[f["name"]] = m.group(1)
                    break
        values[s] = found
        common = set(found) if common is None else common & set(found)
    if not common:
        ANY_UNIONS.add(name)
        continue
    field = sorted(common)[0]
    ok = True
    for s in subs:
        prev = TAGS.get(s)
        if prev and prev[0] != field:
            ok = False
    if not ok:
        ANY_UNIONS.add(name)
        continue
    for s in subs:
        TAGS[s] = (field, values[s][field])
    UNIONS[name] = subs

# MaybeInaccessibleMessage has no tag: InaccessibleMessage is a Message with date == 0
SPECIAL = {"MaybeInaccessibleMessage": "Message"}
ANY_UNIONS -= set(SPECIAL)


def py_type(tg: str, *, input_side: bool = False) -> str:
    if tg.startswith("Array of "):
        return f"list[{py_type(tg[9:], input_side=input_side)}]"
    if tg in PRIMS:
        return PRIMS[tg]
    if tg == "InputFile":
        return "InputFile"
    if tg in SPECIAL:
        return SPECIAL[tg]
    if tg in ANY_UNIONS:
        return "Any"
    return tg


def join(types: list[str], **kw) -> str:
    out: list[str] = []
    for t in types:
        p = py_type(t, **kw)
        if p not in out:
            out.append(p)
    if "Any" in out:
        return "Any"
    return " | ".join(out)


def first_line(desc) -> str:
    if isinstance(desc, list):
        desc = desc[0] if desc else ""
    desc = desc.replace('"""', "'").replace("\\", "/")
    return desc.split(". ")[0].strip().rstrip(".") + "."


def safe(name: str) -> str:
    return name + "_" if keyword.iskeyword(name) else name


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()



# ---------------------------------------------------------------- docs: arguments and examples
_ID_NAMES = {"chat_id", "user_id", "message_id", "from_chat_id", "message_thread_id", "inline_message_id", "callback_query_id",
             "inline_query_id", "file_id", "sticker", "custom_emoji_id", "business_connection_id", "shipping_query_id",
             "pre_checkout_query_id", "web_app_query_id", "telegram_payment_charge_id", "gift_id", "owned_gift_id", "story_id"}
_FILE_SAMPLE = {"photo": '"photo.jpg"', "video": '"video.mp4"', "audio": '"song.mp3"', "document": '"report.pdf"', "voice": '"voice.ogg"',
                "animation": '"funny.gif"', "video_note": '"circle.mp4"', "sticker": '"sticker.webp"', "thumbnail": '"thumb.jpg"',
                "png_sticker": '"sticker.png"', "certificate": '"cert.pem"'}


def wrap(text: str, width: int = 100, indent: str = "") -> list[str]:
    import textwrap as _tw

    return _tw.wrap(text, width=width, initial_indent=indent, subsequent_indent=indent + "    ") or [indent]


def field_doc(desc) -> str:
    if isinstance(desc, list):
        desc = " ".join(desc)
    desc = (desc or "").replace('"""', "'").replace("\\", "/").strip()
    if desc.startswith("Optional. "):
        desc = desc[len("Optional. "):]
    first = desc.split(". ")[0].strip().rstrip(".")
    return first + "." if first else ""


def sample(f) -> str:
    name, types = f["name"], f["types"]
    if name in _ID_NAMES:
        return name
    if name in _FILE_SAMPLE and ("InputFile" in types or "String" in types):
        return _FILE_SAMPLE[name]
    t = types[0]
    if t.startswith("Array of "):
        inner = t[len("Array of "):]
        if inner.startswith("Array of "):
            return "[[...]]"
        if inner in ("String",):
            return '["..."]'
        if inner in ("Integer",):
            return "[1, 2]"
        return f"[{inner}(...)]"
    if t == "Integer":
        return {"limit": "10", "offset": "0", "duration": "60", "amount": "100", "star_count": "50"}.get(name, "1")
    if t == "Float":
        return {"latitude": "41.31", "longitude": "69.28"}.get(name, "1.0")
    if t in ("Boolean", "True"):
        return "True"
    if t == "String":
        return {"text": '"Hello!"', "caption": '"Nice photo"', "url": '"https://example.com"', "title": '"Title"',
                "description": '"Description"', "name": '"Name"', "emoji": '"🎲"', "question": '"Question?"', "payload": '"payload"',
                "currency": '"XTR"', "action": '"typing"', "language_code": '"en"', "parse_mode": '"HTML"'}.get(name, '"..."')
    if t == "InputFile":
        return '"file.bin"'
    return f"{t}(...)"


def method_doc(meth, indent: str) -> list[str]:
    out = [f'{indent}"""{first_line(meth.get("description", ""))}', ""]
    fields = meth.get("fields", [])
    if fields:
        out.append(f"{indent}Args:")
        for f in fields:
            d = field_doc(f.get("description", ""))
            label = f"{safe(f['name'])}{'' if f['required'] else ' (optional)'}: {d}"
            out.extend(wrap(label, indent=indent + "    "))
        out.append("")
    req = [f for f in fields if f["required"]]
    call = ", ".join(sample(f) for f in req)
    ret = meth["returns"][0] if meth.get("returns") else "bool"
    var = "msg" if ret == "Message" else "result"
    out.append(f"{indent}Example::")
    out.append("")
    out.append(f"{indent}    {var} = await bot.{snake(meth['name'])}({call})")
    out.append("")
    out.append(f"{indent}{meth['href']}")
    out.append(f'{indent}"""')
    return out


def type_doc(name, t, fields, indent: str) -> list[str]:
    out = [f'{indent}"""{first_line(t.get("description", ""))}', ""]
    if fields:
        out.append(f"{indent}Attributes:")
        for f in fields:
            d = field_doc(f.get("description", ""))
            label = f"{safe(f['name'])}{'' if f['required'] else ' (optional)'}: {d}"
            out.extend(wrap(label, indent=indent + "    "))
        out.append("")
    req = [f for f in fields if f["required"]]
    args = ", ".join(f"{safe(f['name'])}={sample(f)}" for f in req)
    out.append(f"{indent}Example::")
    out.append("")
    out.append(f"{indent}    obj = {name}({args})")
    if fields:
        out.append(f"{indent}    obj.{safe(fields[0]['name'])}")
    out.append("")
    out.append(f"{indent}{t['href']}")
    out.append(f'{indent}"""')
    return out


# ---------------------------------------------------------------- types.py
lines = [
    '"""Telegram Bot API types — AUTO-GENERATED by tools/gen_api.py. Do not edit.\n\nExample::\n\n    from nicebot import types\n\n    button = types.InlineKeyboardButton(text="Open", url="https://example.com")\n"""',
    "# fmt: off",
    "# ruff: noqa",
    "from __future__ import annotations",
    "",
    "from typing import Any, Union",
    "",
    "import msgspec",
    "",
    "from ._base import TelegramObject, InputFile",
    "",
    f'API_VERSION = "{SPEC["version"]}"',
    "",
]
all_names = ["API_VERSION", "InputFile", "TelegramObject"]

for name, t in TYPES.items():
    if t.get("subtypes"):
        continue
    opts = ", kw_only=True"
    tag = TAGS.get(name)
    if tag:
        opts += f', tag_field="{tag[0]}", tag="{tag[1]}"'
    lines.append(f"class {name}(TelegramObject{opts}):")
    fields = [f for f in t.get("fields", []) if not (tag and f["name"] == tag[0])]
    lines.extend(type_doc(name, t, fields, "    "))
    if not fields and not tag:
        lines.append("    pass")
    if tag:
        lines.append("")
        lines.append("    @property")
        lines.append(f"    def {safe(tag[0])}(self) -> str:")
        lines.append(f'        """Always ``"{tag[1]}"`` for this type."""')
        lines.append(f'        return "{tag[1]}"')
        lines.append("")
    for f in fields:
        typ = join(f["types"], input_side=name.startswith("Input"))
        fname = safe(f["name"])
        if fname == "from_":
            pass
        rename = f'name="{f["name"]}"' if fname != f["name"] else ""
        if f["required"] and f["types"] in (["Boolean"], ["True"]):
            # missing flags (e.g. new permissions on an older server) must not break decoding
            lines.append(f"    {fname}: bool = False" if not rename else f"    {fname}: bool = msgspec.field(default=False, {rename})")
        elif f["required"]:
            if rename:
                lines.append(f"    {fname}: {typ} = msgspec.field({rename})")
            else:
                lines.append(f"    {fname}: {typ}")
        else:
            if rename:
                lines.append(f"    {fname}: {typ} | None = msgspec.field(default=None, {rename})")
            else:
                lines.append(f"    {fname}: {typ} | None = None")
    lines.append("")
    all_names.append(name)

lines.append("")
for name, subs in UNIONS.items():
    lines.append(f"{name} = Union[{', '.join(subs)}]")
    all_names.append(name)
for name in sorted(ANY_UNIONS):
    lines.append(f"{name} = Any")
    all_names.append(name)
for name, target in SPECIAL.items():
    lines.append(f"{name} = {target}")
    all_names.append(name)
lines.append("")
lines.append("__all__ = [")
for n in all_names:
    lines.append(f'    "{n}",')
lines.append("]")
(ROOT / "src" / "nicebot" / "types.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- api.py
m = [
    '"""Telegram Bot API methods — AUTO-GENERATED by tools/gen_api.py. Do not edit.\n\nExample::\n\n    await bot.send_message(chat_id, "Hello!")\n"""',
    "# fmt: off",
    "# ruff: noqa",
    "from __future__ import annotations",
    "",
    "from typing import Any, TYPE_CHECKING",
    "",
    "from .types import *  # noqa: F403",
    "from .types import InputFile",
    "",
    "",
    "class BotAPI:",
    '    """Every Bot API method as a typed async Python method.',
    "",
    "    Methods have snake_case names; required arguments come first, the rest are keyword-only.",
    "",
    "    Example::",
    "",
    "        await bot.send_message(chat_id, 'Hello!')",
    "        member = await bot.get_chat_member('@my_channel', user_id)",
    '    """',
    "",
    "    async def request(self, method: str, params: dict[str, Any], returns: Any = Any) -> Any:  # pragma: no cover",
    "        raise NotImplementedError",
    "",
]
method_names = {}
for name, meth in METHODS.items():
    fields = meth.get("fields", [])
    req = [f for f in fields if f["required"]]
    opt = [f for f in fields if not f["required"]]
    args = ["self"]
    for f in req:
        args.append(f"{safe(f['name'])}: {join(f['types'], input_side=True)}")
    if opt:
        args.append("*")
        for f in opt:
            args.append(f"{safe(f['name'])}: {join(f['types'], input_side=True)} | None = None")
    ret = join(meth["returns"])
    pyname = snake(name)
    method_names[pyname] = name
    m.append(f"    async def {pyname}({', '.join(args)}) -> {ret}:")
    m.extend(method_doc(meth, "        "))
    if fields:
        items = ", ".join(f'"{f["name"]}": {safe(f["name"])}' for f in fields)
        m.append(f"        return await self.request(\"{name}\", {{{items}}}, {ret!r})")
    else:
        m.append(f"        return await self.request(\"{name}\", {{}}, {ret!r})")
    m.append("")

m.append("")
m.append(f"METHOD_COUNT = {len(METHODS)}")
(ROOT / "src" / "nicebot" / "api.py").write_text("\n".join(m) + "\n", encoding="utf-8")

print(f"types: {len(all_names)}  unions(tagged): {len(UNIONS)}  any-unions: {sorted(ANY_UNIONS)}  methods: {len(METHODS)}")
