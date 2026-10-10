"""
Talking to anibis.ch: building search URLs, reading results, finding locations.

Anibis encodes a search in the URL as
    "A" + base64url(msgpack([text, category, [selects, multiselects, price, locations]]))
where a location is ["location", "<localityID>", <radius km or None>], e.g.
"geo-city-lausanne", "geo-region-lausanne", "geo-canton-vaud".

Search pages embed their results as JSON (__NEXT_DATA__), which gives title,
description, price, place, canton, photo and date for every listing.
"""

import base64
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
BASE = "https://www.anibis.ch"
# tutti.ch runs on the same platform: same search URLs, same page data.
SITES = {"anibis": "https://www.anibis.ch", "tutti": "https://www.tutti.ch"}
RADII_KM = (5, 10, 20, 50)

# Canton short name (as Anibis returns it) -> candidate locality ids.
CANTON_IDS = {
    "AG": ["aargau", "argovie"], "AI": ["appenzell-innerrhoden", "appenzell-rhodes-interieures"],
    "AR": ["appenzell-ausserrhoden", "appenzell-rhodes-exterieures"], "BE": ["bern", "berne"],
    "BL": ["basel-landschaft", "bale-campagne"], "BS": ["basel-stadt", "bale-ville"],
    "FR": ["fribourg", "freiburg"], "GE": ["geneve", "genf", "geneva"], "GL": ["glarus", "glaris"],
    "GR": ["graubunden", "grisons", "graubuenden"], "JU": ["jura"], "LU": ["luzern", "lucerne"],
    "NE": ["neuchatel", "neuenburg"], "NW": ["nidwalden", "nidwald"], "OW": ["obwalden", "obwald"],
    "SG": ["st-gallen", "saint-gall", "sankt-gallen"], "SH": ["schaffhausen", "schaffhouse"],
    "SO": ["solothurn", "soleure"], "SZ": ["schwyz"], "TG": ["thurgau", "thurgovie"],
    "TI": ["ticino", "tessin"], "UR": ["uri"], "VD": ["vaud", "waadt"], "VS": ["valais", "wallis"],
    "ZG": ["zug", "zoug"], "ZH": ["zurich", "zuerich"],
}
# Common alternative names people type -> Anibis slug.
ALIASES = {
    "geneva": "geneve", "genf": "geneve", "ginevra": "geneve", "zuerich": "zurich", "zurigo": "zurich",
    "biel": "biel-bienne", "bienne": "biel-bienne", "sitten": "sion", "lucerne": "luzern",
    "berne": "bern", "bale": "basel", "basle": "basel", "neuenburg": "neuchatel",
    "freiburg": "fribourg", "waadt": "vaud", "wallis": "valais", "tessin": "ticino",
    "st-gall": "st-gallen", "saint-gall": "st-gallen", "sankt-gallen": "st-gallen",
}


# ------------------------------------------------------------------ low level

def _msgpack(o):
    if o is None:
        return b"\xc0"
    if o is True:
        return b"\xc3"
    if o is False:
        return b"\xc2"
    if isinstance(o, int):
        if 0 <= o < 128:
            return bytes([o])
        return b"\xcd" + o.to_bytes(2, "big")
    if isinstance(o, str):
        b = o.encode("utf-8")
        if len(b) < 32:
            return bytes([0xA0 | len(b)]) + b
        return b"\xd9" + bytes([len(b)]) + b
    if isinstance(o, list):
        return bytes([0x90 | len(o)]) + b"".join(_msgpack(x) for x in o)
    raise TypeError(o)


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def search_url(text=None, locality=None, radius=None, page=1, lang="de", site="anibis"):
    loc = [["location", locality, radius or None]] if locality else None
    token = "A" + base64.urlsafe_b64encode(
        _msgpack([text or None, None, [None, None, None, loc]])).decode().rstrip("=")
    url = f"{SITES[site]}/{lang}/q/{slugify(text or '') or 'inserate'}/{token}"
    return url + (f"?page={page}" if page > 1 else "")


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _next_data(page):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else None


def _search_data(nd):
    for q in nd["props"]["pageProps"]["dehydratedState"]["queries"]:
        if q.get("queryKey", [None])[0] == "SearchListingsByConstraints":
            return q["state"]["data"]
    return None


# ------------------------------------------------------------------ search

class SearchResult:
    def __init__(self, listings, total, localities, page):
        self.listings = listings      # list of dicts (see _listing)
        self.total = total            # total hits on Anibis
        self.localities = localities  # location(s) Anibis understood
        self.page = page              # page Anibis actually served


def _listing(node, site="anibis"):
    loc = node.get("localization") or {}
    pc = node.get("postcodeInformation") or {}
    canton = pc.get("canton") or {}
    thumb = node.get("thumbnail") or {}
    photo = ((thumb.get("retinaRendition") or {}).get("src")
             or (thumb.get("normalRendition") or {}).get("src") or "")
    slug = (node.get("seoInformation") or {}).get("deSlug")
    lid = str(node.get("listingID"))
    place = ", ".join(x for x in (pc.get("locationName"), pc.get("postcode")) if x)
    base = SITES[site]
    return {
        "site": site,
        "id": lid,
        "title": (loc.get("title") or "").strip(),
        "description": (loc.get("body") or "").strip(),
        "price": (node.get("formattedPrice") or "").strip(),
        "place": place,
        "postcode": str(pc.get("postcode") or ""),
        "canton": canton.get("shortName") or "",
        "canton_name": canton.get("name") or "",
        "photo": photo,
        "time": node.get("timestamp") or "",
        "url": f"{base}/de/vi/{slug}/{lid}" if slug else f"{base}/de/vi/{lid}",
    }


def search(text=None, locality=None, radius=None, page=1, site="anibis"):
    """One page (about 30 listings, newest first) of an Anibis or tutti search."""
    html_page = fetch(search_url(text, locality, radius, page, site=site))
    nd = _next_data(html_page)
    data = _search_data(nd) if nd else None
    if not data:
        # Layout changed: fall back to reading links from the HTML.
        import anibis_alert
        items = anibis_alert.parse_from_links(html_page, SITES[site])
        for i in items:
            i["site"] = site
        return SearchResult(items, None, [], page)
    edges = (data.get("listings") or {}).get("edges") or []
    listings = [_listing(e["node"], site) for e in edges if e.get("node")]
    total = (data.get("listings") or {}).get("totalCount")
    localities = []
    for f in data.get("filters") or []:
        if f.get("name") == "location":
            localities = ((f.get("value") or {}).get("selectedLocalities")) or []
    served = page
    try:
        served = nd["props"]["pageProps"]["initialReduxState"]["searchResultPage"]["page"]
    except (KeyError, TypeError):
        pass
    return SearchResult(listings, total, localities, served)


def search_new(text, locality, radius, seen_ids, max_pages=5, site="anibis"):
    """Listings not in seen_ids, reading further pages while everything is new."""
    found, ids = [], set()
    for page in range(1, max_pages + 1):
        res = search(text, locality, radius, page, site=site)
        if res.page != page:
            break  # Anibis ignored the page number
        new = [l for l in res.listings if l["id"] not in seen_ids and l["id"] not in ids]
        found += new
        ids.update(l["id"] for l in new)
        if len(new) < len(res.listings) or not res.listings:
            break  # reached listings we already know
        time.sleep(1)
    return found


def is_free(listing):
    price = listing.get("price", "")
    return bool(re.search(r"gratis|gratuit|gratuito|free|verschenk", price, re.I)
                or re.fullmatch(r"(CHF\s*)?0+(\.0+)?(\.-)?", price.strip()))


# ------------------------------------------------------------------ locations

def _probe(locality, radius=None):
    """Return (name, type, total) if Anibis knows this locality, else None."""
    try:
        res = search(None, locality, radius)
    except Exception:
        return None
    for loc in res.localities:
        if loc.get("localityID") == locality:
            return loc.get("name") or locality, loc.get("localityType") or "", res.total, res
    return None


def find_locations(user_text):
    """All Anibis location options that match what the user typed.

    Returns a list of dicts: {id, radius, name, kind, total}
    kind is one of: city, region, canton.
    """
    base = slugify(user_text)
    if not base:
        return []
    variants = [base]
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        if a in base and base.replace(a, b) not in variants:
            variants.append(base.replace(a, b))
    variants += [ALIASES[v] for v in list(variants) if v in ALIASES and ALIASES[v] not in variants]

    options, cantons = [], []
    for v in variants:
        city = _probe(f"geo-city-{v}")
        if city:
            name, _, total, res = city
            options.append({"id": f"geo-city-{v}", "radius": None, "name": name, "kind": "city", "total": total})
            for km in RADII_KM:
                options.append({"id": f"geo-city-{v}", "radius": km, "name": name, "kind": "city", "total": None})
            cantons += [l["canton"] for l in res.listings if l.get("canton")]
            break
    for v in variants:
        region = _probe(f"geo-region-{v}")
        if region:
            name, _, total, _ = region
            options.append({"id": f"geo-region-{v}", "radius": None, "name": name, "kind": "region", "total": total})
            break

    # Canton: the one the user typed, or the one most listings in the town are in.
    canton_candidates = list(variants)
    if cantons:
        top = max(set(cantons), key=cantons.count)
        canton_candidates = CANTON_IDS.get(top, []) + canton_candidates
    for v in dict.fromkeys(canton_candidates):
        canton = _probe(f"geo-canton-{v}")
        if canton:
            name, _, total, _ = canton
            options.append({"id": f"geo-canton-{v}", "radius": None, "name": name, "kind": "canton", "total": total})
            break
    return options
