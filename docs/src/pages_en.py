"""New pages (English): VS Code, media, Mini Apps."""

PAGES = {}

PAGES["vscode"] = ("VS Code and autocomplete", """
To make your editor list every method after `ctx.`, you need **one thing**: give the handler parameter a type.

{code:vscode_hint}

## Why?

Python is dynamic. With `async def start(ctx)` the editor has no idea what `ctx` is, so it suggests nothing. With `ctx: Context`, VS Code (Pylance), PyCharm and other editors show:

- every property and method after `ctx.`
- the parameters of each method: typing `ctx.reply("...", ` offers `buttons=`, `keyboard=`, `delete_after=`, `silent=` and more
- a description and a **usage example** when you hover a method
- a red underline when you mistype a parameter name (for example `butons=`)

> [!TIP]
> Every function and class of the library has an example. Hover a method, or `Ctrl`-click it to open the source.

## For other objects too

The same rule works everywhere: annotate `Media`, `User`, `WebAppRequest`, `Nicebot`.

{code:vscode_types}

| What | Type | Where from |
|---|---|---|
| Handler context | `Context` | `from nicebot import Context` |
| Received file | `Media` | `ctx.media` |
| User (database) | `User` or your model | `ctx.user` |
| Mini App request | `WebAppRequest` | an `@bot.api` handler |
| The bot | `Nicebot` | `ctx.bot` |
| Test session | `TestSession` | `bot.test()` |

## VS Code setup

1. Install the **Python** extension (Pylance comes with it).
2. Pick the Python interpreter where nicebot is installed in the bottom-right corner (`Ctrl+Shift+P` → *Python: Select Interpreter*).
3. Optional — `.vscode/settings.json`:

{code:vscode_settings:json}

> [!NOTE]
> PyCharm needs no setup — writing `ctx: Context` is enough.
""")

PAGES["media-receive"] = ("Receiving files", """
When a user sends a photo, video, document, voice note or any other file, nicebot turns it into one handy `Media` object: `ctx.media`.

{code:media_receive}

## Which kinds to catch

Pass content types to `@bot.on(...)`. Several can be listed together.

| Type | What it is |
|---|---|
| `"photo"` | Photo (compressed by Telegram) |
| `"video"` | Video |
| `"animation"` | GIF or silent MP4 |
| `"document"` | Any file (PDF, ZIP, an uncompressed photo…) |
| `"audio"` | Music |
| `"voice"` | Voice message |
| `"video_note"` | Round video message |
| `"sticker"` | Sticker |
| `"any"` | Any message |

> [!TIP]
> When a user sends a picture **as a file**, it arrives as `"document"`. To accept both, write `@bot.on("photo", "document")` and check `ctx.media.is_image`.

## The Media object

{code:media_fields}

Telegram delivers photos in several sizes — `ctx.media` picks the largest automatically.

## Asking for a file

To ask for a file inside a conversation, pass a file validator to `ctx.ask`. If the file is wrong (kind, size or MIME type), the bot explains the problem and asks again.

{code:media_ask}

| Validator | Accepts | Returns |
|---|---|---|
| `Photo` | photos only | `PhotoSize` |
| `File` | any file | `Media` |
| `Document` | documents | `Media` |
| `Video` | videos | `Media` |
| `Audio` | music | `Media` |
| `Voice` | voice messages | `Media` |

`File`, `Document`, `Video`, `Audio` and `Voice` accept `max_size="10MB"`, `mime="application/pdf"` or `mime="image/*"` (a list works too) and `kinds=[...]`.

## Albums

When several photos or videos come as one album, `@bot.album()` gives them to you in **one call** — see [Albums and editing](#media-albums).
""")

PAGES["media-download"] = ("Downloading and saving", """
You can get a file in two ways: into memory (`bytes`) or straight to disk.

{code:media_download}

| Method | Result | When |
|---|---|---|
| `await ctx.download()` | `bytes` | process the file right away (edit an image, read a CSV) |
| `await ctx.save(path)` | path (`str`) | keep the file |
| `await ctx.media.download()` / `.save()` | the same | from a `Media` object |
| `await bot.download_file(file_id)` | `bytes` | outside handlers, by `file_id` |
| `await bot.save_file(file_id, path)` | path | outside handlers |

`save()` writes the file **in chunks**, so a big file never fills the memory.

## Where the file goes

- `save()` — into `downloads/`, with the file's original name (or `file_unique_id` + extension when it has none)
- `save("uploads/")` — a path ending with `/` (or an existing folder) keeps the file name inside that folder
- `save("avatar.jpg")` — exactly this path
- missing folders are created for you

## The 20 MB limit

Telegram's cloud Bot API lets bots download files **up to 20 MB**. For bigger files nicebot raises `FileTooBig`. You can check beforehand with `ctx.media.can_download`.

{code:media_too_big}

> [!NOTE]
> The sending limit is different: a bot can send files **up to 50 MB**.

## Big files: your own Bot API server

For files up to 2 GB run Telegram's open-source [Bot API server](https://github.com/tdlib/telegram-bot-api) yourself and pass its address. nicebot understands `--local` mode too: files are read straight from disk, without the network.

{code:media_local_api}
""")

PAGES["media-send"] = ("Sending files", """
Every file type has its own method. They all work the same way: the first argument is the file, the second is the caption.

{code:media_send}

## Where a file can come from

| Source | Example |
|---|---|
| Local path | `"images/menu.jpg"`, `Path("menu.jpg")` |
| URL | `"https://example.com/a.jpg"` — Telegram downloads it |
| `file_id` | a file already in Telegram: instant, no upload |
| `Media` object | `ctx.media` — send a received file back |
| `bytes` / `BytesIO` | a file created in memory (pass `filename=`) |
| `InputFile` | full control: `InputFile(data, filename="a.pdf")` |

A local path that does not exist raises a clear `FileNotFoundError` instead of a confusing Telegram error.

## Files created in memory

Charts, QR codes, Excel or CSV files can be sent without writing them to disk:

{code:media_bytes}

## More options

Every sending method accepts the `ctx.reply` options (`buttons=`, `keyboard=`, `delete_after=`, `silent=`, `protect=`, `quote=`, `chat_id=`) plus media options:

{code:media_options}

| Option | Meaning |
|---|---|
| `spoiler=True` | the photo/video is blurred until tapped |
| `caption_above=True` | caption above the media |
| `thumbnail=` | a small preview for videos and documents |
| `duration=`, `width=`, `height=` | video/audio metadata |
| `supports_streaming=True` | watch the video before it is fully downloaded |
| `performer=`, `title=` | for audio |
| `filename=` | the file name when sending `bytes` |

## Automatic cache

When you send the same local file a second time, nicebot does not upload it again — the `file_id` Telegram returned is remembered and reused. If the file changes (size or time), it is uploaded again.

{code:media_cache}

## Automatic kind detection

`ctx.send_file()` picks the method from the extension: `.jpg/.png` → photo, `.mp4` → video, `.mp3` → audio, `.ogg` → voice, everything else → document. A `Media` object keeps its original kind. Force a kind with `kind="document"`.

## Copying and forwarding

{code:media_forward}
""")

PAGES["media-albums"] = ("Albums and editing", """
## Sending an album

2–10 files go out as one album. Photos and videos can be mixed; documents and audio go in albums of their own. The caption appears under the first file.

{code:media_album_send}

## Receiving an album

Telegram delivers an album as separate messages. `@bot.album()` collects them and calls your handler **once**.

{code:media_album_receive}

> [!TIP]
> Without an `@bot.album()` handler, each file of the album reaches your regular handlers such as `@bot.on("photo")` one by one.

## Replacing a photo in place

`ctx.edit_media()` replaces the photo, video or document without deleting the message. Great for galleries, catalogs and ◀️ ▶️ browsing.

{code:media_edit}

## Status

While you prepare a big file, show a status: `await ctx.action("upload_photo")`, `"upload_video"`, `"upload_document"`, `"record_voice"`. The handler option `typing="upload_photo"` keeps the status visible for as long as the handler runs.
""")

PAGES["miniapp"] = ("Mini Apps: overview", """
A **Mini App** is a web page (HTML, CSS, JavaScript) that opens inside Telegram. A shop, a game, a form, a calendar — anything a website can do, except that the user never leaves Telegram and you know who they are without a login.

nicebot gives you everything a Mini App needs **in the same process as the bot**:

- a web server: `bot.webapp("webapp")` serves your HTML/JS/CSS
- a backend API: `@bot.api("/api/...")` — the user is verified by Telegram's signature automatically
- a frontend helper: `nicebot.js` — requests, buttons, theme, uploads
- HTTPS: `bot.start(tunnel=True)` — a free HTTPS address with no domain or certificate

## How it works

1. The bot sends the user a Mini App button.
2. The user taps it — Telegram opens your page and hands it `initData` (signed data saying who opened it).
3. The page calls your `@bot.api` endpoints through `nicebot.js`; `initData` is attached to every request.
4. nicebot checks the signature with your bot token and gives your handler a **trustworthy** `req.user`.
5. The handler writes to the database, messages the user in the chat (`req.send`) and returns an answer.

## Your first Mini App in 5 minutes

Project layout:

{code:miniapp_tree:text}

`bot.py`:

{code:miniapp_quick_py}

`webapp/index.html`:

{code:miniapp_quick_html:html}

Run `python bot.py`. The terminal shows:

{code:miniapp_log:text}

Send `/start` to your bot and tap **🛍 Do'kon** — the page opens and greets you by name.

> [!NOTE]
> `tunnel=True` needs `cloudflared` or `ssh` on your computer (`ssh` already ships with Windows 10+, macOS and Linux). Details: [Developing without HTTPS](#miniapp-dev).

## About HTTPS

Telegram apps open Mini Apps **only over HTTPS** — that is Telegram's rule and nothing can bypass it. But you do not need to buy a domain or set up certificates:

| Situation | Solution |
|---|---|
| Development | `bot.start(tunnel=True)` — free HTTPS address |
| Testing in a browser | `Nicebot(debug=True)` → `http://localhost:8080` |
| Telegram test server | `Nicebot(test_server=True)` — plain HTTP works |
| Production | your domain + Caddy/Nginx → `Nicebot(public_url=...)` |

## Next steps

1. [Opening a Mini App](#miniapp-open) — button, keyboard, menu, link and BotFather
2. [Backend: @bot.api](#miniapp-backend) — reading and saving data, receiving files
3. [Frontend: nicebot.js](#miniapp-frontend) — the JavaScript helper
4. [Developing without HTTPS](#miniapp-dev) — tunnel, browser and test server
5. [Deployment and security](#miniapp-deploy) — domain, CORS, separate hosting
6. [Full example: a shop](#miniapp-example)
""")

PAGES["miniapp-open"] = ("Opening a Mini App", """
A Mini App can be opened in 4 ways. Which one to use depends on what your app does.

{code:miniapp_open}

| Way | Where it shows | Sending data back to the bot |
|---|---|---|
| Inline button `Button(webapp=...)` | under a message | through `@bot.api` (the most convenient) |
| Reply keyboard `ReplyButton(webapp=...)` | under the message field | `nicebot.sendData()` → `@bot.webapp_data()` |
| Menu button `bot.menu_app(...)` | next to the message field, always | through `@bot.api` |
| Link `bot.app_link(...)` | anywhere (channel, website, QR) | through `@bot.api` |

> [!TIP]
> Write the address as a **relative path** like `"/shop"`. nicebot turns it into a full HTTPS URL using `public_url` (or the tunnel address). Full `https://...` URLs work too.

## Reply keyboard and sendData

Here the Mini App sends its data straight to the bot as a message and closes. No server requests are needed — handy for simple forms. Up to 4 KB of data.

{code:miniapp_senddata}

## BotFather setup

Inline and menu buttons need no BotFather setup. For extra features:

1. **Direct link** (`t.me/your_bot/shop`): @BotFather → `/newapp` → pick the bot → name, description, picture and Mini App URL → a short name (`shop`). Link: `bot.app_link("shop")`.
2. **Main Mini App** (the "Open App" button in the bot's profile): @BotFather → `/mybots` → your bot → *Bot Settings* → *Configure Mini App* → the URL. Link: `bot.app_link()`.
3. **Menu button** in code: `bot.menu_app("🛍 Shop")` — set when the bot starts. For one user only: `await bot.set_menu_app("🎮 Play", "/game", chat_id=ctx.chat_id)`.

> [!WARNING]
> A tunnel address changes on every start, so give BotFather a permanent domain. During development inline buttons and `bot.menu_app()` are enough — they pick up the current address.

## The startapp parameter

A link can carry a parameter: `bot.app_link("shop", startapp="promo")`. The backend gets it as `req.start_param`, the frontend as `nicebot.startParam`.
""")

PAGES["miniapp-backend"] = ("Backend: @bot.api", """
`@bot.api` is an HTTP endpoint your Mini App calls. It runs in the same process as the bot, so you have direct access to the database, to `bot` and to every nicebot feature.

{code:miniapp_api}

## Secure by default

The `initData` signature of every request is checked with your bot token (**HMAC-SHA256**). A wrong or outdated (older than 24 hours) signature is rejected with `401` before your handler runs. That is why you can fully trust `req.user` — it cannot be forged.

`auth=False` makes a public endpoint (a product list, for example). There `req.user` is empty.

## WebAppRequest

{code:miniapp_req}

## Responses

| The handler returns | The browser gets |
|---|---|
| `dict` / `list` | JSON |
| `str` | text |
| `None` | `{"ok": true}` |
| `aiohttp.web.Response` | as is |

Report errors with plain Python exceptions — nicebot turns them into the right HTTP response:

{code:miniapp_errors}

## Receiving files

Uploading a photo or a document from the Mini App: `nicebot.upload(...)` on the frontend, `await req.form()` on the backend.

{code:miniapp_upload_py}

## Answering in the chat

- `await req.send("...")` — a message from the bot to the user (buttons work too)
- `await req.send_photo(...)`, `await req.send_document(...)` — a file
- `await req.answer(title, text)` — when the Mini App was opened from an inline button, a message on the user's behalf in that chat

> [!NOTE]
> `req.send` works only if the user has started the bot (`/start`). Mini Apps are usually opened from the bot, so this is normally true.

## Testing

{code:miniapp_test}
""")

PAGES["miniapp-frontend"] = ("Frontend: nicebot.js", """
`nicebot.js` is a small JavaScript helper your bot serves at `/nicebot.js`. It sits on top of Telegram's `telegram-web-app.js` and turns the most common tasks into one line.

{code:miniapp_js_basic:html}

Load both scripts in `<head>` or at the end of `<body>`, **in this order**.

## Requests

| Function | Meaning |
|---|---|
| `nicebot.get(path)` | GET request |
| `nicebot.post(path, data)` | POST with a JSON body |
| `nicebot.put(path, data)`, `nicebot.del(path)` | PUT / DELETE |
| `nicebot.upload(path, files, fields)` | file upload (multipart) |

All return a `Promise`. `initData` is attached to every request. When the backend returns an error (`400`, `403`…), the `Promise` rejects and `e.message` holds the backend's error text.

## Interface

{code:miniapp_js_ui}

| Function | Meaning |
|---|---|
| `nicebot.mainButton(text, onClick)` | the big button at the bottom |
| `nicebot.hideMainButton()` | hide it |
| `nicebot.progress(true/false)` | loading indicator on the button |
| `nicebot.backButton(onClick)` | the "back" button at the top |
| `nicebot.alert(text)` | a message popup (`Promise`) |
| `nicebot.confirm(text)` | a Yes/No popup (`Promise<boolean>`) |
| `nicebot.haptic(kind)` | vibration: `"light"`, `"medium"`, `"heavy"`, `"success"`, `"error"`, `"warning"` |
| `nicebot.close()` | close the Mini App |

## Theme

`nicebot.theme()` writes Telegram's colors into CSS variables, so your app matches the user's light or dark theme:

{code:miniapp_js_theme:text}

## More

{code:miniapp_js_more}

The full Telegram API is available too: `nicebot.tg` is `window.Telegram.WebApp` itself.

## When the frontend lives elsewhere

If your page is on GitHub Pages or Vercel and the bot is on another server, load `nicebot.js` **from the bot's server**. It detects where it was loaded from and sends every request there. Enable CORS on the server — see [Deployment and security](#miniapp-deploy).
""")

PAGES["miniapp-dev"] = ("Developing without HTTPS", """
Telegram opens Mini Apps only over HTTPS. While developing you have 3 options — none needs a domain or a certificate.

## 1. Tunnel: a free HTTPS address

{code:miniapp_dev_tunnel}

`tunnel=True` exposes the server on your computer through a secure HTTPS address and stores it in `bot.public_url`. Relative Mini App URLs (`webapp="/"`), `bot.menu_app()` and `webhook=True` use that address.

| Provider | What you need | Address looks like |
|---|---|---|
| `cloudflared` | the [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) program | `https://...trycloudflare.com` |
| `localhost.run` | only `ssh` | `https://...lhr.life` |
| your own command | e.g. `ngrok` | the first `https://` address it prints |

> [!WARNING]
> The tunnel address changes on every start. Use it for development only; in production use your own domain.

Webhooks work through the tunnel too:

{code:miniapp_webhook}

## 2. Testing in a normal browser

The fastest way to check design and logic is without Telegram, in plain Chrome or Firefox. With `debug=True` nicebot creates a fake but correctly signed user, and `nicebot.js` uses it automatically.

{code:miniapp_dev_browser}

Open `http://localhost:8080` — `@bot.api` requests run as `dev_user`. DevTools, hot reload and other tools work as usual.

> [!NOTE]
> For safety the fake user is given out only with `debug=True` and only to requests from the same computer (`localhost`). Turn `debug` off in production.

## 3. Telegram test server

In Telegram's separate test environment Mini Apps open from plain `http://` links too — for example from your phone to your computer on the same Wi-Fi.

{code:miniapp_dev_test_server}

The test server needs its own account and bot: create a test account in the Telegram app and get a token from @BotFather there ([guide](https://core.telegram.org/bots/webapps#testing-mini-apps)).

## Which one to pick

- Page design and JavaScript → **browser** (`debug=True`)
- Checking inside real Telegram → **tunnel** (`tunnel=True`)
- Local network without internet → **test server**
""")

PAGES["miniapp-deploy"] = ("Deployment and security", """
## On your own domain

In production run the bot on a server and put a web server with HTTPS (Caddy or Nginx) in front of it.

{code:miniapp_deploy}

[Caddy](https://caddyserver.com) obtains and renews the HTTPS certificate by itself — the whole config is 3 lines:

{code:miniapp_caddy:text}

Once `public_url` (or `PUBLIC_URL`) is set, relative URLs, `bot.menu_app()` and `webhook=True` use that domain.

## Frontend on separate hosting

You can keep the frontend on GitHub Pages, Vercel or Netlify and the backend on the bot's server. To do so:

1. Enable CORS on the bot server — list the sites allowed to send requests.
2. Load `nicebot.js` from the bot server in your frontend.
3. Put the full frontend URL in the Mini App button: `Button("🛍", webapp="https://me.github.io/shop/")`.

{code:miniapp_cors}

## Security rules

- **Never** trust `nicebot.user` or a `user_id` sent by the browser — trust only `req.user` on the backend: it is verified by the signature.
- Compute prices, discounts and totals on the backend; let the frontend send only product `id`s.
- Use `auth=False` only for truly public data.
- Turn off `debug=True` in production.
- Never put your bot token into frontend code.

If you use another server (FastAPI, Django), verify `initData` yourself:

{code:miniapp_security}

## Health check

To check the server is alive: `GET /nicebot/health` → `{"ok": true, "bot": "...", "uptime": 123}`.
""")

PAGES["miniapp-example"] = ("Full example: a shop", """
This example puts everything together: a product list, a cart, Telegram's main button, saving the order, and messages to the user and the admin.

## bot.py

{code:miniapp_shop_py}

## webapp/index.html

{code:miniapp_shop_html:html}

## Running it

1. `pip install nicebot`
2. Save both files in the layout above and put your token from @BotFather into `token=`.
3. `python bot.py` — the tunnel address appears in the terminal.
4. Send `/start` to the bot, tap **🛍 Do'kon**, add products and tap **Buyurtma berish**.
5. An order message arrives in the chat, and the admin gets a notification.

> [!TIP]
> Open `http://localhost:8080` in your browser first — thanks to `debug=True` everything works without Telegram. Then check it inside Telegram.

## Next steps

- Move the products into a `Product` model ([Database](#database))
- Add payment with Telegram Stars ([Payments](#payments))
- Write admin commands for orders ([Admin panel](#admin))
""")
