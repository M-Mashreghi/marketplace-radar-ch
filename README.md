# Anibis Alarm – Telegram bot for new listings on Anibis, tutti and Ricardo

A Telegram bot that runs on your Windows PC and watches **anibis.ch**,
**tutti.ch** and **ricardo.ch** for its users. **Anyone** who opens the bot in Telegram can use it, and each person
has their own settings:

- **Language:** Persian, English, French or German (changeable any time)
- **Area:** a town, a town plus a radius (5 / 10 / 20 / 50 km), a region or a canton
- **Free items:** new "Gratis" listings in their area (on by default)
- **Wish list:** things they want, typed in any language
- **Sites:** Anibis, tutti and Ricardo (each can be switched on or off with `/sites`)

Every **2 hours** the bot searches the sites for every user. It sends each new
listing with photo, price, place, description, the site it came from and a link.
Each listing is sent only once, even if the same ad is on two sites.

### What each site supports

| | anibis.ch | tutti.ch | ricardo.ch |
|---|---|---|---|
| Your area (town, radius, region, canton) | ✅ | ✅ | ✅ by the seller's postcode (see below) |
| Free items | ✅ | ✅ | ❌ (Ricardo has no free listings) |
| Wish list | ✅ | ✅ | ✅ |
| Newest listings first | ✅ | ✅ | ❌ Ricardo's own order |

Ricardo's rules for automated visitors (its robots.txt) only allow the plain
search page. The bot isn't allowed to add an area filter, more pages or
"newest first" there. So on Ricardo it reads the first results page for each
wish-list word (about 60 items from all of Switzerland) and keeps only the
items whose seller postcode is in your area. Some Ricardo items in your area
may therefore be missed. To know where postcodes are, the bot downloads the
Swiss postcode list from GeoNames once (`ch_postcodes.txt`). If that fails,
it uses the postcodes it saw on Anibis for your area. Anibis and tutti have
no such limit for search pages.

---

## First-time setup (about 5 minutes)

### 1. Install Python
If you don't have it yet, install Python from <https://www.python.org/downloads/>.
During setup, tick **"Add Python to PATH"**. Nothing else needs installing.

### 2. Create your Telegram bot
1. In Telegram, open **@BotFather** and send `/newbot`.
2. Choose a name and a username (the username must end in `bot`).
3. BotFather replies with a **token** that looks like `123456789:AAH...`.
   Keep it secret, because anyone with it can control your bot.

### 3. Put the token in config.json
Open `config.json` in this folder with Notepad:

```json
{
  "telegram_bot_token": "123456789:AAH...your token...",
  "telegram_chat_id": ""
}
```

`telegram_chat_id` is only used by `telegram_setup.py`, and you can leave it empty.

**Optional:** to let only certain people use the bot, add their chat ids:
`"allowed_chat_ids": ["111111111", "222222222"]`. Without this line, everyone can use it.

### 4. Check the connection (optional)
Send your bot any message in Telegram, then run this in this folder:

```
python telegram_setup.py
```

It checks the token and sends you a test message. To open a terminal in this
folder, click the File Explorer address bar, type `cmd` and press Enter.

### 5. Start the bot

```
python bot.py
```

Leave this window open while you try it out. In Telegram:
1. Send `/start` and pick your **language**.
2. Type your **town or canton**, for example `Lausanne`. The bot looks it up on
   Anibis and shows every option it found:
   - 📍 Lausanne (the town only)
   - ⭕ Lausanne + 5 / 10 / 20 / 50 km
   - 🗺 Lausanne region
   - 🏔 the canton (Vaud)

   Tap the one you want.
3. Send the **name of something you want**, in any language, for example
   `دوچرخه`, `bike` or `canapé`. The bot translates it into German, French,
   Italian and English, shows you the words it will search for, and adds it
   when you tap ✅.

When you choose an area, the bot sends **all free items listed there now**.
When you add an item, it sends **everything listed now** for it on all three
sites, free and paid. Every listing is its own message with photo, price,
place, description and its link (up to 100 per search the first time, then
up to 50 new ones per check).

Only listings whose title is really about the item are sent: every word of
one of the search words must be in the title ("power strip" needs both
words), or one long specific word is enough ("multiprise"). Listings with
another common name for the item (from the translator's alternatives, for
example "Mehrfachsteckdose" for "Bloc multiprise") are marked 🔍 similar name.

After you choose an area, and after every check (`/check` and each automatic
2-hour check), the bot sends a short **report for all three sites**: whether
your area was found there, a link to the search, how many listings it noted or
found new, and any error. Ricardo always shows "all of Switzerland" because it
doesn't allow an area filter.

### 6. Make it run automatically
Close the terminal window (this stops the bot you started by hand), then
double-click **`install_schedule.bat`**. From now on the bot starts when you log
in to Windows, runs in the background without a window, and restarts if it
crashes. See `SCHEDULE.md` for details. The PC must be on for the bot to work.

---

## Telegram commands

| Command | What it does |
|---|---|
| `/start` | Start, choose language and area |
| `/add <item>` | Add something you want (or just send its name) |
| `/list` | Your area, your items and the last check time, with 🗑 buttons to remove items |
| `/free` | Turn free-item alerts on or off |
| `/check` | Search now instead of waiting for the next 2-hour check |
| `/region` | Change your area |
| `/language` | Change the bot's language |
| `/sites` | Turn Anibis, tutti and Ricardo on or off |
| `/stop` | Stop all alerts (send `/start` to resume) |
| `/help` | Show the commands |

---

## How it works

- `bot.py` stays running. It answers Telegram messages and, every 2 hours,
  searches each site once for each user's free items and once for each word
  on their list.
- The search on these sites matches the words written in a listing, and listings are in
  German, French, Italian or English. That's why every item is translated and
  searched in all four languages, so `دوچرخه` finds "Velo", "vélo",
  "bicicletta" and "bicycle". Translation uses Google Translate's free service.
- Everything is stored in **`bot.db`**, a small SQLite database in this folder.
  It holds users, languages, areas, wish lists and the listings already sent.

## Files in this folder

| File | Purpose |
|---|---|
| `bot.py` | The Telegram bot (users, commands, the 2-hour checks) |
| `anibis.py` | Searches Anibis and tutti (same platform) and finds location options |
| `ricardo.py` | Searches Ricardo |
| `geo.py` | Swiss postcodes, to keep Ricardo results in your area |
| `translate.py` | Translates wish-list items for searching |
| `texts.py` | Bot messages in the four languages |
| `main.py` | Starts the bot. Task Scheduler runs this file |
| `anibis_alert.py` | Logging, plus a backup way to read Anibis pages |
| `telegram_setup.py` | One-time check of the token |
| `config.json` | Your bot token (keep it private) |
| `bot.db` | The database (created automatically) |
| `anibis_alert.log` | What the bot did, including errors. Look here first if something seems wrong |
| `install_schedule.bat` / `remove_schedule.bat` | Turn automatic start on or off |

`bot_state.json` and `debug_search.html` are from the earlier version. You can delete them.

## Troubleshooting

- **The bot doesn't answer:** make sure it's running, either in a terminal
  or through the scheduled task. Then check `anibis_alert.log`.
- **"bot is already running" in the log:** that's normal. A copy is already
  running, so the new one exits. After updating the files, stop the old copy
  first: close its window, or run `remove_schedule.bat` and then
  `install_schedule.bat` again.
- **The bot can't find a town:** write it as Anibis spells it, for example
  `Geneve`, `Zurich` or `Biel`, or use the canton name.
- **No messages for a while:** maybe nothing new was posted. `/check` searches
  now, and `/list` shows when it last searched.
- **Start over completely:** stop the bot, delete `bot.db` and start it again.
  Everyone's settings will be lost.
