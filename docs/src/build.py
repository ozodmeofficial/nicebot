"""Build the nicebot docs site: one self-contained HTML page, three languages.

    python docs/src/build.py        → docs/index.html (GitHub Pages) + docs/artifact.html
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import comments  # noqa: E402
import content_en  # noqa: E402
import content_ru  # noqa: E402
import content_uz  # noqa: E402
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


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def slug(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s).lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.U)
    return re.sub(r"[\s_]+", "-", s).strip("-")[:60] or "s"


def translate_code(code: str, lang: str) -> str:
    if lang == "uz":
        return code
    tr = comments.TR[lang]

    def sub(m: re.Match) -> str:
        text = m.group(2)
        return m.group(1) + tr.get(text, text)

    return re.sub(r"((?:#|//) )(.+)$", sub, code, flags=re.M)


def code_block(code: str, lang: str, label: str = "") -> str:
    cls = HLJS_LANG.get(lang, lang)
    head = f'<span class="code-lang">{esc(label or lang)}</span>'
    return (
        f'<figure class="code"><figcaption>{head}<button class="copy" type="button" data-copy>'
        f'<span data-t="copy"></span></button></figcaption>'
        f'<pre><code class="language-{cls}">{esc(code)}</code></pre></figure>'
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
        p = re.sub(r"\[([^\]]+)\]\((#[\w-]+)\)", r'<a href="\2" data-nav>\1</a>', p)
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
        blocks.append(f'<section class="fgroup"><h2 id="{slug(title)}">{esc(title)} <span class="fcount">{len(items)}</span></h2><ol class="flist">{"".join(lis)}</ol></section>')
    return "".join(blocks)


def render(md: str, lang: str, mod) -> tuple[str, list[tuple[str, str]]]:
    lines = md.strip("\n").split("\n")
    out: list[str] = []
    toc: list[tuple[str, str]] = []
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
            out.append(code_block(translate_code(CODE[name], lang), lng))
            i += 1
            continue
        if s == "{features}":
            flush()
            out.append(features_html(mod))
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
            hid = slug(text)
            if level == 2:
                toc.append((hid, re.sub(r"`", "", text)))
            out.append(f'<h{level} id="{hid}">{inline(text)}</h{level}>')
            i += 1
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            header, body = rows[0], [r for r in rows[2:]]
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
            out.append(f'<aside class="note"><p>{inline(" ".join(buf))}</p></aside>')
            continue
        para.append(s)
        i += 1
    flush()
    return "".join(out), toc


def text_of(h: str) -> str:
    t = re.sub(r"<pre>.*?</pre>", " ", h, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def build_data() -> dict:
    data: dict = {"nav": NAV, "langs": {}}
    for lang, mod in LANGS.items():
        pages = {}
        for _, ids in NAV:
            for pid in ids:
                title, body = mod.PAGES[pid]
                rendered, toc = render(body, lang, mod)
                pages[pid] = {"title": title, "html": rendered, "toc": toc, "text": text_of(rendered)[:4000]}
        data["langs"][lang] = {"ui": mod.UI, "groups": mod.GROUPS, "pages": pages, "home": mod.HOME}
    return data


def home_static() -> dict:
    count = lambda c: sum(1 for ln in c.splitlines() if ln.strip())  # noqa: E731
    a = count(CODE["aiogram"])
    n = count(CODE["nicebot_same"])
    return {
        "aiogram_lines": a,
        "nicebot_lines": n,
        "hello_lines": count(CODE["hello"]),
        "hello": code_block(CODE["hello"], "python", "bot.py"),
        "aiogram": code_block(CODE["aiogram"], "python", f"aiogram · {a}"),
        "nicebot": code_block(CODE["nicebot_same"], "python", f"nicebot · {n}"),
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
    title = re.search(r"<title>.*?</title>", page).group(0)
    standalone = (
        "<!doctype html>\n<html lang=\"uz\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<meta name=\"description\" content=\"nicebot — Telegram botlar uchun Python kutubxonasi. Hujjatlar: o'zbek, rus, ingliz tillarida.\">\n"
        + page.replace(title, title, 1)
        + "\n</html>\n"
    )
    # move <body> marker: the template keeps head-ish parts first, then a <!--BODY--> comment
    standalone = standalone.replace("<!--BODY-->", "</head>\n<body>", 1).replace("<!--/BODY-->", "</body>", 1)
    (out / "index.html").write_text(standalone, encoding="utf-8")
    print(f"ok: {len(page) // 1024} KB, pages={len(data['langs']['uz']['pages'])}")


if __name__ == "__main__":
    main()
