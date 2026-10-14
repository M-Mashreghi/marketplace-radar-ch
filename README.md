# marketplace-radar-ch

**A Telegram bot that watches the Swiss second-hand marketplaces [anibis.ch](https://www.anibis.ch), [tutti.ch](https://www.tutti.ch) and [ricardo.ch](https://www.ricardo.ch) for you, and sends new listings straight to your Telegram.**

You tell the bot where you live and what you are looking for, in any language. Every 2 hours it searches all three sites and sends each new listing as its own message, with photo, price, place, description and a link.

- 🎁 **Free items:** new "gratis / gratuit / zu verschenken" listings in your area (on by default)
- 🔎 **Wish list:** up to 20 things you want, typed in any language (`دوچرخه`, `bike`, `vélo`…). The bot translates each one into German, French, Italian and English and searches for all of them
- 💰 **Price range:** an optional minimum and maximum price per item
- 📍 **Your area:** a town, a town plus 5 / 10 / 20 / 50 km, a region or a whole canton
- 🌍 **Four languages:** Persian (فارسی), English, French and German
- 👥 **Many users:** anyone you share the bot with gets their own language, area and list
- 🔁 **No duplicates:** each listing is sent once, even when the same ad is on two sites

You can run it in three places:

| Where | On when | Cost | How |
|---|---|---|---|
| **Your Windows PC** | while the PC is on and you're logged in | free | [step 8](#8-keep-it-running-on-windows-or-linux) |
| **A Linux computer or server** | while it's on (a server: always) | free / your server | [step 8](#linux-systemd) |
| **Cloudflare** | **24/7, no computer needed** | Workers Paid plan, 5 USD/month | [step 9](#9-run-it-on-cloudflare-247) |

On Windows and Linux the bot is plain Python using **only the standard library**, so there is nothing to `pip install`. The Cloudflare version (in the `cloudflare/` folder) is the same bot rewritten as a Cloudflare Worker: same commands, same messages, same searches.

> This is an unofficial hobby project. It is not affiliated with anibis.ch, tutti.ch, ricardo.ch or Telegram.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Download the project](#2-download-the-project)
3. [Create your Telegram bot](#3-create-your-telegram-bot)
4. [Create config.json](#4-create-configjson)
5. [Test the connection](#5-test-the-connection-optional)
6. [Start the bot](#6-start-the-bot)
7. [First steps in Telegram](#7-first-steps-in-telegram)
8. [Keep it running on Windows or Linux](#8-keep-it-running-on-windows-or-linux)
9. [Run it on Cloudflare (24/7)](#9-run-it-on-cloudflare-247)
10. [All Telegram commands](#10-all-telegram-commands)
11. [Sharing the bot with friends](#11-sharing-the-bot-with-friends)
12. [How it works](#12-how-it-works)
13. [Files](#13-files)
14. [Privacy: never commit config.json or bot.db](#14-privacy-never-commit-configjson-or-botdb)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What you need

| | |
|---|---|
| **Python** | 3.8 or newer (tested with 3.13). Download it from <https://www.python.org/downloads/>. On Windows, tick **"Add Python to PATH"** in the installer. |
| **pip packages** | None. Everything the bot uses comes with Python. |
| **Telegram** | A Telegram account (phone or desktop app). |
| **A computer that stays on** | The bot only works while it is running. It needs internet access to `api.telegram.org`, `anibis.ch`, `tutti.ch`, `ricardo.ch`, `translate.googleapis.com` and, once, `download.geonames.org`. |

To check Python is installed, open a terminal and run:

```
python --version
```

On macOS and Linux the command is usually `python3` instead of `python`.

> **How to open a terminal in a folder on Windows:** open the folder in File Explorer, click the address bar, type `cmd` and press Enter.

## 2. Download the project

Either clone it with git:

```
git clone https://github.com/M-Mashreghi/marketplace-radar-ch.git
cd marketplace-radar-ch
```

or, on the GitHub page, click **Code → Download ZIP** and unzip it somewhere permanent (for example `D:\marketplace-radar-ch`). The bot keeps its database and log in this folder, so don't run it from your Downloads folder if you clean that out.

## 3. Create your Telegram bot

Every copy of this project needs its own Telegram bot. Creating one takes a minute:

1. In Telegram, search for **[@BotFather](https://t.me/BotFather)** (the official one has a blue check mark) and open it.
2. Send `/newbot`.
3. Send a **display name**, for example `My Marketplace Radar`.
4. Send a **username**. It must be unique and end in `bot`, for example `my_marketplace_radar_bot`.
5. BotFather answers with a **token** that looks like this:

   ```
   123456789:AAHk3x...long-string...
   ```

**Keep this token secret.** Anyone who has it can control your bot. If it ever leaks, open @BotFather, send `/revoke`, pick your bot and put the new token in `config.json`.

You don't need to set a command list in BotFather: the bot sets its own menu (`/start`, `/add`, `/list`…) every time it starts.

## 4. Create config.json

The bot reads its settings from `config.json`, which you create from the example file that comes with the project.

**Windows** (in a terminal in the project folder):

```
copy config.example.json config.json
```

**macOS / Linux:**

```
cp config.example.json config.json
```

Open `config.json` in a text editor (Notepad is fine) and paste your token:

```json
{
  "telegram_bot_token": "123456789:AAHk3x...your token...",
  "telegram_chat_id": ""
}
```

| Setting | Required | What it does |
|---|---|---|
| `telegram_bot_token` | **yes** | The token from BotFather. The bot will not start without it. |
| `telegram_chat_id` | no | Only used by `telegram_setup.py` to send you a test message. Leave it empty; the setup script fills it in. |
| `allowed_chat_ids` | no | A list of Telegram chat ids that may use the bot, e.g. `["111111111", "222222222"]`. Without it, **anyone** who finds your bot can use it. See [Sharing the bot](#11-sharing-the-bot-with-friends). |

On a server you can use **environment variables** instead of (or on top of) `config.json`; they win over the file:

| Variable | Same as |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `telegram_bot_token` |
| `ALLOWED_CHAT_IDS` | `allowed_chat_ids`, comma separated: `111111111,222222222` |
| `DATA_DIR` | Folder for `bot.db` and `anibis_alert.log` (default: the project folder) |

A full example with every setting:

```json
{
  "telegram_bot_token": "123456789:AAHk3x...",
  "telegram_chat_id": "111111111",
  "allowed_chat_ids": ["111111111", "222222222"]
}
```

## 5. Test the connection (optional)

This checks that your token works and finds your own chat id.

1. In Telegram, open your new bot (search for its username) and send it any message, e.g. `hi`. It won't answer yet, that's fine.
2. In the project folder, run:

   ```
   python telegram_setup.py
   ```

You should see:

```
Token OK, bot is @my_marketplace_radar_bot
Chat id found and saved to config.json
Test message sent. Check Telegram!
```

and receive a test message in Telegram. Your chat id is now in `config.json` under `telegram_chat_id`. That number is what you put in `allowed_chat_ids` if you want to limit who can use the bot.

Run this **before** starting `bot.py`. Once the bot is running it reads the incoming messages itself, so the setup script may not find yours.

| Message | Meaning |
|---|---|
| `Put your bot token in config.json first.` | `telegram_bot_token` is still empty or still says `PASTE_YOUR_BOT_TOKEN_HERE`. |
| `Telegram rejected the token.` | The token is wrong or was revoked. Copy it again from BotFather. |
| `No messages found.` | Send your bot a message in Telegram first, then run the script again. |

## 6. Start the bot

In the project folder:

```
python bot.py
```

The terminal shows `bot started`. Leave the window open while you try it out; closing it stops the bot. Everything the bot prints is also written to `anibis_alert.log` in the same folder.

On the first run the bot creates its database `bot.db`, and the first time someone uses Ricardo it downloads the Swiss postcode list into `ch_postcodes.txt` (a copy already comes with the project).

Only one copy of the bot can run at a time. If you start a second one, it writes `bot is already running, exiting` and stops.

## 7. First steps in Telegram

Open your bot in Telegram and:

1. **Send `/start`** and tap your **language**: فارسی, English, Français or Deutsch.
2. **Type your town or canton**, for example `Lausanne`, `Zurich` or `Vaud`. The bot looks it up on Anibis and shows every option it found, with the number of listings:
   - 📍 Lausanne (town only)
   - ⭕ Lausanne + 5 / 10 / 20 / 50 km
   - 🗺 Lausanne region
   - 🏔 Canton Vaud
   - ✏️ Somewhere else (type another place)

   Tap one. Common spellings work too (`Genf`, `Geneva`, `Bienne`, `Zürich`…).
3. The bot now **checks all three sites** and sends every free item listed in your area right now, followed by a short **setup report** (see below).
4. **Send the name of something you want**, in any language, for example `دوچرخه`, `bike` or `canapé`. You don't need a command: any plain text is treated as a new item. The bot translates it and shows the words it will search for, for example *Fahrrad · vélo · bicicletta · bicycle*, plus any **similar names** it found. Tap **✅ Yes**.
5. The bot asks for a **price range** in CHF. Type one of these, or tap **♾ No limit**:

   | You type | Means |
   |---|---|
   | `20-100` | between 20 and 100 CHF |
   | `-100` or `100` | up to 100 CHF |
   | `20-` | from 20 CHF |
   | `0` or `-` | no limit |

   `20 to 100`, `20 bis 100`, `20 à 100`, `20 تا 100` and Persian digits (`۲۰-۱۰۰`) work too.
6. The bot sends **everything listed now** for that item on all three sites, then from then on **only new listings, every 2 hours**.

### What a listing looks like

Each listing is its own message:

```
🆕 Velo Peugeot 28 Zoll
🏷 anibis.ch
💰 CHF 80.–
📍 1004 Lausanne
🔎 For: bike

Short description of the item…

🔗 Open on anibis.ch
```

Listings whose title uses one of the *similar names* rather than the main words are marked **🔍 similar name**.

### Which listings are sent

- **Only listings that are really about your item.** Every word of a search word must be in the title (`power strip` needs both words), or one long, specific word is enough (`multiprise`). Plurals and compound words count (`Velo` matches `Velos` and `Kindervelo`).
- **Only listings in your price range.** Listings without a clear price ("on request") are kept, in case they fit. On Ricardo, the buy-now price counts, otherwise the current bid.
- **Each listing once.** If the same ad (same title, price and place) is on two sites, you get it once.
- **Limits:** up to 100 listings per search the first time, then up to 50 new ones per check. If there are more, the bot tells you and the report has a link to see them all on the site.

### Reports

After you choose an area, after you add an item, after `/check` and after every automatic 2-hour check, the bot sends a short **report** for each search on each site: whether your area was found there, a link to the same search on the site, how many listings it found or how many were new, and any error.

## 8. Keep it running on Windows or Linux

### Windows

When you're happy with it, let Windows start the bot for you, in the background, without a window:

1. Close the terminal where `python bot.py` is running (this stops it).
2. Double-click **`install_schedule.bat`**.

This creates a Windows Task Scheduler job called **Anibis Alarm** that:

- starts the bot (`main.py` → `bot.py`, using `pythonw.exe` so no window appears) **when you log in**, and
- checks **every 15 minutes** that it's still running and restarts it if it crashed. If it is already running, nothing happens.

The bot starts about a minute after you install it. Running the installer again just replaces the job.

| To… | Do this |
|---|---|
| Check it's running | Send the bot a message, or run `schtasks /Query /TN "Anibis Alarm" /V /FO LIST` |
| See what it's doing | Open `anibis_alert.log` |
| Pause it | `schtasks /Change /TN "Anibis Alarm" /Disable`, then `schtasks /End /TN "Anibis Alarm"` (use `/Enable` to resume) |
| Remove it for good | Double-click **`remove_schedule.bat`** |
| Update the code | Run `remove_schedule.bat`, replace the files, then run `install_schedule.bat` again |

The computer must be **on and logged in** for the bot to work. If it sleeps, the bot catches up after it wakes. More details are in [SCHEDULE.md](SCHEDULE.md).

<a id="linux-systemd"></a>
### Linux (systemd)

On Linux (Ubuntu, Debian, Raspberry Pi OS, a cloud server…) the bot runs as a **systemd service**: it starts when the computer starts, restarts itself if it crashes, and keeps running after you log out.

1. Do steps 2 to 6 above (`python3 bot.py` to try it, then `Ctrl+C` to stop it).
2. In the project folder, run:

   ```
   bash linux/install_service.sh
   ```

   It asks for your `sudo` password once and creates the service **marketplace-radar**, running as your user from this folder.

| To… | Do this |
|---|---|
| Check it's running | `systemctl status marketplace-radar` |
| See what it's doing | `journalctl -u marketplace-radar -f` (or `anibis_alert.log`) |
| Restart after changing files | `sudo systemctl restart marketplace-radar` |
| Remove it for good | `bash linux/remove_service.sh` |

**macOS:** run `python3 bot.py` inside `tmux` or `screen`, so it keeps running after you close the terminal.

> **Only one copy of the bot at a time.** One Telegram bot can only be answered by one copy. Don't run it on Windows, Linux and Cloudflare at the same time: stop the old one first.

## 9. Run it on Cloudflare (24/7)

The `cloudflare/` folder contains the same bot as a **Cloudflare Worker**, so it runs on Cloudflare's servers day and night and your computer can be off.

### How it works there

- Telegram delivers every message straight to the Worker (a *webhook*), so the bot answers at once.
- A timer (*cron trigger*) runs the Worker **every minute**. It first does any waiting `/check`, new area or new item, then the users whose 2-hour check is due. So after `/check`, results arrive within about a minute.
- Everything the Python version keeps in `bot.db` is kept in a Cloudflare **D1** database instead (same tables).
- The bot token is a Cloudflare **secret**: it is never in a file and never in git.

### What it costs

You need the **Workers Paid** plan (**5 USD per month**). The free plan stops each run after 10 ms of computing and 50 web requests, and one check of one user reads dozens of pages, so it would break. This bot's use stays well inside what the paid plan includes, so 5 USD/month is normally the whole bill.

### Will the marketplaces answer Cloudflare?

That can only be checked from Cloudflare itself: some sites block requests coming from data centres. The `/setup` page (step 7 below) tests anibis.ch, tutti.ch, ricardo.ch, Google Translate and Telegram from your Worker and shows ✅ or ❌ for each. If a site shows ❌, the others keep working; if you need that site, run the bot on Windows or Linux instead.

### Setup (once)

You need [Node.js](https://nodejs.org/) (the **LTS** version) on your computer, only for uploading. Open a terminal in the project folder (on Windows use **Command Prompt**, `cmd`) and:

1. **Create a Cloudflare account** at <https://dash.cloudflare.com/sign-up>, then choose the **Workers Paid** plan under *Workers & Pages → Plans*.
2. **Install the tools and log in:**

   ```
   cd cloudflare
   npm install
   npx wrangler login
   ```

   A browser window opens; allow access.
3. **Create the database:**

   ```
   npx wrangler d1 create marketplace-radar
   ```

   It prints a `database_id`. Open `cloudflare/wrangler.toml` and paste it in place of `PASTE_YOUR_DATABASE_ID_HERE`.
4. **Who may use the bot (optional):** in `wrangler.toml`, set `ALLOWED_CHAT_IDS = "111111111,222222222"`. Empty means everyone.
5. **Stop the bot on your computer** if it runs there (Windows: `remove_schedule.bat`; Linux: `bash linux/remove_service.sh`).
6. **Upload the bot and its token:**

   ```
   npx wrangler deploy
   npx wrangler secret put TELEGRAM_BOT_TOKEN
   ```

   `deploy` prints your Worker's address, like `https://marketplace-radar-ch.<your-name>.workers.dev`. `secret put` asks for the token: paste the one from BotFather and press Enter (nothing is shown while you paste).
7. **Connect Telegram:** open `https://marketplace-radar-ch.<your-name>.workers.dev/setup` in your browser. It connects the bot to the Worker and tests every site. When every line is ✅, open your bot in Telegram and send `/start`.

### Moving your users from the Python version (optional)

If people already use the bot on your computer, copy their settings so nobody starts over. In the **project folder** (where `bot.db` is):

```
python tools/export_to_d1.py
cd cloudflare
npx wrangler d1 execute marketplace-radar --remote --file ../d1_import.sql
```

Then delete `d1_import.sql` (it contains everyone's chat id and list; it's in `.gitignore`).

### Day to day

| To… | Do this (in the `cloudflare` folder) |
|---|---|
| See what it's doing | `npx wrangler tail` (live), or the Worker's *Logs* tab in the Cloudflare dashboard |
| Update after changing the code | `npx wrangler deploy` (if you changed `texts.py`, first run `python cloudflare/scripts/export_texts.py` from the project folder) |
| Change the token | `npx wrangler secret put TELEGRAM_BOT_TOKEN`, then open `/setup` again |
| Test it on your computer | `npm test` (uses saved pages, no internet and no Cloudflare account needed) |
| Pause it | Cloudflare dashboard → your Worker → *Settings → Triggers*: remove the cron trigger (messages are still answered); `npx wrangler deploy` puts it back |
| Move back to your computer | `npx wrangler delete`, then in the project folder `python telegram_setup.py --delete-webhook`, then start the Python bot |

## 10. All Telegram commands

The commands also appear in the bot's **menu** button in Telegram.

| Command | What it does |
|---|---|
| `/start` | Start (or restart after `/stop`) and choose your language. New users then choose their area. |
| `/add <item>` | Add something to your wish list, e.g. `/add bike`. Sending just the name does the same. Max 20 items. |
| `/list` | Shows your area, free-item setting, your items with their price ranges and search words, and the time of the last check. Each item has a **💰** button (change price range) and a **🗑** button (remove it). |
| `/price` | Pick an item and set or change its minimum and maximum price. The bot then sends the current listings that fit the new range. |
| `/free` | Turn free-item alerts on or off. |
| `/check` | Search now instead of waiting for the next 2-hour check. A report follows. |
| `/region` | Change your area. All your searches start fresh in the new area. |
| `/language` | Change the bot's language (also `/lang`, `/sprache`, `/langue`). Your area and list stay. |
| `/sites` | Turn anibis.ch, tutti.ch and ricardo.ch on or off (tap to toggle; at least one stays on). |
| `/remove <item>` | Remove an item by name, e.g. `/remove bike` (the 🗑 buttons in `/list` do the same). |
| `/stop` | Stop all alerts. Your settings are kept; send `/start` to resume. |
| `/help` | Show the list of commands. |

The bot only works in **private chats**. Messages from groups and channels are ignored.

### Languages

The bot speaks **Persian (fa), English (en), French (fr) and German (de)**. New users start in their Telegram app's language if it's one of these, otherwise English, and choose for themselves with `/start` or `/language`.

The language you *search* in doesn't matter: every item is searched in German, French, Italian and English, because listings on these sites are written in those languages.

## 11. Sharing the bot with friends

Your bot can serve your friends and family too. Each person has their **own** language, area, wish list and price ranges.

1. Send them your bot's link: `https://t.me/<your_bot_username>`
2. They open it and send `/start`. That's all.

Things to know:

- **Your computer does the work for everyone.** It must be on, and every extra user means more searches every 2 hours.
- **By default, anyone who finds your bot can use it.** To allow only certain people, add `allowed_chat_ids` to `config.json` (see [step 4](#4-create-configjson)) and restart the bot. Messages from everyone else are ignored.
- **Finding someone's chat id:** your own is saved by `telegram_setup.py`. A friend can find theirs by sending a message to a bot such as [@userinfobot](https://t.me/userinfobot). Chat ids are also stored in `bot.db` (table `users`) once someone has written to your bot.
- If someone blocks the bot, it stops sending to them automatically.

## 12. How it works

- **`bot.py`** keeps running. It answers Telegram messages and, in the background, checks each user whose last check is more than 2 hours old. Requests like `/check`, a new area or a new item go to the front of the queue. Users with the same area and search word share one search.
- **anibis.ch and tutti.ch** run on the same platform. The bot reads their search pages filtered by your area, newest first: up to 5 pages for free items and 2 pages per search word (3 the first time).
- **ricardo.ch** only allows automated visitors (its `robots.txt`) to read the plain search page: no area filter, no extra pages, no "newest first". So the bot reads the first results page for each search word (about 60 items from all of Switzerland) and keeps only items whose **seller's postcode is in your area**. Some Ricardo items near you may be missed, and Ricardo isn't used for free items (it has none).
- **Postcodes** come from the [GeoNames](https://www.geonames.org/) Swiss postcode list (CC BY 4.0), stored in `ch_postcodes.txt`. If the file is missing and can't be downloaded, the bot uses the postcodes it saw on Anibis for your area.
- **Translation** uses Google Translate's free web endpoint, with MyMemory as a fallback. If both fail, the item is searched exactly as you typed it.
- **Everything is stored in `bot.db`**, a SQLite database in the project folder: users, their language, area, sites, wish lists, price ranges, and which listings were already seen and sent.

## 13. Files

| File | Purpose |
|---|---|
| `bot.py` | The Telegram bot: users, commands, the 2-hour checks. **Start this.** |
| `cloudflare/` | The same bot as a Cloudflare Worker: `src/` (code), `wrangler.toml` (settings), `test/` (offline test). |
| `cloudflare/src/texts.json` | The bot's messages for the Worker, made from `texts.py` by `cloudflare/scripts/export_texts.py`. |
| `linux/install_service.sh` / `linux/remove_service.sh` | Run the bot as a systemd service on Linux. |
| `tools/export_to_d1.py` | Copies users and lists from `bot.db` to the Cloudflare database. |
| `tests/fixtures/` | Saved anibis.ch and ricardo.ch search pages, used by the tests. |
| `main.py` | Starts `bot.py`. This is what the Windows scheduled task runs. |
| `anibis.py` | Searches anibis.ch and tutti.ch and finds location options. |
| `ricardo.py` | Searches ricardo.ch. |
| `geo.py` | Swiss postcodes, to keep Ricardo results in your area. |
| `translate.py` | Translates wish-list items into search words. |
| `texts.py` | All bot messages in the four languages. |
| `anibis_alert.py` | Writes the log file (and contains the older one-shot version of the alert). |
| `telegram_setup.py` | One-time check of the token; saves your chat id. `--delete-webhook` disconnects the Cloudflare version. |
| `config.example.json` | Template for `config.json`. |
| `ch_postcodes.txt` | Swiss postcode list from GeoNames. |
| `install_schedule.bat` / `install_schedule.ps1` | Create the Windows scheduled task. |
| `remove_schedule.bat` | Stop the bot and delete the scheduled task. |
| `SCHEDULE.md` | More about the scheduled task. |

Created when you use it (all ignored by git):

| File | Purpose |
|---|---|
| `config.json` | Your bot token and settings. **Secret.** |
| `bot.db` | The database with all users and their settings. **Private.** |
| `anibis_alert.log` | What the bot did, including errors. Look here first if something seems wrong. |

## 14. Privacy: never commit config.json or bot.db

- `config.json` contains your **bot token**. Anyone with it can take over your bot.
- `bot.db` contains **every user's chat id, name, area and wish list**.
- `anibis_alert.log` contains chat ids too.

All three are listed in `.gitignore`, so `git add .` skips them. So are `d1_import.sql` (made by `tools/export_to_d1.py`) and `cloudflare/.dev.vars`. On Cloudflare the token is stored with `wrangler secret put`, never in `wrangler.toml`. Keep it that way: don't remove them from `.gitignore`, and don't force-add them. Before pushing, `git status` should never show them.

If you ever push your token by mistake, revoke it immediately in @BotFather (`/revoke`), even if you delete the commit afterwards.

## 15. Troubleshooting

| Problem | What to do |
|---|---|
| The bot doesn't answer | Make sure it's running (a terminal with `python bot.py`, or the scheduled task). Then look at `anibis_alert.log`. |
| `Put your telegram_bot_token in config.json first.` | `config.json` is missing or still has the placeholder token. See [step 4](#4-create-configjson). |
| `This bot is connected to a webhook…` in the log | The Cloudflare version is answering this bot. Only one copy can. To run it on your computer instead: `python telegram_setup.py --delete-webhook` (and `npx wrangler delete` in `cloudflare/`). |
| Cloudflare: the bot doesn't answer | Open `https://<your worker>/setup` and look for ❌. Then `npx wrangler tail` in `cloudflare/` and send the bot a message to see errors. |
| Cloudflare: `TELEGRAM_BOT_TOKEN is not set` | Run `npx wrangler secret put TELEGRAM_BOT_TOKEN` in `cloudflare/`. |
| Cloudflare: `running scripts is disabled on this system` (PowerShell) | Use Command Prompt (`cmd`) instead of PowerShell for the `npm` / `npx` commands. |
| `bot is already running, exiting` in the log | Normal: a copy is already running, so the new one stops. To restart after changing files, stop the old copy first (close its window, or run `remove_schedule.bat` and then `install_schedule.bat`). If a copy you started by hand is still running, end `pythonw.exe` / `python.exe` in Task Manager. |
| `'python' is not recognized…` | Python isn't on PATH. Reinstall it and tick **Add Python to PATH**, or try `py bot.py`. |
| The bot can't find my town | Write it as Anibis spells it (`Geneve`, `Zurich`, `Biel`), or use the canton name. |
| An item finds nothing | Check `/list` to see the search words. Try a simpler or more common word, or a wider area with `/region`. |
| No messages for a while | Maybe nothing new was posted. `/check` searches now and `/list` shows the last check time. |
| A site shows `❌ error` in the report | The site may be down or have changed. The other sites keep working; details are in `anibis_alert.log`. |
| Start over completely | Stop the bot, delete `bot.db` and start it again. **Everyone's** settings are lost. |
