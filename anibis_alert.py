"""
Anibis -> Telegram alert.

Checks one or more anibis.ch search result pages and sends every listing it
has not seen before (title, price, link) to a Telegram chat.

Only uses the Python standard library, so no pip install is needed.

Usage:
    python anibis_alert.py              # check once
    python anibis_alert.py --loop 5     # check every 5 minutes, forever
    python anibis_alert.py --test       # send the newest listing now, even if seen
    python anibis_alert.py --dry-run    # print what would be sent, send nothing

sada.py is the entry point Task Scheduler runs; it does one check and exits.

Settings live in config.json next to this file (created on first run).
Seen listing ids are stored in seen_ids.json next to this file.
"""

import argparse
import builtins
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"
SEEN_FILE = HERE / "seen_ids.json"
# Where bot.db and the log are kept: this folder, unless DATA_DIR is set.
DATA_DIR = Path(os.environ.get("DATA_DIR") or HERE).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "anibis_alert.log"


def print(*args, **kwargs):
    """Print to the console when there is one, and always append to the log file
    (Task Scheduler runs this windowless, so the log is the only output)."""
    text = " ".join(str(a) for a in args)
    if sys.stdout is not None:
        builtins.print(text, **kwargs)
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            for line in text.splitlines() or [""]:
                f.write(f"{stamp}  {line}\n")
    except OSError:
        pass

DEFAULT_CONFIG = {
    "telegram_bot_token": "PUT-YOUR-BOT-TOKEN-HERE",
    "telegram_chat_id": "PUT-YOUR-CHAT-ID-HERE",
    # Search on anibis.ch with your filters, then copy the address bar here.
    # Example: "https://www.anibis.ch/de/q/fahrrad"
    "search_urls": [],
    # On the very first run, mark everything currently listed as seen instead
    # of sending dozens of messages. Later runs only send new items.
    "silent_first_run": True,
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# Listing links look like /de/vi/1074007766 or /de/vi/<region>/<cat>/<slug>/54389608
LISTING_HREF_RE = re.compile(r'href="([^"]*/vi/[^"]*?(\d{6,}))(?:[?#][^"]*)?"')
PRICE_RE = re.compile(
    r"(CHF\s*[\d'’.,]+(?:\.-|–)?|[\d][\d'’]*(?:\.\d{2})?\s*\.-|Gratis|Gratuit|Gratuito|"
    r"Auf Anfrage|Sur demande|Su richiesta)",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")
STYLE_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.S | re.I)
PRICE_ELEMENT_RE = re.compile(
    r"(?:CHF\s*)?[\d'’]+(?:\.\d{2})?\s*\.-(?:\s*(?:pro|par|al)\s+\w+)?|CHF(?:\s*[\d'’.,]+-?)?|"
    r"Gratis|Gratuit|Gratuito|Auf Anfrage|Sur demande|Su richiesta|Preis auf Anfrage",
    re.IGNORECASE,
)
# Card text is e.g. "Lausanne, 1018, Heute 21:04"; keep "Lausanne, 1018".
PLACE_RE = re.compile(r"[^\d,<>]{2,40},\s*\d{4}\b")


# ---------------------------------------------------------------- settings

def fail(msg):
    print(f"[!] {msg}")
    sys.exit(1)


def load_config():
    cfg = {}
    if CONFIG_FILE.exists():
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if "search_urls" not in cfg:
        # Add the setting the user still has to fill in, keeping what's there.
        cfg = {**DEFAULT_CONFIG, **cfg, "search_urls": ["PASTE-YOUR-ANIBIS-SEARCH-URL-HERE"]}
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    cfg = {**DEFAULT_CONFIG, **cfg}
    if isinstance(cfg["search_urls"], str):
        cfg["search_urls"] = [cfg["search_urls"]]
    for key in ("telegram_bot_token", "telegram_chat_id", "search_urls"):
        value = str(cfg.get(key) or "")
        if not value or "PUT-YOUR" in value or "PASTE" in value:
            fail(f"Please set '{key}' in {CONFIG_FILE.name}.")
    return cfg


def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    return None  # None = first run ever


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- fetching

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean(text):
    text = STYLE_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", text))).strip()


def parse_from_next_data(page, base_url):
    """Anibis is a Next.js site; the listings are usually in a JSON blob."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []

    found = {}

    def walk(node):
        if isinstance(node, dict):
            lid = node.get("listingID") or node.get("listingId") or node.get("id")
            title = node.get("title") or node.get("subject")
            if lid and title and re.fullmatch(r"\d{6,}", str(lid)) and isinstance(title, str):
                price = node.get("formattedPrice") or node.get("priceFormatted") or node.get("price")
                if isinstance(price, dict):
                    price = price.get("formatted") or price.get("amount") or price.get("value")
                link = node.get("url") or node.get("link") or f"/de/vi/{lid}"
                found.setdefault(str(lid), {
                    "id": str(lid),
                    "title": title.strip(),
                    "price": format_price(price),
                    "url": urllib.parse.urljoin(base_url, str(link)),
                })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return list(found.values())


def format_price(price):
    if price in (None, ""):
        return ""
    if isinstance(price, (int, float)):
        return f"CHF {price:,.0f}".replace(",", "'")
    return str(price).strip()


def parse_from_links(page, base_url):
    """Fallback: find listing links in the HTML and read title/price around them."""
    matches = list(LISTING_HREF_RE.finditer(page))
    items = {}
    order = []
    for i, m in enumerate(matches):
        href, lid = m.group(1), m.group(2)
        if lid not in items:
            items[lid] = {"id": lid, "title": "", "price": "",
                          "url": urllib.parse.urljoin(base_url, html.unescape(href))}
            order.append(lid)
        item = items[lid]

        # Text of this <a> element = a title candidate.
        end_a = page.find("</a>", m.end())
        start_tag_end = page.find(">", m.end())
        if 0 < start_tag_end < end_a:
            text = clean(page[start_tag_end + 1:end_a])
            if len(text) > len(item["title"]) and not text.isdigit() and not PRICE_RE.fullmatch(text):
                item["title"] = text
        if not item["title"]:
            tag = page[page.rfind("<", 0, m.start()):start_tag_end]
            t = re.search(r'(?:title|aria-label)="([^"]+)"', tag)
            if t:
                item["title"] = clean(t.group(1))

        # Price and place: first element whose whole text looks like a price
        # ("CHF 100.-", "1'600.-", "Gratis") or a place ("Lausanne, 1018"),
        # between this link and the next listing. Whole-element matching keeps
        # titles like "... (Gratis Versand)" from counting as free.
        nxt = next((n.start() for n in matches[i + 1:] if n.group(2) != lid), len(page))
        raw = page[m.end():min(nxt, m.end() + 15000)].replace("<!-- -->", "")
        texts = [clean(t) for t in re.findall(r">([^<>]+)<", raw)]
        texts = [t for t in texts if t]
        if not item["price"]:
            for j, t in enumerate(texts):
                if PRICE_ELEMENT_RE.fullmatch(t):
                    # "CHF" and the number are sometimes separate elements.
                    if t.upper() == "CHF" and j + 1 < len(texts):
                        t = f"CHF {texts[j + 1]}"
                    item["price"] = t
                    break
        if not item.get("place"):
            for j, t in enumerate(texts):
                # Featured cards split it: "Lausanne" + ", 1007".
                if j + 1 < len(texts) and texts[j + 1].startswith(","):
                    t += texts[j + 1]
                p = PLACE_RE.match(t)
                if p:
                    item["place"] = p.group(0)
                    break

    for item in items.values():
        if not item["title"]:
            # Last resort: make a title from the URL slug.
            slug = item["url"].rstrip("/").split("/")
            item["title"] = slug[-2].replace("-", " ").capitalize() if len(slug) > 2 and not slug[-2] == "vi" else f"Listing {item['id']}"
    return [items[i] for i in order]


def get_listings(url):
    page = fetch(url)
    items = parse_from_next_data(page, url)
    if not items:
        items = parse_from_links(page, url)
    return items


# ---------------------------------------------------------------- telegram

def send_telegram(cfg, text):
    api = f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": cfg["telegram_chat_id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(api, data=body), timeout=30) as resp:
        result = json.loads(resp.read().decode())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram error: {result}")


def format_message(item):
    lines = [f"🆕 <b>{html.escape(item['title'], quote=False)}</b>"]
    if item["price"]:
        lines.append(f"💰 {html.escape(item['price'], quote=False)}")
    lines.append(item["url"])
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def check_once(cfg, test=False, dry_run=False):
    seen = load_seen()
    first_run = seen is None
    seen = seen or {}
    sent = 0

    for url in cfg["search_urls"]:
        try:
            items = get_listings(url)
        except Exception as e:
            print(f"[!] Could not read {url}: {e}")
            continue
        print(f"{url}: {len(items)} listings found")
        if not items:
            print("    (no listings parsed; the page layout may have changed)")
            continue

        if test:
            new = items[:1]
        elif first_run and cfg.get("silent_first_run", True):
            new = []
            print("    first run: remembering current listings, nothing sent")
        else:
            new = [it for it in items if it["id"] not in seen]

        for item in new:
            msg = format_message(item)
            if dry_run:
                print("---\n" + msg)
            else:
                try:
                    send_telegram(cfg, msg)
                    sent += 1
                    time.sleep(1)  # stay well under Telegram's rate limit
                except Exception as e:
                    print(f"[!] Telegram send failed for {item['id']}: {e}")
                    continue  # don't mark as seen, retry next time

        for item in items:
            seen.setdefault(item["id"], item["title"])

    if not dry_run:
        save_seen(seen)
    print(f"Sent {sent} message(s).")


def main():
    ap = argparse.ArgumentParser(description="Send new Anibis listings to Telegram.")
    ap.add_argument("--loop", type=float, metavar="MINUTES", help="keep checking every N minutes")
    ap.add_argument("--test", action="store_true", help="send the newest listing even if already seen")
    ap.add_argument("--dry-run", action="store_true", help="print messages instead of sending")
    args = ap.parse_args()

    cfg = load_config()
    if args.loop:
        while True:
            check_once(cfg, dry_run=args.dry_run)
            time.sleep(args.loop * 60)
    else:
        check_once(cfg, test=args.test, dry_run=args.dry_run)


def run():
    """main() with any crash written to the log (pythonw has no console)."""
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("[!] Crashed:\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    run()
