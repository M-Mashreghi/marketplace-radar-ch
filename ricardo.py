"""
Searching ricardo.ch.

Ricardo's robots.txt allows plain search pages (/de/s/<words>/) but forbids
search URLs with extra parameters (sorting, location, page, ...). So the bot
only reads the plain search page: about 60 results for all of Switzerland, in
Ricardo's own order. That means:
  * no area filter on the site; the bot keeps the results whose seller
    postcode is in the user's area itself (see geo.py)
  * no "free items" search (Ricardo has no free listings)
  * a new listing is noticed when it appears on the first results page
"""

import json
import re
import urllib.parse

import anibis

BASE = "https://www.ricardo.ch"


def search_url(text):
    return f"{BASE}/de/s/{urllib.parse.quote(text.strip())}/"


def _money(v):
    if v in (None, "", 0):
        return ""
    try:
        return f"{float(v):,.2f}".replace(",", "'")
    except (TypeError, ValueError):
        return str(v)


def _image(node):
    for key in ("image", "imageUrl", "image_url", "thumbnail", "mainImage", "picture"):
        v = node.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
        if isinstance(v, dict):
            for k in ("url", "src", "large", "medium"):
                if isinstance(v.get(k), str) and v[k].startswith("http"):
                    return v[k]
    imgs = node.get("images")
    if isinstance(imgs, list) and imgs:
        first = imgs[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("src") or ""
    return ""


def _from_json(nd):
    """Walk the page data and collect anything that looks like an article."""
    found = {}

    def walk(o):
        if isinstance(o, dict):
            aid = o.get("id") or o.get("articleId")
            title = o.get("title")
            if (aid and isinstance(title, str) and re.fullmatch(r"\d{6,}", str(aid))
                    and any(k in o for k in ("buyNowPrice", "bidPrice", "price", "currentBidPrice", "startPrice"))):
                buy = o.get("buyNowPrice") or (o.get("price") if not isinstance(o.get("price"), dict) else None)
                bid = o.get("bidPrice") or o.get("currentBidPrice") or o.get("startPrice")
                parts = []
                if bid:
                    parts.append(f"🔨 {_money(bid)}")
                if buy:
                    parts.append(f"🛒 {_money(buy)}")
                link = o.get("url") or o.get("link") or ""
                if not link:
                    slug = anibis.slugify(title)
                    link = f"/de/a/{slug}-{aid}/"
                found.setdefault(str(aid), {
                    "site": "ricardo",
                    "id": str(aid),
                    "title": title.strip(),
                    "description": (o.get("description") or o.get("subtitle") or "").strip()
                    if isinstance(o.get("description") or o.get("subtitle") or "", str) else "",
                    "price": " · ".join(parts),
                    "place": o.get("location") if isinstance(o.get("location"), str) else "",
                    "photo": _image(o),
                    "time": o.get("startDate") or "",
                    "url": urllib.parse.urljoin(BASE, link),
                })
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(nd)
    return list(found.values())


def _from_ld(page):
    """The search page has a schema.org ItemList (JSON-LD) with every result."""
    m = re.search(r'<script type="application/ld\+json" id="srps-json-ld">(.*?)</script>', page, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    items = []
    for g in data.get("@graph", []):
        if g.get("@type") != "ItemList":
            continue
        for el in g.get("itemListElement", []):
            prod = el.get("item") or {}
            url = prod.get("url") or ""
            aid = re.search(r"-(\d{6,})/?$", url)
            if not aid or not prod.get("name"):
                continue
            offers = prod.get("offers") or {}
            price = _money(offers.get("price")) if isinstance(offers, dict) else ""
            image = prod.get("image")
            if isinstance(image, list):
                image = image[0] if image else ""
            items.append({
                "site": "ricardo",
                "id": aid.group(1),
                "title": prod["name"].strip(),
                "description": "",
                "price": f"{price} CHF" if price else "",
                "place": "",
                "photo": image if isinstance(image, str) else "",
                "time": "",
                "url": url,
            })
    return items


def _from_rsc(page, urls):
    """The page's own data (Next.js stream) has every article with the
    seller's postcode and town."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', page, re.S)
    try:
        s = "".join(json.loads('"' + c + '"') for c in chunks)
    except ValueError:
        return []
    dec, items = json.JSONDecoder(), {}
    for m in re.finditer(r'\{"id":"(\d{6,})","title":', s):
        try:
            o, _ = dec.raw_decode(s, m.start())
        except ValueError:
            continue
        if o["id"] in items or not isinstance(o.get("title"), str):
            continue
        ship = [x for x in o.get("shipping") or [] if isinstance(x, dict)]
        loc = next((x for x in ship if x.get("zipCode")), {})
        parts = []
        if o.get("hasAuction") and o.get("bidPrice") is not None:
            parts.append(f"🔨 {_money(o['bidPrice']) or '0'} CHF")
        if o.get("buyNowPrice"):
            parts.append(f"🛒 {_money(o['buyNowPrice'])} CHF")
        pickup = any(x.get("key") == "get_by_buyer" for x in ship)
        items[o["id"]] = {
            "site": "ricardo",
            "id": o["id"],
            "title": o["title"].strip(),
            "description": "",
            "price": " · ".join(parts),
            "place": ", ".join(x for x in (loc.get("city"), loc.get("zipCode")) if x),
            "postcode": str(loc.get("zipCode") or ""),
            "pickup": pickup,
            "photo": o.get("image") if isinstance(o.get("image"), str) else "",
            "time": o.get("startDate") or "",
            "url": urls.get(o["id"]) or f"{BASE}/de/a/{anibis.slugify(o['title'])}-{o['id']}/",
        }
    return list(items.values())


def _from_links(page):
    """Fallback: article links look like /de/a/<slug>-<id>/."""
    items, order = {}, []
    for m in re.finditer(r'href="(/(?:de|fr|it)/a/([^"/]*?)-(\d{6,})/?)"[^>]*>(.*?)</a>', page, re.S):
        href, slug, aid, inner = m.groups()
        if aid not in items:
            items[aid] = {"site": "ricardo", "id": aid, "title": "", "description": "", "price": "",
                          "place": "", "photo": "", "time": "", "url": BASE + href}
            order.append(aid)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
        if len(text) > len(items[aid]["title"]):
            items[aid]["title"] = text[:150]
        img = re.search(r'<img[^>]+src="(https://img\.ricardostatic\.ch/[^"]+)"', inner)
        if img and not items[aid]["photo"]:
            items[aid]["photo"] = img.group(1)
    for it in items.values():
        if not it["title"]:
            it["title"] = items and it["url"].rstrip("/").rsplit("/", 1)[-1].rsplit("-", 1)[0].replace("-", " ")
    return [items[a] for a in order]


def search(text):
    page = anibis.fetch(search_url(text))
    ld = _from_ld(page)
    items = _from_rsc(page, {i["id"]: i["url"] for i in ld})
    if items:
        return items
    items = ld
    if not items:
        nd = anibis._next_data(page)
        items = _from_json(nd) if nd else []
    return items or _from_links(page)
