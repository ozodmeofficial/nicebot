"""Build the nicebot docs site: one self-contained HTML page, three languages.

    python docs/src/build.py   → docs/index.html (GitHub Pages), site/index.html (surge) and docs/artifact.html

Sources:
    content_<lang>.py   page texts (Markdown-like) per language
    landing.py          landing page, section overviews and one-line page summaries
    snippets.py         code samples shared by every language
    chats.py            chat previews shown next to code ("what the user sees")
    comments.py         translations of code comments
    pages_<lang>.py     newer pages (VS Code, media, Mini Apps) per language
    reference.py        API reference: members + translated one-liners (signatures/examples come from the library)
    template.html       layout, styles and the client-side router
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

import comments  # noqa: E402
import content_en  # noqa: E402
import content_ru  # noqa: E402
import content_uz  # noqa: E402
import landing  # noqa: E402
import pages_en  # noqa: E402
import pages_ru  # noqa: E402
import pages_uz  # noqa: E402
import reference  # noqa: E402
from chats import CHATS  # noqa: E402
from snippets import CODE  # noqa: E402

LANGS = {"uz": content_uz, "ru": content_ru, "en": content_en}
NEW_PAGES = {"uz": pages_uz.PAGES, "ru": pages_ru.PAGES, "en": pages_en.PAGES}
REF = reference.parse()
NAV = [
    ("start", ["intro", "install", "first-bot", "concepts", "vscode"]),
    ("basics", ["handlers", "ctx", "formatting"]),
    ("ui", ["buttons", "keyboards", "conversations", "validators", "state", "menus"]),
    ("media", ["media-receive", "media-download", "media-send", "media-albums"]),
    ("data", ["database", "users", "i18n"]),
    ("business", ["admin", "broadcast", "payments", "groups"]),
    ("miniapp", ["miniapp", "miniapp-open", "miniapp-backend", "miniapp-frontend", "miniapp-dev", "miniapp-deploy", "miniapp-example"]),
    ("advanced", ["middleware", "scheduler", "deploy", "testing"]),
    ("reference", ["features", "ref-ctx", "ref-bot", "ref-ui", "ref-media", "ref-webapp", "ref-testing", "api"]),
]
HLJS_LANG = {"python": "python", "bash": "bash", "json": "json", "html": "xml", "docker": "dockerfile", "text": "plaintext", "css": "css", "js": "javascript"}
LABEL = {"python": "Python", "bash": "Terminal", "json": "JSON", "html": "HTML", "docker": "Dockerfile", "text": "Text", "css": "CSS", "js": "JavaScript"}
FILENAME = {"hello": "bot.py", "nicebot_same": "bot.py", "aiogram": "bot.py", "testing": "test_bot.py", "docker": "Dockerfile", "env": ".env", "tree": "mybot/",
            "miniapp_quick_py": "bot.py", "miniapp_quick_html": "webapp/index.html", "miniapp_shop_py": "bot.py", "miniapp_shop_html": "webapp/index.html",
            "vscode_settings": ".vscode/settings.json", "miniapp_caddy": "Caddyfile", "miniapp_tree": "mybot/", "miniapp_js_theme": "style.css",
            "miniapp_test": "test_bot.py", "miniapp_log": "Terminal"}


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def attr(s: str) -> str:
    return html.escape(s, quote=True)


def slug(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s).lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.U)
    return re.sub(r"[\s_]+", "-", s).strip("-")[:60] or "s"


def nonblank(code: str) -> int:
    return sum(1 for ln in code.splitlines() if ln.strip())


def translate_code(code: str, lang: str) -> str:
    if lang == "uz":
        return code
    tr = comments.TR[lang]

    def sub(m: re.Match) -> str:
        text = m.group(2)
        return m.group(1) + tr.get(text, text)

    return re.sub(r"((?:#|//) )(.+)$", sub, code, flags=re.M)


def code_block(code: str, lang: str, label: str = "", cls_extra: str = "") -> str:
    cls = HLJS_LANG.get(lang, lang)
    name = label or LABEL.get(lang, lang)
    return (
        f'<figure class="code{" " + cls_extra if cls_extra else ""}"><figcaption><span class="code-lang">{esc(name)}</span>'
        f'<button class="copy" type="button" data-copy aria-label="Copy">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6.5A2.5 2.5 0 0 0 13.5 4h-7A2.5 2.5 0 0 0 4 6.5v7A2.5 2.5 0 0 0 6.5 16H8"/></svg>'
        f'<span data-t="copy"></span></button></figcaption>'
        f'<pre><code class="language-{cls}">{esc(code)}</code></pre></figure>'
    )


def chat_html(name: str) -> str:
    """Render a Telegram-like chat preview. Strings come from the code, so they need no translation."""
    items = []
    for i, m in enumerate(CHATS[name]):
        style = f' style="--i:{i}"'
        if "u" in m:
            items.append(f'<div class="msg me"{style}><p>{esc(m["u"])}</p></div>')
        elif "click" in m:
            items.append(f'<div class="tap"{style}><span>👆 {esc(m["click"])}</span></div>')
        else:
            kb = ""
            if m.get("kb"):
                rows = "".join('<div class="kb-row">' + "".join(f"<span>{esc(b)}</span>" for b in row) + "</div>" for row in m["kb"])
                kb = f'<div class="kb">{rows}</div>'
            edited = ' <i class="edited" data-t="edited"></i>' if m.get("edit") else ""
            items.append(f'<div class="msg bot"{style}><p>{esc(m["b"])}{edited}</p>{kb}</div>')
    return (
        '<!--chat--><div class="chat" data-chat>'
        '<div class="chat-head"><span class="chat-ava" aria-hidden="true">nb</span>'
        '<div class="chat-who"><b>nicebot</b><small data-t="bot"></small></div>'
        '<button class="chat-replay" type="button" data-replay data-t-title="replay">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4.5h4.5"/></svg></button></div>'
        f'<div class="chat-body">{"".join(items)}</div></div><!--/chat-->'
    )


def demo_html(name: str, lang: str) -> str:
    label = FILENAME.get(name, "bot.py")
    code = translate_code(CODE[name], lang)
    wide = max(len(ln) for ln in code.splitlines()) > 58  # too wide to sit next to the chat
    return (
        f'<div class="demo{" stack" if wide else ""}">'
        f'<div class="demo-code">{code_block(code, "python", label)}</div>'
        f'<div class="demo-chat"><div class="demo-label"><span class="dot"></span><span data-t="result"></span></div>{chat_html(name)}</div>'
        "</div>"
    )


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{esc(p[1:-1])}</code>")
            continue
        p = esc(p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"\[([^\]]+)\]\((#[\w-]+)\)", r'<a href="\2">\1</a>', p)
        p = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', p)
        out.append(p)
    return "".join(out)


def features_html(mod) -> str:
    n = 0
    blocks = []
    for title, items in mod.FEATURE_GROUPS:
        lis = []
        for name, desc in items:
            n += 1
            lis.append(f'<li><span class="fnum">{n:02d}</span><div><code>{esc(name)}</code><p>{esc(desc)}</p></div></li>')
        blocks.append(
            f'<section class="fgroup"><h2 id="{slug(title)}">{esc(title)} <span class="fcount">{len(items)}</span></h2>'
            f'<ol class="flist">{"".join(lis)}</ol></section>'
        )
    return "".join(blocks)


ALERT_ICON = {
    "note": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></svg>',
    "tip": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5c-2.363 0-4 1.69-4 3.75 0 .984.424 1.625.984 2.304l.214.253c.223.264.47.556.673.848.284.411.537.896.621 1.49a.75.75 0 0 1-1.484.211c-.04-.282-.163-.547-.37-.847a8.456 8.456 0 0 0-.542-.68c-.084-.1-.173-.205-.268-.32C3.201 7.75 2.5 6.766 2.5 5.25 2.5 2.31 4.863 0 8 0s5.5 2.31 5.5 5.25c0 1.516-.701 2.5-1.328 3.259-.095.115-.184.22-.268.319-.207.245-.383.453-.541.681-.208.3-.33.565-.37.847a.751.751 0 0 1-1.485-.212c.084-.593.337-1.078.621-1.489.203-.292.45-.584.673-.848.075-.088.147-.173.213-.253.561-.679.985-1.32.985-2.304 0-2.06-1.637-3.75-4-3.75ZM5.75 12h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5ZM6 15.25a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5a.75.75 0 0 1-.75-.75Z"/></svg>',
    "warning": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/></svg>',
}
ALERT_TITLE = {"note": {"uz": "Eslatma", "ru": "Примечание", "en": "Note"}, "tip": {"uz": "Maslahat", "ru": "Совет", "en": "Tip"},
               "warning": {"uz": "Diqqat", "ru": "Внимание", "en": "Warning"}}


def render(md: str, lang: str, mod) -> tuple[str, list[tuple[str, str]]]:
    lines = md.strip("\n").split("\n")
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    seen: set[str] = set()
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush()
            i += 1
            continue
        m = re.fullmatch(r"\{code:([\w_]+)(?::(\w+))?\}", s)
        if m:
            flush()
            name, lng = m.group(1), m.group(2) or "python"
            out.append(code_block(translate_code(CODE[name], lang), lng, FILENAME.get(name, "")))
            i += 1
            continue
        m = re.fullmatch(r"\{demo:([\w_]+)\}", s)
        if m:
            flush()
            out.append(demo_html(m.group(1), lang))
            i += 1
            continue
        if s == "{features}":
            flush()
            out.append(features_html(mod))
            for title, _ in mod.FEATURE_GROUPS:
                toc.append((slug(title), title))
            i += 1
            continue
        if s.startswith("```"):
            flush()
            lng = s[3:] or "text"
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(code_block("\n".join(buf), lng))
            i = j + 1
            continue
        if s.startswith("## ") or s.startswith("### "):
            flush()
            level = 2 if s.startswith("## ") else 3
            text = s[level + 1:]
            hid = base = slug(text)
            k = 2
            while hid in seen:
                hid = f"{base}-{k}"
                k += 1
            seen.add(hid)
            if level == 2:
                toc.append((hid, re.sub(r"`", "", text)))
            out.append(f'<h{level} id="{hid}">{inline(text)}<a class="anchor" href="#" data-anchor="{hid}" aria-hidden="true" tabindex="-1">#</a></h{level}>')
            i += 1
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            header, body = rows[0], rows[2:]
            th = "".join(f"<th>{inline(c)}</th>" for c in header)
            has_head = any(c for c in header)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="table"><table>{"<thead><tr>" + th + "</tr></thead>" if has_head else ""}<tbody>{trs}</tbody></table></div>')
            continue
        if re.match(r"^(- |\d+\. )", s):
            flush()
            ordered = bool(re.match(r"^\d+\. ", s))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i].strip()):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i].strip()))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(it)}</li>" for it in items) + f"</{tag}>")
            continue
        if s.startswith("> "):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                buf.append(lines[i].strip()[2:])
                i += 1
            kind = "note"
            m = re.fullmatch(r"\[!(NOTE|TIP|WARNING)\]", buf[0].strip()) if buf else None
            if m:
                kind = m.group(1).lower()
                buf = buf[1:]
            title = ALERT_TITLE[kind][lang]
            out.append(f'<aside class="alert alert-{kind}"><p class="alert-title">{ALERT_ICON[kind]}{title}</p><p>{inline(" ".join(buf))}</p></aside>')
            continue
        para.append(s)
        i += 1
    flush()
    return "".join(out), toc


def text_of(h: str) -> str:
    t = re.sub(r"<pre>.*?</pre>", " ", h, flags=re.S)
    t = re.sub(r"<!--chat-->.*?<!--/chat-->", " ", t, flags=re.S)
    t = re.sub(r'<a class="anchor"[^>]*>#</a>', "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


# ----------------------------------------------------------------------------- API reference
def _resolve(spec: str):
    import importlib

    mod_name, _, path = spec.partition(":")
    obj = importlib.import_module(mod_name)
    owner = None
    for part in path.split("."):
        owner, obj = obj, getattr(obj, part) if not isinstance(obj, type) else obj.__dict__.get(part, getattr(obj, part, None))
    return owner, obj


def _example(doc: str) -> str:
    import textwrap

    if not doc or "Example::" not in doc:
        return ""
    block = doc.split("Example::", 1)[1]
    lines = block.split("\n")[1:]
    out = []
    for ln in lines:
        if ln.strip() and not ln.startswith("    ") and not ln.startswith("\t") and out:
            break
        out.append(ln)
    return textwrap.dedent("\n".join(out)).strip("\n")


def _clean_ann(a: str) -> str:
    a = a.replace("'", "").replace('"', "")
    a = re.sub(r"\bT\.", "", a)
    a = re.sub(r"\b(?:nicebot\.)?(?:types|context|media|orm\.builtin|server)\.", "", a)
    a = a.replace("Unpack[SendOptions]", "SendOptions").replace("Unpack[MediaOptions]", "MediaOptions").replace("Unpack[HandlerOptions]", "HandlerOptions")
    return a


def _signature(func, drop_self: bool) -> tuple[str, str]:
    import inspect

    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return "(…)", ""
    parts, star = [], False
    params = list(sig.parameters.values())
    if drop_self and params and params[0].name in ("self", "cls"):
        params = params[1:]
    for p in params:
        if p.kind == p.VAR_POSITIONAL:
            parts.append(f"*{p.name}")
            star = True
            continue
        if p.kind == p.VAR_KEYWORD:
            ann = _clean_ann(str(p.annotation)) if p.annotation is not p.empty else ""
            parts.append("**options" if ann.endswith("Options") else f"**{p.name}")
            continue
        if p.kind == p.KEYWORD_ONLY and not star:
            parts.append("*")
            star = True
        if p.kind == p.POSITIONAL_ONLY:
            pass
        txt = p.name
        if p.default is not p.empty:
            d = p.default
            txt += "=…" if d is ... else f"={d!r}" if isinstance(d, (str, int, float, bool, type(None))) and len(repr(d)) < 24 else "=…"
        parts.append(txt)
    ret = ""
    if sig.return_annotation is not sig.empty:
        ret = _clean_ann(str(sig.return_annotation))
        if ret in ("None", "Any"):
            ret = ""
    return "(" + ", ".join(parts) + ")", ret


def _member_html(prefix: str, name: str, obj, owner, raw: bool, desc: str, lang: str) -> str:
    import inspect

    anchor = slug(name.split(":")[-1].replace(".", "-"))
    if raw:
        head = f'<code class="sig">{esc(name)}</code>'
        return f'<div class="ref" id="{anchor}"><h3>{head}</h3><p>{inline(desc)}</p></div>'
    display = name.split(":")[-1]
    if display.startswith("_F"):
        display = "F" + display[2:]
    doc = ""
    sig, ret, kind = "", "", "attr"
    is_async = False
    target = obj
    if isinstance(obj, property):
        doc = obj.fget.__doc__ or ""
        kind = "prop"
        r = getattr(obj.fget, "__annotations__", {}).get("return")
        ret = _clean_ann(str(r)) if r is not None else ""
    elif isinstance(obj, (staticmethod, classmethod)):
        target = obj.__func__
        kind = "func"
    if kind == "attr" and callable(target) and not isinstance(target, type):
        kind = "func"
    if isinstance(target, type):
        kind = "class"
        doc = target.__doc__ or ""
        sig, _ = _signature(target.__init__, True) if "__init__" in target.__dict__ else ("", "")
    elif kind == "func":
        doc = target.__doc__ or ""
        is_async = inspect.iscoroutinefunction(target)
        sig, ret = _signature(target, drop_self=isinstance(owner, type))
    if ":" in name or kind == "class":
        full = display if kind == "class" or "." not in display or display.startswith("F") else display
        if kind != "class" and "." in display and not display.startswith("F"):
            cls, _, meth = display.partition(".")
            inst = {"TestUser": "user", "SentMessage": "msg", "Menu": "menu"}.get(cls, cls)
            full = f"{inst}.{meth}"
    else:
        full = f"{prefix}.{display}"
    if ret.startswith(("Callable[[F]", "Callable[[Callable")) or display in ("deep_link",):
        text = "@" + full + sig            # a decorator
        badge_override = "decorator"
    else:
        text = ("await " if is_async else "") + full + sig + (f" → {ret}" if ret else "")
        badge_override = ""
    badge = badge_override or {"prop": "property", "func": "async" if is_async else "method", "class": "class", "attr": "attribute"}[kind]
    ex = _example(doc)
    ex_html = code_block(ex, "python", "Example") if ex else ""
    return (f'<div class="ref" id="{anchor}"><h3><code class="sig">{esc(text)}</code><span class="badge badge-{badge}">{badge}</span></h3>'
            f'<p>{inline(desc)}</p>{ex_html}</div>')


def render_reference(pid: str, lang: str) -> tuple[str, list[tuple[str, str]]]:
    page = REF[pid]
    owner_cls = _resolve(page["target"])[1]
    out = [f"<p>{inline(reference.INTRO[pid][lang])}</p>"]
    toc = []
    for titles, members in page["groups"]:
        gid = slug(titles["en"])
        toc.append((gid, titles[lang]))
        out.append(f'<h2 id="{gid}">{esc(titles[lang])}<a class="anchor" href="#" data-anchor="{gid}" aria-hidden="true" tabindex="-1">#</a></h2>')
        for name, desc, raw in members:
            if raw:
                out.append(_member_html(page["prefix"], name, None, None, True, desc[lang], lang))
                continue
            if ":" in name:
                owner, obj = _resolve(name)
            else:
                owner = owner_cls
                obj = None
                for klass in owner_cls.__mro__:
                    if name in klass.__dict__:
                        obj = klass.__dict__[name]
                        break
                if obj is None:
                    obj = getattr(owner_cls, name, None)
            out.append(_member_html(page["prefix"], name, obj, owner, False, desc[lang], lang))
    return "".join(out), toc


def check_reference() -> list[str]:
    """Public members of the documented classes that are missing from reference.py (keeps the docs complete)."""
    import inspect

    from nicebot.api import BotAPI

    missing = []
    for pid, page in REF.items():
        if pid == "ref-ui":  # documents several classes explicitly; Button's options live in its docstring
            continue
        cls = _resolve(page["target"])[1]
        listed = {n for _, members in page["groups"] for n, _, raw in members if not raw and ":" not in n}
        names = set()
        for klass in cls.__mro__:
            if klass in (object, BotAPI) or klass.__module__.startswith(("builtins", "typing")):
                continue
            names |= {n for n in klass.__dict__ if not n.startswith("_")}
        if pid == "ref-ctx" or pid == "ref-media" or pid == "ref-webapp" or pid == "ref-testing":
            try:
                src = inspect.getsource(cls.__init__)
                names |= set(re.findall(r"self\.([a-z][a-z_]*)\s*[:=]", src))
            except (TypeError, OSError):
                pass
        ignore = {"defaults", "handlers", "error_handlers", "routers", "parent", "name", "token", "client", "admins", "parse_mode", "i18n",
                  "track_users", "analytics", "admin_panel", "required_channels", "support_chat", "captcha", "error_message", "notify_errors",
                  "ask_timeout", "state_ttl", "tz", "config", "test_server", "cors", "debug", "dev_user", "db", "storage", "user_model", "me",
                  "username", "middlewares", "started_at", "timeout", "member_status", "bot_username", "chat_members", "bot", "s", "id",
                  "first_name", "lang", "chat_id", "chat_type", "data", "method", "message_id", "markup", "reply_markup_raw", "tg"}
        for n in sorted(names - listed - ignore):
            missing.append(f"{pid}: {n}")
    return missing


def fill(obj, values: dict):
    """Replace {name} placeholders in every string of a nested structure."""
    if isinstance(obj, str):
        for k, v in values.items():
            obj = obj.replace("{" + k + "}", str(v))
        return obj
    if isinstance(obj, list):
        return [fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v, values) for k, v in obj.items()}
    return obj


def build_data() -> dict:
    values = {"hello": nonblank(CODE["hello"])}
    from nicebot import __version__

    data: dict = {"nav": NAV, "langs": {}, "version": __version__, "groupIcon": landing.GROUP_ICON, "featureIcon": landing.FEATURE_ICON,
                  "featureCode": landing.FEATURE_CODE, "pathPages": landing.PATH_PAGES}
    for lang, mod in LANGS.items():
        extra = fill(landing.L[lang], values)
        pages = {}
        all_pages = {**mod.PAGES, **NEW_PAGES[lang]}
        for _, ids in NAV:
            for pid in ids:
                if pid in REF:
                    title = reference.TITLES[pid][lang]
                    rendered, toc = render_reference(pid, lang)
                    desc = reference.DESC[pid][lang]
                else:
                    title, body = all_pages[pid]
                    rendered, toc = render(body, lang, mod)
                    desc = extra["DESC"][pid]
                text = text_of(rendered)
                words = len(text.split()) + sum(nonblank(c) for c in re.findall(r"<pre>(.*?)</pre>", rendered, flags=re.S)) * 3
                pages[pid] = {
                    "title": title, "desc": desc, "html": rendered, "toc": toc,
                    "text": text[:12000], "min": max(1, round(words / 180)),
                }
        ui = {**mod.UI, **extra["UI"]}
        data["langs"][lang] = {
            "ui": ui, "groups": mod.GROUPS, "groupDesc": extra["GROUPS"], "pages": pages, "home": extra["HOME"],
        }
    return data


def home_static() -> dict:
    a = nonblank(CODE["aiogram"])
    n = nonblank(CODE["nicebot_same"])
    return {
        "aiogram_lines": a,
        "nicebot_lines": n,
        "hello_lines": nonblank(CODE["hello"]),
        "hero_code": code_block(CODE["nicebot_same"], "python", "bot.py"),
        "hero_chat": chat_html("nicebot_same"),
        "hello": code_block(CODE["hello"], "python", "bot.py"),
        "hello_chat": chat_html("hello"),
        "aiogram": code_block(CODE["aiogram"], "python", "aiogram · bot.py"),
        "nicebot": code_block(CODE["nicebot_same"], "python", "nicebot · bot.py"),
    }


def main() -> None:
    missing = check_reference()
    if missing:
        raise SystemExit("Undocumented members (add them to docs/src/reference.py):\n  " + "\n  ".join(missing))
    data = build_data()
    static = home_static()
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    page = (
        tpl.replace("/*__DATA__*/", "window.NB_DATA = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ";")
        .replace("/*__STATIC__*/", "window.NB_STATIC = " + json.dumps(static, ensure_ascii=False).replace("</", "<\\/") + ";")
    )
    out = HERE.parent
    (out / "artifact.html").write_text(page, encoding="utf-8")
    standalone = (
        "<!doctype html>\n<html lang=\"uz\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<meta name=\"description\" content=\"nicebot — Telegram botlar uchun Python kutubxonasi. Hujjatlar: o'zbek, rus, ingliz tillarida.\">\n"
        "<meta property=\"og:title\" content=\"nicebot — Telegram botlar uchun Python kutubxonasi\">\n"
        "<meta property=\"og:description\" content=\"Kam kod. Hamma narsa ichida. Suhbatlar, tugmalar, baza va admin panel bitta importda.\">\n"
        + page
        + "\n</html>\n"
    )
    standalone = standalone.replace("<!--BODY-->", "</head>\n<body>", 1).replace("<!--/BODY-->", "</body>", 1)
    (out / "index.html").write_text(standalone, encoding="utf-8")
    site = ROOT / "site"
    if site.is_dir():
        (site / "index.html").write_text(standalone, encoding="utf-8")
    print(f"ok: {len(standalone) // 1024} KB, pages={len(data['langs']['uz']['pages'])}")


if __name__ == "__main__":
    main()
