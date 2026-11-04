"""English documentation text."""

UI = {
    "search": "Search…",
    "on_this_page": "On this page",
    "copy": "Copy",
    "copied": "Copied",
    "prev": "Previous",
    "next": "Next",
    "menu": "Contents",
    "no_results": "No results",
    "theme": "Theme",
    "edit_hint": "Bot API",
    "tagline": "A Python library for Telegram bots",
}

GROUPS = {
    "start": "Getting started",
    "basics": "Basics",
    "ui": "Buttons and dialogs",
    "data": "Data",
    "business": "Business tools",
    "advanced": "Advanced",
    "reference": "Reference",
}

PAGES = {}

PAGES["intro"] = ("Introduction", """
nicebot is a Python library that makes writing Telegram bots as simple as possible. One import, one object and plain functions. A database, buttons, dialogs, translations, statistics and an admin panel are built in.

{demo:hello}

This is a complete, working bot. There is no `Dispatcher`, no `Router` and no state classes, and the user is saved to the database automatically.

## Why nicebot?

Let's compare a simple sign-up bot. First, aiogram:

{code:aiogram}

The same bot in nicebot:

{demo:nicebot_same}

`ctx.ask()` asks a question and waits for the answer. Pass `int` and the bot politely asks again until it gets a number. You don't write a `StatesGroup`, and you don't store or clear any state.

## What's inside

- **Full Bot API 10.3:** 403 types and 185 methods generated from the official specification
- **Built-in ORM:** one API for SQLite, PostgreSQL, MySQL and MongoDB, with automatic migrations
- **Dialogs:** `ask`, `confirm`, `choose`, `form` and ready-made validators
- **Buttons:** `on_click`, templates, toggles, expiring and one-time buttons, automatic layout
- **Business:** referrals, broadcasts, statistics, admin panel, required subscription, support, Telegram Stars
- **Reliability:** waits out flood limits, retries on network errors, loses no updates on restart
- **Speed:** msgspec types and a single connection pool

The full list is on the [50 features](#features) page.

> nicebot is built on `async`. Every handler is an `async def`, and every call to Telegram is written with `await`.
""")

PAGES["install"] = ("Installation", """
You need Python 3.10 or newer.

{code:install:bash}

The part in square brackets installs the driver for that database. SQLite works without extras.

## Create a ready-made project

{code:new:bash}

The command creates this layout:

{code:tree:text}

Open `.env` and replace `BOT_TOKEN` with the token @BotFather gave you.

{code:env:bash}

## Check the version

`nicebot version` prints the library, Bot API and Python versions.
""")

PAGES["first-bot"] = ("Your first bot", """
## 1. Get a token

Open @BotFather in Telegram, send `/newbot`, then choose a name and a username. You'll get a token like `123456:ABC-DEF...`. Never share it.

## 2. Write the code

Create `bot.py`:

{demo:hello}

## 3. Run it

```bash
python bot.py
```

The terminal shows `✅ @your_bot ishga tushdi`. Send `/start` to your bot and it greets you by name.

## What happened?

| Line | Meaning |
|---|---|
| `Nicebot(token=...)` | Creates the bot. Without `db`, an in-memory SQLite is used |
| `@bot.command("start")` | Calls the function below when `/start` arrives |
| `async def start(ctx)` | `ctx` knows everything about the current message |
| `await ctx.reply(...)` | Sends a reply to this chat |
| `bot.start()` | Starts receiving messages. Stop it with Ctrl+C |

> To keep data after a restart, write `Nicebot(token=..., db="sqlite:///bot.db")`.

## Reload on code changes

With `bot.start(reload=True)` the bot restarts itself every time you save a file, which is very handy during development.
""")

PAGES["concepts"] = ("Core concepts", """
nicebot has only three concepts.

## Bot

`Nicebot` is your whole application. The token, database, admins, language and other settings go here.

{code:options}

## Handler

A handler is an `async` function that runs when something happens. The decorator says when: `@bot.command("start")`, `@bot.text("salom")`, `@bot.callback("buy:{id:int}")` and so on. Handlers are checked in the order you declare them, and the first match runs.

## ctx (context)

A new `ctx` is created for every message and passed to the handler as the first argument. It does two jobs:

- **it gives you data:** `ctx.text`, `ctx.user`, `ctx.chat_id`, `ctx.args`…
- **it acts:** `ctx.reply()`, `ctx.edit()`, `ctx.ask()`, `ctx.photo()`…

## Lifecycle

When a message arrives, this happens:

1. If the user is answering a `ctx.ask()`, the message goes there
2. Built-in middleware runs: the user is saved, maintenance mode and required subscription are checked
3. Your middleware runs
4. The first matching handler is called
5. If nothing matched, `@bot.fallback()` or support mode handles it
6. If a button was pressed and you didn't answer it, `answerCallbackQuery` is sent automatically
""")

PAGES["handlers"] = ("Handlers", """
## Kinds

{code:handlers}

## Handler options

You can add these options to any decorator:

{code:handler_opts}

| Option | What it does |
|---|---|
| `admin=True` | Only for `Nicebot(admins=[...])` |
| `chat="private"` | `private`, `group`, `supergroup`, `channel` |
| `throttle="3s"` | Rate limit per user. When exceeded, shows "⏳ Please wait" |
| `typing=True` | Shows "typing…" while the handler runs. `"upload_photo"` works too |
| `state="x"` | Only when the user is in this state |
| `users=[...]` | Only for these ids |
| `description="..."` | The command appears in Telegram's menu. `{"uz": ..., "ru": ...}` also works |

## Filters

`F` provides ready-made filters. Combine them with `&` (and), `|` (or) and `~` (not).

{code:filters}

## Router: split code into files

{code:router}

## All event kinds

`@bot.callback`, `@bot.inline`, `@bot.chosen_inline`, `@bot.edited`, `@bot.channel`, `@bot.join`, `@bot.leave`, `@bot.album`, `@bot.paid`, `@bot.pre_checkout`, `@bot.webapp_data`, `@bot.my_chat_member`, `@bot.chat_member`, `@bot.join_request`, `@bot.reaction`, `@bot.poll_answer`. For any other update: `@bot.event("chat_boost")`.

> `raise SkipHandler` inside a handler lets the next matching handler run.
""")

PAGES["ctx"] = ("ctx: the context", """
## Data

{code:ctx_props}

## Sending

{code:ctx_send}

Every send method accepts the same extra options:

| Option | Meaning |
|---|---|
| `buttons=` | Inline buttons ([Buttons](#buttons)) |
| `keyboard=` | Bottom keyboard. `False` closes it |
| `columns=` | Number of button columns |
| `delete_after="1m"` | Delete the message automatically |
| `silent=True` | No notification sound |
| `protect=True` | Disallow forwarding and saving |
| `quote=True` | Reply to the incoming message |
| `preview=False` | Disable link previews |
| `chat_id=` | Send to another chat |

## Editing and answering

{code:ctx_edit}

`ctx.edit()` picks what to edit by itself: the caption when the message has media, otherwise the text. It quietly ignores "message is not modified".

## More useful methods

| Method | What it does |
|---|---|
| `ctx.forward(chat)` / `ctx.copy(chat)` | Send the message to another chat |
| `ctx.download()` / `ctx.save(path)` | Download a file |
| `ctx.action("upload_photo")` | Show a status |
| `ctx.is_member("@kanal")` | Check a subscription |
| `ctx.notify_admins(text)` | Message the admins |
| `ctx.background(func)` | Background task |
| `ctx.t("key")` | Translation |
""")

PAGES["formatting"] = ("Text formatting", """
By default nicebot uses HTML parse mode, so `<b>`, `<i>`, `<code>` and `<a href>` tags work right away.

## Handling user text safely

User text may contain `<` or `&`. If you insert it directly, Telegram returns an error. `html()` escapes the values and leaves the template untouched:

{code:html}

Ready helpers: `bold`, `italic`, `underline`, `strike`, `spoiler`, `code`, `pre`, `link`, `mention`, `quote`, `escape`.

> Even if the markup is broken, the bot doesn't crash. nicebot resends the message without formatting and logs a warning.

## Other modes

`Nicebot(parse_mode="MarkdownV2")`, or `parse_mode=None` to send plain text.
""")

PAGES["buttons"] = ("Inline buttons", """
## A button and its action

`Button` takes a label and one action. The most convenient is `on_click`: pressing the button calls a plain function. You don't invent callback data or catch it in a separate handler.

{demo:buttons}

| Kind | Syntax |
|---|---|
| Function | `Button("OK", on_click=func)` |
| Link | `Button("Site", url="https://...")` |
| Mini App | `Button("App", webapp="https://...")` |
| Copy | `Button("Code", copy="PROMO")` |
| Share | `Button("Share", share="text")` |
| Plain data | `Button("Yes", data="yes")` |
| Payment | `Button("Pay", pay=True)` |

## Passing parameters

{code:buttons_params}

## Callback templates

{code:buttons_template}

Types: `int`, `float`, `bool`, `str` (default) and `any`. Values reach the handler with the right type.

## Automatic layout

{code:buttons_layout}

## Protected buttons

{code:buttons_safe}

> Telegram limits callback_data to 64 bytes. nicebot stores longer data in the database and puts a short key on the button, so you never notice the limit. Button presses are also answered automatically, so the loading clock never hangs.
""")

PAGES["keyboards"] = ("Keyboards and toggles", """
## Bottom (reply) keyboard

{code:reply_kb}

The `:contact` suffix makes a button that asks for the phone number, and `:location` asks for the location. For more complex cases there is `ReplyButton("...", webapp=...)`.

## Toggle: switch on and off

For settings menus. Pressing the button swaps ✅ and ⬜️ by itself, and the value is saved for each user.

{demo:toggle}

To react to a change right away, write `Toggle(..., on_change=func)`, and `func(ctx, value)` is called.
""")

PAGES["conversations"] = ("Dialogs", """
This is the biggest convenience in nicebot. You ask a question and wait for the answer inside the same function.

## ask

{demo:ask}

- If the user sends `/cancel` or presses "🚫 Cancel", the dialog ends quietly
- After 10 minutes without an answer, "⌛️ Time is up" is shown. Change it with `timeout="5m"`
- A wrong value shows a clear error and the question is asked again. Set the number of attempts with `retries=`

## confirm

{demo:confirm}

## choose

{code:choose}

## form: several questions in a row

{code:form}

The result of `form` is a `dict`, and you can also read fields with a dot: `data.name`.

> You can run dialogs with thousands of users at once. Each one waits in its own handler and doesn't block the others.
""")

PAGES["validators"] = ("Validators", """
A validator checks the user's answer and turns it into a clean value.

{code:validators}

| Validator | Returns | Notes |
|---|---|---|
| `Text(min=, max=)` | `str` | Length limits |
| `Integer(min=, max=)` / `int` | `int` | Understands spaces: `1 000 000` |
| `Number` / `float` | `float` | Accepts a comma: `12,5` |
| `Phone` | `"+998901234567"` | Contact button. Checks Uzbek operator codes |
| `Email` | `str` | Lowercased |
| `Url` | `str` | Must start with `https://` |
| `Date(format=)` | `date` | Default format: `DD.MM.YYYY` |
| `Choice(choices=)` | `str` | Shows the options as buttons |
| `Regex(pattern)` | `str` | |
| `Photo` / `File` | media object | Has `.file_id` |
| `Location` | `Location` | Location button |

Phone numbers can be typed in any form: `90 123 45 67`, `+998 (90) 123-45-67` or `8 90 1234567`. The result is always `+998901234567`.
""")

PAGES["state"] = ("State", """
Most of the time `ctx.ask()` is enough. Use state when a user stays on one step for a long time, for example several days. State is stored in the database and survives restarts.

{code:state}

| Method | Meaning |
|---|---|
| `await ctx.set_state("name", **data)` | Set the state |
| `await ctx.get_state()` | Current state or `None` |
| `await ctx.state_data()` | Saved data |
| `await ctx.update_data(**data)` | Add data |
| `await ctx.clear_state()` | Clear |
""")

PAGES["menus"] = ("Menus and pagination", """
## Multi-level menu

You describe the menu as a dictionary. Navigation and the "⬅️ Back" button work automatically, and the message is edited in place instead of sending a new one.

{demo:menu}

Value types: text (shown), `Menu` or `dict` (a submenu), a function (called), a URL (a link button) or a `Button`.

## Pagination

Splits a long list into pages with ◀️ 2/5 ▶️ buttons.

{code:paginate}
""")

PAGES["database"] = ("Database (ORM)", """
nicebot has its own ORM. The same code runs on SQLite, PostgreSQL, MySQL/MariaDB and MongoDB, and all four are covered by automated tests.

{code:orm_urls}

## Model

{code:orm_model}

Fields: `Int`, `BigInt`, `Float`, `Str(max_length)`, `Text`, `Bool`, `DateTime(auto_now_add=, auto_now=)`, `Date`, `JSON` and `ForeignKey`. Common options: `default=`, `null=`, `unique=`, `index=` and `choices=`.

> **Automatic migrations:** tables are created when the bot starts. Add a new field to a model and the column is added by itself. Your data is never dropped.

## Create, read, update, delete

{code:orm_crud}

## Queries

{code:orm_query}

| Lookup | Meaning |
|---|---|
| `price=5` | equals |
| `price__ne=5` | not equal |
| `__gt` `__gte` `__lt` `__lte` | greater or less than |
| `__in=[...]` / `__not_in` | in or not in a list |
| `__contains` / `__icontains` | contains (`i` ignores case) |
| `__startswith` / `__endswith` | starts or ends with |
| `__isnull=True` | empty |
| `__between=(a, b)` | in a range |

## ForeignKey

`await order.product` loads the related object and caches it. `order.product_id` is the plain number.

## Transactions

{code:orm_tx}

MongoDB supports transactions only on a replica set, so there `transaction()` does nothing.
""")

PAGES["users"] = ("Users and referrals", """
Everyone who writes to the bot is saved to the `nb_users` table automatically and is available as `ctx.user`. Name, username and last activity are kept up to date too.

| Field | |
|---|---|
| `id` | Telegram id |
| `first_name`, `last_name`, `username` | |
| `lang` | Chosen language |
| `phone` | Phone |
| `is_blocked` | Blocked the bot (set automatically) |
| `is_premium` | Telegram Premium |
| `referrer_id` | Who invited them |
| `data` | Any JSON |
| `created_at`, `last_seen` | |

## Add your own fields

{code:user_model}

## Referral system

A new user who comes through `ctx.ref_link` gets `referrer_id` set automatically.

{code:referral}

## Lifecycle events

{code:lifecycle}
""")

PAGES["i18n"] = ("Translations", """
Put one JSON file per language in the `locales/` folder:

{code:i18n_files:json}

{code:i18n_use}

The user's language is chosen in this order: the language saved with `ctx.set_lang()`, then the Telegram app language, then `Nicebot(lang="uz")`. If a key is missing, the default language text is used. The library's own texts ("Yes", "Cancelled" and others) ship in uz, ru and en. You can override them in your own file too, for example `"nb.yes": "Sure"`.
""")

PAGES["admin"] = ("Admin panel and stats", """
{code:admin}

Admin commands appear only in the admins' menu. Regular users don't see them and can't run them.

## Statistics

{code:stats}

| Metric | Meaning |
|---|---|
| DAU / WAU / MAU | Active in the last 1, 7 and 30 days |
| `retention_d7` | Share of users who joined 7–14 days ago and came back last week (%) |
| `top_commands` | Most used commands in 30 days |

## Maintenance mode

While `await bot.maintenance(True)` is on, everyone except admins gets a "🛠 maintenance" message. The mode survives restarts.

## Error reports

When a handler fails, the user gets a polite message and the admins get a report with the traceback. The same error is reported at most once every 10 minutes.
""")

PAGES["broadcast"] = ("Broadcasts", """
{code:broadcast}

- Telegram limits are respected: the default speed is 25 messages per second, changed with `rate=`
- On a 429 error it waits the required time and continues
- Users who blocked the bot are marked `is_blocked=True` and skipped next time
- With `id=`, progress is saved every 20 messages. If the bot stops, call it again with the same `id` and it continues where it left off
- An `on_progress=` function receives the current state every 3 seconds
""")

PAGES["payments"] = ("Payments (Telegram Stars)", """
{code:stars}

`pre_checkout_query` is approved automatically. To check it yourself, write a `@bot.pre_checkout()` handler. Refunds: `await ctx.refund()`.
""")

PAGES["groups"] = ("Groups, subscription and support", """
## Moderating groups

{code:group}

These methods act on the user whose message you replied to, or take `user_id=`. The bot must be a group admin.

## Captcha

{code:captcha}

## Required subscription

{code:subscribe}

The bot must be an admin of the channel, otherwise it can't check membership. The result is cached for a minute, so Telegram isn't asked more than needed.

## Support mode

{code:support}
""")

PAGES["middleware"] = ("Middleware, DI and errors", """
## Middleware

Middleware wraps every update and can run code before and after the handler.

{code:middleware}

## Dependency injection (DI)

A handler asks for what it needs by parameter name or type:

{code:di}

Available by name: `bot`, `message`, `callback`, `user`, `chat`, `text`, `args`, `arg`, `payload`, `data`, `value`, `album`, `lang`, `state`, `config`, `db` and `storage`, plus callback and regex parameters.

## Errors

{code:errors}
""")

PAGES["miniapp"] = ("Mini Apps", """
nicebot includes a web server that runs in the same process as the bot. It serves Mini App files and creates API endpoints. Telegram's `initData` signature is verified with HMAC automatically.

{code:miniapp_py}

In the browser, include the ready-made `nicebot.js`. It adds `initData` to every request:

{code:miniapp_js:html}

A missing, wrong or expired `initData` is rejected with `401`. `@bot.api(..., auth=False)` creates a public endpoint. The `WebAppRequest` object has `user`, `json`, `query`, `params` and `db_user()`.
""")

PAGES["scheduler"] = ("Scheduling, background and cache", """
## Scheduled jobs

{code:schedule}

Days can be written in English (`mon`…`sun`) or Uzbek (`du`, `se`, `chor`, `pay`, `ju`, `shan`, `yak`).

## Background tasks

{code:background}

A failing background task is retried with exponential backoff. When the bot stops, unfinished tasks are awaited.

## Cache

{code:cache}

## Files

{code:files}
""")

PAGES["deploy"] = ("Running and deploying", """
{code:run}

## Polling or webhook

Polling needs no setup and is enough for small and medium bots. A webhook needs an HTTPS domain. nicebot calls `setWebhook` with a secret token and checks incoming requests. Server health is available at `/nicebot/health`.

## Graceful shutdown

On Ctrl+C or SIGTERM the bot stops fetching new updates and waits for running handlers to finish. Then it confirms the offset with Telegram, so no update is lost or handled twice after a restart.

## Docker

{code:docker:docker}

## Reliability

- Flood control (429): waits the required seconds and resends the request
- Network and 5xx errors: up to 3 retries with exponential backoff
- Unknown new update kinds don't break the bot: they are logged and skipped
- Concurrent handlers are capped by `max_concurrency=256`
""")

PAGES["testing"] = ("Testing", """
You can test the bot without Telegram, the way a real user would use it. A fake API records every call.

{code:testing}

| | |
|---|---|
| `t.user(...)` | A test user |
| `user.send(text)` | Send a message |
| `user.click("label")` | Press a button |
| `user.send_photo()` / `send_contact()` / `send_location()` / `send_album()` | Send media |
| `t.last` | The latest message: `.text`, `.buttons`, `.keyboard` |
| `t.messages` / `t.texts` | All messages |
| `t.calls_of("sendPhoto")` | API calls |
| `t.blocked = {id}` | A user who blocked the bot |

Works with `pytest` and `pytest-asyncio`.
""")

PAGES["features"] = ("50 features", """
{features}
""")

PAGES["api"] = ("Bot API", """
`Nicebot` exposes every Bot API method directly. They are generated from the official specification and fully typed, so your editor suggests every parameter.

{code:raw_api}

Types are available via `from nicebot import types`, for example `types.Message` or `types.InlineKeyboardButton`. They are built on msgspec and decode JSON very fast. Your code keeps working even when Telegram adds new fields.

## Versions

| | |
|---|---|
| nicebot | 0.1.1 |
| Bot API | 10.3 |
| Python | 3.10+ |
| License | MIT |
""")

FEATURE_GROUPS = [
    ("Dialogs", [
        ("await ctx.ask()", "Question and answer without FSM classes"),
        ("ctx.confirm()", "Yes/No question that returns True/False"),
        ("ctx.choose(multiple=True)", "Pick several options with ✅/⬜️"),
        ("ctx.form()", "Several questions, validation and re-asking"),
        ("Validators", "Phone (+998), email, date, number, URL, photo and more"),
    ]),
    ("Buttons", [
        ("Button(on_click=)", "A button is bound straight to a function"),
        ("Callback templates", "\"buy:{id:int}\" is parsed automatically"),
        ("Automatic layout", "Short buttons share a row by themselves"),
        ("Toggle", "✅/⬜️ settings with the value saved"),
        ("ttl= and only=", "Expiring buttons and buttons for one person"),
        ("once=True", "One-time button"),
        ("No 64-byte limit", "Long callback data is kept in the database"),
        ("Auto-answer", "The loading clock never hangs"),
        ("Reply shortcuts", "\"📞 Phone:contact\", \":location\""),
        ("ctx.respond()", "Edits after a button press, sends otherwise"),
        ("Multi-level Menu", "The Back button is automatic"),
        ("ctx.paginate()", "◀️ 2/5 ▶️ pagination"),
    ]),
    ("Data", [
        ("Built-in ORM", "One API for SQLite, PostgreSQL, MySQL and MongoDB, with migrations"),
        ("ctx.user", "Users are saved to the database automatically"),
        ("i18n", "ctx.t(), built-in uz/ru/en texts"),
        ("file_id cache", "A local file is uploaded only once"),
    ]),
    ("Business", [
        ("Referral system", "ctx.ref_link, referrer_id and @bot.on_referral"),
        ("Broadcasts", "Rate limits, blocked-user marking and resuming"),
        ("Admin panel", "/stats, /broadcast, /maintenance and /backup"),
        ("Analytics", "DAU/MAU, retention and top commands"),
        ("Required subscription", "required_channels=[…]"),
        ("Support mode", "Messages go to a group, replies go back to the user"),
        ("Maintenance mode", "Admins can still use the bot"),
        ("Telegram Stars", "ctx.invoice() and @bot.paid"),
        ("Groups and captcha", "ban, mute, warn (3 → ban), captcha for newcomers"),
        ("Error reports", "Tracebacks are sent to admins automatically"),
    ]),
    ("Architecture", [
        ("DI via type hints", "async def h(ctx, user: Customer, cfg: Settings)"),
        ("Nicebot.from_env()", "Configuration from a .env file"),
        ("bot.include(\"handlers\")", "Routers are discovered automatically"),
        ("@cache(\"5m\")", "Cache for async functions"),
        ("ctx.background()", "Background tasks with retries"),
        ("@bot.every / @bot.at", "Scheduler with time zones"),
        ("Albums", "A media group arrives as one list in one handler"),
        ("Mini App server", "Files and initData (HMAC) checks inside the bot process"),
        ("Mini App RPC", "@bot.api endpoints and a ready nicebot.js"),
        ("Several bots", "Nicebot.run_all(bot1, bot2)"),
        ("typing=True", "Shows \"typing…\" while the handler runs"),
    ]),
    ("Reliability", [
        ("Flood protection", "Waits and resends on a 429 error"),
        ("throttle=", "Rate limiting against spam"),
        ("Graceful shutdown", "No updates are lost on restart"),
        ("Safe formatting", "html() and a plain-text resend on markup errors"),
        ("delete_after=", "Delete messages automatically"),
        ("Hot reload", "bot.start(reload=True)"),
        ("Test kit", "bot.test(): tests without Telegram"),
        ("CLI", "nicebot new mybot"),
    ]),
]

