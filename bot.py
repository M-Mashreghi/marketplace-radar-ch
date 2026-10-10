"""
Anibis / tutti / Ricardo Telegram bot – many users, four languages.

Each user picks a language (Persian, English, French, German), an area on
Anibis (town, town + radius, region or canton) and the things they want.
Every 2 hours the bot searches Anibis for each user and sends new listings
with photo, price, place, description and link:
  * new FREE listings in their area (can be turned off with /free)
  * new listings for each item on their list; the item is translated to
    German, French, Italian and English, and all versions are searched

Everything is stored in bot.db (SQLite) in this folder.

Start:  python bot.py   (main.py / sada.py also start it, for Task Scheduler)
Needs:  telegram_bot_token in config.json. Optional in config.json:
        "allowed_chat_ids": ["123", ...] to limit who may use the bot.
Only uses the Python standard library.
"""

import difflib
import html
import json
import queue
import re
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anibis  # noqa: E402
import geo  # noqa: E402
import ricardo  # noqa: E402
import translate  # noqa: E402
from anibis_alert import print  # noqa: E402,A001  (console + anibis_alert.log)
from texts import LANGS, t  # noqa: E402

CONFIG_FILE = HERE / "config.json"
DB_FILE = HERE / "bot.db"
CHECK_EVERY_HOURS = 2
MAX_WISHES = 20
MAX_ALERTS_PER_CHECK = 50   # new listings per user per check, so a broken page can't flood anyone
FIRST_MAX = 100             # "everything listed now" for a new area or item, per search
FREE_PAGES = 5              # free items: read up to 5 pages (~150 listings) per check
WISH_PAGES = 2
FIRST_WISH_PAGES = 3        # a new item: list what's there now, up to 3 pages per word
ALL_SITES = ("anibis", "tutti", "ricardo")
FREE_SITES = ("anibis", "tutti")   # Ricardo has no free listings and no area filter
SITE_NAMES = {"anibis": "anibis.ch", "tutti": "tutti.ch", "ricardo": "ricardo.ch"}
LOCK_PORT = 47613           # only one copy of the bot may run at a time


# ------------------------------------------------------------------ database

class DB:
    def __init__(self, path):
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock, self.con:
            self.con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id    TEXT PRIMARY KEY,
                name       TEXT,
                lang       TEXT,
                loc_id     TEXT,
                loc_radius INTEGER,
                loc_label  TEXT,
                free_on    INTEGER DEFAULT 1,
                active     INTEGER DEFAULT 1,
                pending    TEXT,
                last_check REAL DEFAULT 0,
                created    REAL
            );
            CREATE TABLE IF NOT EXISTS wishes (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                keyword TEXT,
                terms   TEXT,
                created REAL
            );
            CREATE TABLE IF NOT EXISTS seen (
                chat_id    TEXT,
                search_key TEXT,
                listing_id TEXT,
                PRIMARY KEY (chat_id, search_key, listing_id)
            );
            CREATE TABLE IF NOT EXISTS sent (
                chat_id    TEXT,
                listing_id TEXT,
                sent_at    REAL,
                PRIMARY KEY (chat_id, listing_id)
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """)
            cols = [r[1] for r in self.con.execute("PRAGMA table_info(users)")]
            if "sites" not in cols:
                self.con.execute("ALTER TABLE users ADD COLUMN sites TEXT DEFAULT 'anibis,tutti,ricardo'")
            if "ricardo_area" not in cols:
                self.con.execute("ALTER TABLE users ADD COLUMN ricardo_area TEXT")
            wcols = [r[1] for r in self.con.execute("PRAGMA table_info(wishes)")]
            if "similar" not in wcols:
                self.con.execute("ALTER TABLE wishes ADD COLUMN similar TEXT")
            for col in ("min_price", "max_price"):
                if col not in wcols:
                    self.con.execute(f"ALTER TABLE wishes ADD COLUMN {col} REAL")

    def q(self, sql, args=()):
        with self.lock:
            return self.con.execute(sql, args).fetchall()

    def x(self, sql, args=()):
        with self.lock, self.con:
            return self.con.execute(sql, args)

    # users
    def user(self, chat_id):
        rows = self.q("SELECT * FROM users WHERE chat_id=?", (chat_id,))
        return dict(rows[0]) if rows else None

    def ensure_user(self, chat_id, name, lang):
        if not self.user(chat_id):
            self.x("INSERT INTO users (chat_id, name, lang, created) VALUES (?,?,?,?)",
                   (chat_id, name, lang, time.time()))
        return self.user(chat_id)

    def set(self, chat_id, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE users SET {cols} WHERE chat_id=?", (*fields.values(), chat_id))

    def pending(self, user):
        try:
            return json.loads(user.get("pending") or "null") or {}
        except ValueError:
            return {}

    def set_pending(self, chat_id, data):
        self.set(chat_id, pending=json.dumps(data, ensure_ascii=False) if data else None)

    # wishes
    def wishes(self, chat_id):
        return [dict(r) for r in self.q("SELECT * FROM wishes WHERE chat_id=? ORDER BY id", (chat_id,))]

    def add_wish(self, chat_id, keyword, terms, similar=None):
        cur = self.x("INSERT INTO wishes (chat_id, keyword, terms, similar, created) VALUES (?,?,?,?,?)",
                     (chat_id, keyword, json.dumps(terms, ensure_ascii=False),
                      json.dumps(similar or [], ensure_ascii=False), time.time()))
        return cur.lastrowid

    def wish(self, chat_id, wish_id):
        rows = self.q("SELECT * FROM wishes WHERE chat_id=? AND id=?", (chat_id, wish_id))
        return dict(rows[0]) if rows else None

    def set_price(self, chat_id, wish_id, lo, hi):
        self.x("UPDATE wishes SET min_price=?, max_price=? WHERE chat_id=? AND id=?", (lo, hi, chat_id, wish_id))
        # Start this item fresh, so listings that now fit the range are sent.
        self.x("DELETE FROM seen WHERE chat_id=? AND search_key LIKE ?", (chat_id, f"w{wish_id}@%"))

    def del_wish(self, chat_id, wish_id):
        rows = self.q("SELECT keyword FROM wishes WHERE chat_id=? AND id=?", (chat_id, wish_id))
        self.x("DELETE FROM wishes WHERE chat_id=? AND id=?", (chat_id, wish_id))
        self.x("DELETE FROM seen WHERE chat_id=? AND search_key LIKE ?", (chat_id, f"w{wish_id}@%"))
        return rows[0]["keyword"] if rows else None

    # seen / sent
    def seen_ids(self, chat_id, key):
        return {r["listing_id"] for r in self.q(
            "SELECT listing_id FROM seen WHERE chat_id=? AND search_key=?", (chat_id, key))}

    def mark_seen(self, chat_id, key, ids):
        with self.lock, self.con:
            self.con.executemany("INSERT OR IGNORE INTO seen VALUES (?,?,?)",
                                 [(chat_id, key, i) for i in ids])

    def was_sent(self, chat_id, listing_id):
        return bool(self.q("SELECT 1 FROM sent WHERE chat_id=? AND listing_id=?", (chat_id, listing_id)))

    def mark_sent(self, chat_id, listing_id):
        self.x("INSERT OR IGNORE INTO sent VALUES (?,?,?)", (chat_id, listing_id, time.time()))

    def reset_searches(self, chat_id):
        self.x("DELETE FROM seen WHERE chat_id=?", (chat_id,))

    # meta
    def meta(self, key, default=None):
        rows = self.q("SELECT value FROM meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_meta(self, key, value):
        self.x("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, str(value)))


# ------------------------------------------------------------------ Telegram

class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method, http_timeout=40, **params):
        data = urllib.parse.urlencode(
            {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
             for k, v in params.items() if v is not None}).encode()
        try:
            with urllib.request.urlopen(self.base + method, data=data, timeout=http_timeout) as r:
                res = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            res = json.loads(e.read().decode() or "{}")
        if not res.get("ok"):
            raise RuntimeError(f"{method}: {res.get('description')}")
        return res["result"]

    def send(self, chat, text, buttons=None, preview=False):
        return self.call("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
                         disable_web_page_preview="false" if preview else "true",
                         reply_markup={"inline_keyboard": buttons} if buttons else None)


def esc(s):
    return html.escape(str(s or ""), quote=False)


def caption(item, why, lang):
    parts = [f"🆕 <b>{esc(item['title'])}</b>", f"🏷 {SITE_NAMES.get(item.get('site'), 'anibis.ch')}"]
    if item.get("price"):
        parts.append(f"💰 {esc(item['price'])}")
    if item.get("place"):
        parts.append(f"📍 {esc(item['place'])}")
    if why:
        parts.append(t("match", lang, what=esc(why)))
    desc = (item.get("description") or "").strip()
    if desc:
        parts += ["", esc(desc[:450] + ("…" if len(desc) > 450 else ""))]
    parts += ["", f'<a href="{html.escape(item["url"])}">{t("open", lang, site=SITE_NAMES.get(item.get("site"), "anibis.ch"))}</a>',
              esc(item["url"])]
    text = "\n".join(parts)
    if len(text) > 1024:  # Telegram's photo caption limit
        text = "\n".join(parts[:5] + [""] + parts[-2:])
    return text


def send_listing(tg, chat, item, why, lang):
    cap = caption(item, why, lang)
    if item.get("photo"):
        try:
            return tg.call("sendPhoto", chat_id=chat, photo=item["photo"], caption=cap, parse_mode="HTML")
        except Exception as e:
            print(f"[!] sendPhoto failed, sending text: {e}")
    return tg.call("sendMessage", chat_id=chat, text=cap, parse_mode="HTML")


# ------------------------------------------------------------------ searching

def loc_label(opt, lang):
    key = {"city": "opt_city", "region": "opt_region", "canton": "opt_canton"}[opt["kind"]]
    if opt["kind"] == "city" and opt.get("radius"):
        key = "opt_radius"
    return re.sub(r"^\W+", "", t(key, lang, name=opt["name"], km=opt.get("radius") or "")).strip()


def user_sites(user):
    sites = [x for x in (user.get("sites") or ",".join(ALL_SITES)).split(",") if x in ALL_SITES]
    return sites


def user_searches(db, user):
    """(key, label, [terms], [similar names], free_only, pages, (min, max price)) for every search."""
    out = []
    if user["free_on"]:
        out.append(("free", t("free_label", user["lang"]), [None], [], True, FREE_PAGES, (None, None)))
    for w in db.wishes(user["chat_id"]):
        terms = json.loads(w["terms"]) or [w["keyword"]]
        if w.get("similar") is None:  # item added by an older version: look the names up once
            try:
                _, similar = translate.expand(w["keyword"], user["lang"] or "en")
            except Exception:
                similar = []
            db.x("UPDATE wishes SET similar=? WHERE id=?", (json.dumps(similar, ensure_ascii=False), w["id"]))
        else:
            similar = json.loads(w["similar"] or "[]")
        out.append((f"w{w['id']}", w["keyword"], terms, similar, False, WISH_PAGES,
                    (w.get("min_price"), w.get("max_price"))))
    return out


def price_value(item):
    """The listing's price in CHF as a number: 0 for free, None if unknown.
    For Ricardo the buy-now price counts, else the current bid."""
    p = item.get("price") or ""
    if anibis.is_free(item):
        return 0.0
    if "🛒" in p:
        p = p.split("🛒", 1)[1]
    m = re.search(r"\d[\d'’ ]*(?:[.,]\d{1,2})?", p)
    if not m:
        return None
    try:
        return float(re.sub(r"['’ ]", "", m.group(0)).replace(",", "."))
    except ValueError:
        return None


def in_price_range(item, lo, hi):
    if lo is None and hi is None:
        return True
    v = price_value(item)
    if v is None:  # "price on request" and the like: keep, it may fit
        return True
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def parse_price_range(text):
    """'20-100', '20 100', '-100' (max only), '20-' (min only), '0' or '-' (no limit).
    Returns (min, max) or None if it can't be read."""
    text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    text = re.sub(r"(?i)chf|fr\.?|\.-|['’]", "", text).strip()
    text = re.sub(r"\s*[-–—]\s*|\s+(?:to|bis|à|a|تا)\s+", "-", text)
    text = re.sub(r"\s+", "-", text)
    if text in ("", "-", "0", "0-0"):
        return (None, None)
    if re.fullmatch(r"\d+(?:[.,]\d+)?", text):
        text = "-" + text  # one number = the most you'll pay
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)?-(\d+(?:[.,]\d+)?)?", text)
    if not m:
        return None
    lo, hi = (float(x.replace(",", ".")) if x else None for x in m.groups())
    lo = lo or None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return (lo, hi)


def price_label(lo, hi, lang):
    f = lambda v: f"{v:,.0f}".replace(",", "'")  # noqa: E731
    if lo is None and hi is None:
        return t("price_any", lang)
    if hi is None:
        return t("price_from", lang, lo=f(lo))
    if lo is None:
        return t("price_upto", lang, hi=f(hi))
    return f"{f(lo)}–{f(hi)} CHF"


STOP_WORDS = {"les", "des", "une", "pour", "avec", "sans", "und", "der", "die", "das", "ein", "eine",
              "mit", "von", "fur", "the", "and", "for", "with", "del", "della", "per", "con", "uno", "una"}
LONG_WORD = 10   # a word this long is specific on its own ("multiprise", "bicyclette")


def _words(s):
    return [w for w in anibis.slugify(s).split("-") if len(w) >= 3 and w not in STOP_WORDS]


PLURAL_ENDINGS = ("s", "es", "e", "en", "n", "x")


def _word_in(w, title_words):
    """w, its plural, or a compound containing it is among the title's words."""
    for x in title_words:
        if x == w or (len(w) >= 6 and w in x):
            return True
        if x.startswith(w) and x[len(w):] in PLURAL_ENDINGS:
            return True
        if len(x) >= 4 and w.startswith(x) and w[len(x):] in PLURAL_ENDINGS:
            return True
        if len(w) >= 5 and len(x) == len(w) and x[:-1] == w[:-1] and x[-1] in "aeio" and w[-1] in "aeio":
            return True  # Italian singular / plural: bicicletta, biciclette
    return False


def title_matches(title, term):
    """Is this listing really about `term`? Every word of the term must be in
    the title ("power strip" needs both words), except that one long, specific
    word is enough ("multiprise" for "bloc multiprise")."""
    words, tw = _words(term), _words(title)
    if not words or not tw:
        return False
    if any(len(w) >= LONG_WORD and _word_in(w, tw) for w in words):
        return True
    return all(_word_in(w, tw) for w in words)


def classify(title, terms, similar):
    """'exact', 'similar' or None (not related: dropped)."""
    if any(title_matches(title, x) for x in terms):
        return "exact"
    if any(title_matches(title, x) for x in similar):
        return "similar"
    return None


def search_words(terms, similar):
    """Everything to type into the sites' search box for one item."""
    out, keys = [], set()
    longs = [w for x in terms if len(_words(x)) > 1 for w in _words(x) if len(w) >= LONG_WORD]
    for x in list(terms) + longs + list(similar):
        k = anibis.slugify(x)
        if k and k not in keys:
            keys.add(k)
            out.append(x)
    return out


def ricardo_area(db, user):
    """Where the user's area is, for keeping Ricardo results by seller postcode."""
    if user.get("ricardo_area"):
        try:
            return json.loads(user["ricardo_area"])
        except ValueError:
            pass
    kind = (user["loc_id"] or "").split("-")[1] if (user["loc_id"] or "").count("-") >= 2 else "city"
    name = (user["loc_id"] or "").split("-", 2)[-1]
    listings = anibis.search_new(None, user["loc_id"], user["loc_radius"], set(), 3, site="anibis")
    area = geo.make_area(kind, name, user["loc_radius"], listings)
    if area.get("lat") or area.get("zips"):
        db.set(user["chat_id"], ricardo_area=json.dumps(area))
        return area
    return None


def run_search(site, term, user, seen, pages, first_time, cache, area=None):
    """One word on one site -> {"items", "places", "all"}.

    first_time: everything listed now (several pages); otherwise only new ones.
    Ricardo has no area filter on the site, so its results (all of Switzerland)
    are kept only when the seller's postcode is in the user's area.
    """
    ck = (site, term, user["loc_id"], user["loc_radius"], first_time, pages)
    if site == "ricardo":
        if ck not in cache:
            items = ricardo.search(term)
            kept = [i for i in items if geo.in_area(area, i.get("postcode"))] if area else items
            cache[ck] = {"items": kept, "places": None, "all": len(items)}
        return cache[ck]
    if ck in cache:
        return cache[ck]
    if first_time:
        res = anibis.search(term, user["loc_id"], user["loc_radius"], site=site)
        items, ids = list(res.listings), {i["id"] for i in res.listings}
        for page in range(2, pages + 1):
            if len(res.listings) < 20:
                break  # that was the last page
            time.sleep(1)
            res2 = anibis.search(term, user["loc_id"], user["loc_radius"], page, site=site)
            if res2.page != page:
                break
            more = [i for i in res2.listings if i["id"] not in ids]
            if not more:
                break
            items += more
            ids.update(i["id"] for i in more)
            if len(res2.listings) < 20:
                break
        out = {"items": items, "places": [l.get("name") for l in res.localities if l.get("name")],
               "all": res.total}
    else:
        out = {"items": anibis.search_new(term, user["loc_id"], user["loc_radius"], seen, pages, site=site),
               "places": None, "all": None}
    cache[ck] = out
    return out


def site_search_url(site, term, user):
    if site == "ricardo":
        return ricardo.search_url(term) if term else ricardo.BASE
    return anibis.search_url(term, user["loc_id"], user["loc_radius"], site=site)


def fingerprint(item):
    """Same ad posted on several sites -> same fingerprint, so it's sent once."""
    return "fp:" + re.sub(r"\W+", "", f"{item.get('title')}|{item.get('price')}|{item.get('place')}".lower())[:120]


def site_link(site, url):
    return f'<a href="{html.escape(url)}">{SITE_NAMES[site]}</a>'


def build_report(user, rows, sent, kind, area=None):
    """One message: what happened on every site for every search."""
    lang = user["lang"] or "en"
    lines = [t("rep_head_" + kind, lang, label=esc(user["loc_label"]))]
    any_first = False
    for label, site_rows in rows:
        lines += ["", f"<b>{esc(label)}</b>"]
        for r in site_rows:
            name = site_link(r["site"], r["url"])
            if r["status"] == "off":
                lines.append(t("rep_off", lang, site=SITE_NAMES[r["site"]]))
            elif r["status"] == "no_free":
                lines.append(t("rep_ricardo_free", lang, site=name))
            elif r["status"] == "error":
                lines.append(t("rep_err", lang, site=name, err=esc(r["err"])[:120]))
            else:
                if r["site"] == "ricardo":
                    where = (t("rep_ric_area", lang, label=esc(user["loc_label"]), d=geo.describe(area),
                               all=r.get("all") or 0) if area else t("rep_all_ch", lang))
                elif r["places"] is not None and not r["places"]:
                    where = t("rep_noloc", lang)
                else:
                    where = esc(", ".join(r["places"]) if r["places"] else user["loc_label"])
                key = "rep_first" if r["first"] else "rep_ok"
                any_first = any_first or r["first"]
                lines.append(t(key, lang, site=name, where=where, n=r["n"], new=r["new"]))
    if kind == "init" and not any(label != t("free_label", lang) for label, _ in rows):
        lines += ["", t("rep_no_wishes", lang)]
    lines.append("")
    if any_first:
        lines.append(t("rep_first_note", lang))
    if kind not in ("init", "wish"):
        lines.append(t("rep_sent", lang, n=sent))
    return "\n".join(lines)


def check_user(tg, db, user, report=None, cache=None, only=None):
    """Search all of a user's sites, send listings and (optionally) a report.

    A search done for the first time (new area, new item) sends everything
    listed now; later checks send only new listings. Each listing is its own
    message with photo, details and link. Listings whose title isn't really
    about the item are dropped.
    report: None, "init" (new area), "wish" (new item), "check" (/check),
    "auto" (the 2-hourly run). only: just this search key (e.g. "w12").
    Returns number of listings sent.
    """
    chat, lang = user["chat_id"], user["lang"] or "en"
    if not user["loc_id"]:
        return 0
    cache = {} if cache is None else cache
    sites = user_sites(user)
    area = None
    if "ricardo" in sites:
        try:
            area = ricardo_area(db, user)
        except Exception as e:
            print(f"[!] Ricardo area for {chat} failed: {e}")
    sent, rows = 0, []
    for key, label, terms, similar, free_only, pages, (lo, hi) in user_searches(db, user):
        if only and key != only:
            continue
        words = [None] if free_only else search_words(terms, similar)
        to_send, site_rows, any_first = [], [], False
        for site in ALL_SITES:
            url = site_search_url(site, terms[0], user)
            if site not in sites:
                site_rows.append({"site": site, "status": "off", "url": url})
                continue
            if free_only and site not in FREE_SITES:
                site_rows.append({"site": site, "status": "no_free", "url": url})
                continue
            skey = f"{key}@{site}"
            seen = db.seen_ids(chat, skey)
            first_time = not seen
            any_first = any_first or first_time
            n_pages = pages if not first_time or free_only else FIRST_WISH_PAGES
            ids, got, places, errors, total = set(), {}, None, [], 0
            for word in words:
                try:
                    res = run_search(site, word, user, seen, n_pages, first_time, cache, area)
                except Exception as e:
                    print(f"[!] {site} search failed ({label} / {word}): {e}")
                    errors.append(str(e))
                    continue
                if res["places"] is not None:
                    places = sorted(set((places or []) + res["places"]))
                total += res["all"] or 0
                for i in res["items"]:
                    ids.add(i["id"])
                    if i["id"] in seen or i["id"] in got:
                        continue
                    if free_only:
                        if anibis.is_free(i):
                            got[i["id"]] = (i, "exact")
                        continue
                    kind = classify(i["title"], terms, similar)
                    if kind and in_price_range(i, lo, hi):
                        got[i["id"]] = (i, kind)
                time.sleep(1)
            if errors and not ids:
                site_rows.append({"site": site, "status": "error", "err": errors[0], "url": url})
                continue
            db.mark_seen(chat, skey, ids or {"-"})
            items = sorted(got.values(), key=lambda x: x[1] != "exact")  # exact matches first
            to_send += items
            n_sim = sum(1 for _, k in items if k == "similar")
            site_rows.append({"site": site, "status": "ok", "first": first_time, "n": len(items),
                              "new": 0 if first_time else len(items), "sim": n_sim, "places": places,
                              "url": url, "all": total})
        rows.append((label + ("" if free_only or (lo is None and hi is None)
                              else f" · 💰 {price_label(lo, hi, lang)}"), site_rows))
        # One message per listing: photo, details and its own link.
        limit = FIRST_MAX if any_first else MAX_ALERTS_PER_CHECK
        fresh = []
        for item, kind in to_send:
            sid, fp = f"{item['site']}:{item['id']}", fingerprint(item)
            if not db.was_sent(chat, sid) and not db.was_sent(chat, fp) and fp not in {fingerprint(f[0]) for f in fresh}:
                fresh.append((item, kind))
        if any_first and fresh:
            try:
                tg.send(chat, t("now_head", lang, label=esc(label), n=min(len(fresh), limit)))
            except Exception as e:
                print(f"[!] could not send to {chat}: {e}")
        for n, (item, kind) in enumerate(fresh):
            if n >= limit:
                try:
                    tg.send(chat, t("now_more", lang, n=limit, rest=len(fresh) - limit))
                except Exception:
                    pass
                break
            sid, fp = f"{item['site']}:{item['id']}", fingerprint(item)
            why = label + (" · " + t("similar_tag", lang) if kind == "similar" else "")
            try:
                send_listing(tg, chat, item, why, lang)
                db.mark_sent(chat, sid)
                db.mark_sent(chat, fp)
                sent += 1
                time.sleep(1.2)
            except Exception as e:
                print(f"[!] could not send {sid} to {chat}: {e}")
                if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    db.set(chat, active=0)
                    return sent
    db.set(chat, last_check=time.time())
    if report:
        try:
            tg.send(chat, build_report(db.user(chat), rows, sent, report, area))
        except Exception as e:
            print(f"[!] report to {chat} failed: {e}")
    return sent


def checker(tg, db, jobs):
    """Background thread: the regular checks plus /check, new area and new item.

    Users are checked one at a time, and requests waiting in `jobs` always go
    first, so with many users nobody waits for a whole round to finish.
    Searches are shared within a round: users with the same area and word
    cost one request, not one each.
    """
    cache = {}
    while True:
        try:
            job = jobs.get(timeout=1 if cache else 60)
        except queue.Empty:
            job = None
        try:
            if job:  # ("check", chat) /check, ("init", chat) new area, ("wish", chat, key) new item
                kind, chat = job[0], job[1]
                user = db.user(chat)
                if user:
                    check_user(tg, db, user, report=kind, only=job[2] if len(job) > 2 else None)
                continue
            due = db.q("SELECT * FROM users WHERE active=1 AND loc_id IS NOT NULL AND last_check < ? "
                       "ORDER BY last_check LIMIT 1", (time.time() - CHECK_EVERY_HOURS * 3600,))
            if not due:
                cache = {}  # round finished
                continue
            n = check_user(tg, db, dict(due[0]), report="auto", cache=cache)
            print(f"checked {due[0]['chat_id']}: {n} sent")
        except Exception as e:
            print(f"[!] checker: {e}")
            time.sleep(5)


# ------------------------------------------------------------------ conversation

def site_buttons(user):
    on = user_sites(user)
    return [[{"text": f"{'✅' if s in on else '⬜'} {SITE_NAMES[s]}", "callback_data": f"site:{s}"}]
            for s in ALL_SITES]


def lang_buttons():
    return [[{"text": label, "callback_data": f"lang:{code}"}] for code, label in LANGS.items()]


def yes_no(lang, tag):
    return [[{"text": t("yes", lang), "callback_data": f"{tag}:yes"},
             {"text": t("no", lang), "callback_data": f"{tag}:no"}]]


def ask_region(tg, db, user):
    db.set_pending(user["chat_id"], {"type": "await_region"})
    tg.send(user["chat_id"], t("ask_region", user["lang"]))


def handle_region_text(tg, db, user, text):
    chat, lang = user["chat_id"], user["lang"]
    tg.send(chat, t("searching_loc", lang, q=esc(text)))
    options = anibis.find_locations(text)
    if not options:
        db.set_pending(chat, {"type": "await_region"})
        tg.send(chat, t("loc_not_found", lang, q=esc(text)))
        return
    db.set_pending(chat, {"type": "choose_loc", "options": options})
    buttons = []
    for i, opt in enumerate(options):
        label = t({"city": "opt_city", "region": "opt_region", "canton": "opt_canton"}[opt["kind"]]
                  if not opt.get("radius") else "opt_radius", lang, name=opt["name"], km=opt.get("radius") or "")
        if opt.get("total"):
            label += f" · {t('listings_count', lang, n=format(opt['total'], ',').replace(',', chr(39)))}"
        buttons.append([{"text": label, "callback_data": f"loc:{i}"}])
    buttons.append([{"text": t("opt_other", lang), "callback_data": "loc:other"}])
    tg.send(chat, t("loc_choose", lang), buttons=buttons)


def start_wish(tg, db, user, keyword):
    chat, lang = user["chat_id"], user["lang"]
    keyword = keyword.strip()[:60]
    if not user["loc_id"]:
        tg.send(chat, t("need_region", lang))
        return
    wishes = db.wishes(chat)
    if any(w["keyword"].lower() == keyword.lower() for w in wishes):
        tg.send(chat, t("already", lang, kw=esc(keyword)))
        return
    if len(wishes) >= MAX_WISHES:
        tg.send(chat, t("too_many", lang, n=MAX_WISHES))
        return
    tg.send(chat, t("translating", lang, kw=esc(keyword)))
    terms, similar = translate.expand(keyword, lang)
    db.set_pending(chat, {"type": "confirm_wish", "keyword": keyword, "terms": terms, "similar": similar})
    text = t("confirm_terms", lang, kw=esc(keyword), terms=esc(" · ".join(terms)))
    if similar:
        text = text.replace("\n\n", "\n" + t("confirm_similar", lang, names=esc(" · ".join(similar))) + "\n\n", 1)
    tg.send(chat, text, buttons=yes_no(lang, "wish"))


def show_list(tg, db, user):
    chat, lang = user["chat_id"], user["lang"]
    if not user["loc_id"]:
        tg.send(chat, t("need_region", lang))
        return
    wishes = db.wishes(chat)
    items = "\n".join(f"  • {esc(w['keyword'])} · 💰 {price_label(w.get('min_price'), w.get('max_price'), lang)}"
                      f"\n    <i>({esc(' · '.join(json.loads(w['terms']) + json.loads(w.get('similar') or '[]')))})</i>"
                      for w in wishes) or t("list_empty", lang)
    last = time.strftime("%Y-%m-%d %H:%M", time.localtime(user["last_check"])) if user["last_check"] else "-"
    buttons = [[{"text": f"💰 {w['keyword']}", "callback_data": f"price:{w['id']}"},
                {"text": f"🗑 {w['keyword']}", "callback_data": f"del:{w['id']}"}] for w in wishes]
    tg.send(chat, t("list", lang, label=esc(user["loc_label"]), free=t("on" if user["free_on"] else "off", lang),
                    items=items, last=last), buttons=buttons or None)


def ask_price(tg, db, chat, lang, wish_id, keyword, new):
    db.set_pending(chat, {"type": "await_price", "wish": wish_id, "keyword": keyword, "new": new})
    w = db.wish(chat, wish_id) or {}
    now = "" if new else "\n" + t("price_now", lang, range=price_label(w.get("min_price"), w.get("max_price"), lang))
    tg.send(chat, t("ask_price", lang, kw=esc(keyword)) + now,
            buttons=[[{"text": t("price_skip", lang), "callback_data": "pskip:1"}]])


def set_price(tg, db, jobs, user, pending, rng):
    chat, lang = user["chat_id"], user["lang"]
    lo, hi = rng
    db.set_pending(chat, None)
    if not db.wish(chat, pending["wish"]):
        return
    db.set_price(chat, pending["wish"], lo, hi)
    if pending.get("new"):
        tg.send(chat, t("added", lang, kw=esc(pending["keyword"]), label=esc(user["loc_label"]),
                        hours=CHECK_EVERY_HOURS) + "\n💰 " + price_label(lo, hi, lang))
    else:
        tg.send(chat, t("price_set", lang, kw=esc(pending["keyword"]), range=price_label(lo, hi, lang)))
    jobs.put(("wish", chat, f"w{pending['wish']}"))  # send what's listed now in that range


def handle_text(tg, db, jobs, user, text):
    chat, lang = user["chat_id"], user["lang"]
    text = text.strip()
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower().split("@")[0]
    arg = arg.strip()
    pending = db.pending(user)

    if cmd == "/start":
        db.set(chat, active=1)
        db.set_pending(chat, {"type": "await_lang"})
        tg.send(chat, t("choose_lang", lang), buttons=lang_buttons())
    elif cmd in ("/language", "/lang", "/sprache", "/langue"):
        db.set_pending(chat, {"type": "await_lang_only"})
        tg.send(chat, t("choose_lang", lang), buttons=lang_buttons())
    elif cmd == "/region":
        ask_region(tg, db, user)
    elif cmd in ("/sites", "/site"):
        tg.send(chat, t("sites", lang), buttons=site_buttons(user))
    elif cmd == "/help":
        tg.send(chat, t("help", lang))
    elif cmd == "/add":
        if arg:
            start_wish(tg, db, user, arg)
        else:
            db.set_pending(chat, {"type": "await_wish"})
            tg.send(chat, t("add_usage", lang))
    elif cmd == "/remove":
        match = next((w for w in db.wishes(chat) if w["keyword"].lower() == arg.lower()), None)
        if match:
            db.del_wish(chat, match["id"])
            tg.send(chat, t("removed", lang, kw=esc(match["keyword"])))
        else:
            show_list(tg, db, db.user(chat))
    elif cmd == "/list":
        show_list(tg, db, user)
    elif cmd == "/free":
        db.set(chat, free_on=0 if user["free_on"] else 1)
        if user["free_on"]:
            db.x("DELETE FROM seen WHERE chat_id=? AND search_key='free'", (chat,))
        tg.send(chat, t("free_toggled", lang, state=t("off" if user["free_on"] else "on", lang)))
    elif cmd == "/check":
        if not user["loc_id"]:
            tg.send(chat, t("need_region", lang))
        else:
            tg.send(chat, t("checking", lang))
            jobs.put(("check", chat))
    elif cmd == "/stop":
        db.set(chat, active=0)
        tg.send(chat, t("stopped", lang))
    elif cmd == "/price":
        wishes = db.wishes(chat)
        if not wishes:
            tg.send(chat, t("add_usage", lang))
        else:
            tg.send(chat, t("price_choose", lang), buttons=[
                [{"text": f"💰 {w['keyword']} ({price_label(w.get('min_price'), w.get('max_price'), lang)})",
                  "callback_data": f"price:{w['id']}"}] for w in wishes])
    elif cmd.startswith("/"):
        tg.send(chat, t("help", lang))
    elif pending.get("type") == "await_price":
        rng = parse_price_range(text)
        if rng is None:
            tg.send(chat, t("price_bad", lang), buttons=[[{"text": t("price_skip", lang), "callback_data": "pskip:1"}]])
        else:
            set_price(tg, db, jobs, user, pending, rng)
    elif pending.get("type") in ("await_region", "choose_loc") or not user["loc_id"]:
        handle_region_text(tg, db, user, text)
    else:
        start_wish(tg, db, user, text)  # plain text = something they want


def handle_button(tg, db, jobs, user, cb):
    chat = user["chat_id"]
    try:
        tg.call("answerCallbackQuery", callback_query_id=cb["id"])
    except Exception:
        pass
    tag, _, value = (cb.get("data") or "").partition(":")
    pending = db.pending(user)

    if tag == "lang" and value in LANGS:
        db.set(chat, lang=value)
        user = db.user(chat)
        tg.send(chat, t("lang_set", value))
        if pending.get("type") == "await_lang" or not user["loc_id"]:
            tg.send(chat, t("welcome", value))
            db.set_pending(chat, {"type": "await_region"})
        else:
            db.set_pending(chat, None)
        return

    lang = user["lang"]
    if tag == "site" and value in ALL_SITES:
        on = user_sites(user)
        on = [x for x in on if x != value] if value in on else on + [value]
        on = [x for x in ALL_SITES if x in on] or ["anibis"]
        db.set(chat, sites=",".join(on))
        tg.call("editMessageReplyMarkup", chat_id=chat, message_id=cb["message"]["message_id"],
                reply_markup={"inline_keyboard": site_buttons(db.user(chat))})
        return
    if tag == "loc" and pending.get("type") == "choose_loc":
        if value == "other":
            ask_region(tg, db, user)
            return
        opt = pending["options"][int(value)]
        label = loc_label(opt, lang)
        db.set(chat, loc_id=opt["id"], loc_radius=opt.get("radius"), loc_label=label, active=1,
               ricardo_area=None)
        db.reset_searches(chat)  # new area: start fresh
        db.set_pending(chat, None)
        tg.send(chat, t("region_saved", lang, label=esc(label), hours=CHECK_EVERY_HOURS,
                        free=t("on" if user["free_on"] else "off", lang)))
        # Remember what's listed now, so only later listings alert.
        jobs.put(("init", chat))
    elif tag == "wish" and pending.get("type") == "confirm_wish":
        db.set_pending(chat, None)
        if value == "yes":
            wid = db.add_wish(chat, pending["keyword"], pending["terms"], pending.get("similar"))
            ask_price(tg, db, chat, lang, wid, pending["keyword"], new=True)
        else:
            tg.send(chat, t("cancelled", lang))
    elif tag == "price" and value.isdigit():  # change the price range from /list
        w = db.wish(chat, int(value))
        if w:
            ask_price(tg, db, chat, lang, w["id"], w["keyword"], new=False)
    elif tag == "pskip" and pending.get("type") == "await_price":
        set_price(tg, db, jobs, user, pending, (None, None))
    elif tag == "del":
        kw = db.del_wish(chat, int(value))
        if kw:
            tg.send(chat, t("removed", lang, kw=esc(kw)))


# ------------------------------------------------------------------ main loop

def handle_update(tg, db, jobs, chat, cb, msg, lock):
    with lock:
        user = db.user(chat)
        try:
            if cb:
                handle_button(tg, db, jobs, user, cb)
            elif msg.get("text"):
                handle_text(tg, db, jobs, user, msg["text"])
        except Exception as e:
            print(f"[!] handling message from {chat} failed: {e}")


def main():
    try:  # single instance: Task Scheduler may try to start it again
        lock = socket.socket()
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        print("bot is already running, exiting")
        return

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    token = str(cfg.get("telegram_bot_token", "")).strip()
    if not token or "PASTE" in token or "PUT-YOUR" in token:
        print("[!] Put your telegram_bot_token in config.json first.")
        sys.exit(1)
    allowed = {str(x) for x in cfg.get("allowed_chat_ids") or []}

    tg = Telegram(token)
    db = DB(DB_FILE)
    jobs = queue.Queue()
    workers = ThreadPoolExecutor(max_workers=4)
    chat_locks = {}
    threading.Thread(target=checker, args=(tg, db, jobs), daemon=True).start()
    try:
        tg.call("setMyCommands", commands=[
            {"command": c, "description": d} for c, d in (
                ("start", "Start / Starten / Démarrer"), ("add", "Add item / Hinzufügen / Ajouter"),
                ("list", "My list / Liste"), ("free", "Free items on/off / Gratis"),
                ("check", "Search now / Jetzt suchen / Chercher"), ("region", "Change area / Gebiet / Zone"),
                ("language", "Language / Sprache / Langue / زبان"),
                ("sites", "Anibis / tutti / Ricardo"), ("price", "Price range / Preis / Prix / قیمت"), ("help", "Help / Hilfe / Aide"),
                ("stop", "Stop alerts / Stopp / Arrêter"))])
    except Exception as e:
        print(f"[!] setMyCommands: {e}")
    print("bot started")
    offset = int(db.meta("offset", 0))

    while True:
        try:
            updates = tg.call("getUpdates", http_timeout=70, offset=offset, timeout=50,
                              allowed_updates=["message", "callback_query"])
        except Exception as e:
            print(f"[!] getUpdates: {e}")
            time.sleep(15)
            continue
        for up in updates:
            offset = up["update_id"] + 1
            db.set_meta("offset", offset)
            msg = up.get("message") or {}
            cb = up.get("callback_query")
            frm = (cb or msg).get("from") or {}
            chat_obj = msg.get("chat") or ((cb or {}).get("message") or {}).get("chat") or {}
            chat = str(chat_obj.get("id", ""))
            if not chat or chat_obj.get("type", "private") != "private":
                continue
            if allowed and chat not in allowed:
                continue
            tg_lang = (frm.get("language_code") or "en")[:2]
            db.ensure_user(chat, frm.get("first_name") or "", tg_lang if tg_lang in LANGS else "en")
            # Each message is handled on its own thread, so one person's slow
            # step (looking up a town, translating) doesn't keep others waiting.
            # One person's messages are still handled in order.
            workers.submit(handle_update, tg, db, jobs, chat, cb, msg, chat_locks.setdefault(chat, threading.Lock()))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("[!] Crashed:\n" + traceback.format_exc())
        sys.exit(1)
