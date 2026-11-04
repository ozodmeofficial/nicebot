"""Build the nicebot docs site: one self-contained HTML page, three languages.

    python docs/src/build.py   → docs/index.html (GitHub Pages), site/index.html (surge) and docs/artifact.html

Sources:
    content_<lang>.py   page texts (Markdown-like) per language
    landing.py          landing page, section overviews and one-line page summaries
    snippets.py         code samples shared by every language
    chats.py            chat previews shown next to code ("what the user sees")
    comments.py         translations of code comments
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

import comments  # noqa: E402
import content_en  # noqa: E402
import content_ru  # noqa: E402
import content_uz  # noqa: E402
import landing  # noqa: E402
from chats import CHATS  # noqa: E402
from snippets import CODE  # noqa: E402

LANGS = {"uz": content_uz, "ru": content_ru, "en": content_en}
NAV = [
    ("start", ["intro", "install", "first-bot", "concepts"]),
    ("basics", ["handlers", "ctx", "formatting"]),
    ("ui", ["buttons", "keyboards", "conversations", "validators", "state", "menus"]),
    ("data", ["database", "users", "i18n"]),
    ("business", ["admin", "broadcast", "payments", "groups"]),
    ("advanced", ["middleware", "miniapp", "scheduler", "deploy", "testing"]),
    ("reference", ["features", "api"]),
]
HLJS_LANG = {"python": "python", "bash": "bash", "json": "json", "html": "xml", "docker": "dockerfile", "text": "plaintext"}
LABEL = {"python": "Python", "bash": "Terminal", "json": "JSON", "html": "HTML", "docker": "Dockerfile", "text": "Text"}
FILENAME = {"hello": "bot.py", "nicebot_same": "bot.py", "aiogram": "bot.py", "testing": "test_bot.py", "docker": "Dockerfile", "env": ".env", "tree": "mybot/"}


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


ICON_NOTE = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.2"/></svg>'


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
            out.append(f'<aside class="note">{ICON_NOTE}<p>{inline(" ".join(buf))}</p></aside>')
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
    data: dict = {"nav": NAV, "langs": {}, "groupIcon": landing.GROUP_ICON, "featureIcon": landing.FEATURE_ICON,
                  "featureCode": landing.FEATURE_CODE, "pathPages": landing.PATH_PAGES}
    for lang, mod in LANGS.items():
        extra = fill(landing.L[lang], values)
        pages = {}
        for _, ids in NAV:
            for pid in ids:
                title, body = mod.PAGES[pid]
                rendered, toc = render(body, lang, mod)
                text = text_of(rendered)
                words = len(text.split()) + sum(nonblank(c) for c in re.findall(r"<pre>(.*?)</pre>", rendered, flags=re.S)) * 3
                pages[pid] = {
                    "title": title, "desc": extra["DESC"][pid], "html": rendered, "toc": toc,
                    "text": text[:5000], "min": max(1, round(words / 180)),
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
