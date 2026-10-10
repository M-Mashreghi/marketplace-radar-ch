"""
Swiss postcodes -> coordinates, so Ricardo results can be filtered by area.

Ricardo shows each seller's postcode, but its rules don't let the bot filter
by area on the site. So the bot keeps the listings whose seller postcode is
inside the user's area:
  * town (+ radius): within the radius of the town (town only = 6 km)
  * region: within the area where the Anibis listings of that region are
  * canton: same canton

Postcode coordinates come from GeoNames (free, CC-BY), downloaded once to
ch_postcodes.txt. If that download fails, the postcodes seen on Anibis for the
user's area are used instead.
"""

import io
import math
import re
import urllib.request
import zipfile
from pathlib import Path

import anibis

HERE = Path(__file__).resolve().parent
FILE = HERE / "ch_postcodes.txt"
URL = "https://download.geonames.org/export/zip/CH.zip"
TOWN_KM = 6

_zips = None    # postcode -> (lat, lon, canton)
_places = None  # slug of place name -> (lat, lon)


def _load():
    global _zips, _places
    if _zips is not None:
        return _zips
    _zips, _places = {}, {}
    try:
        if not FILE.exists():
            req = urllib.request.Request(URL, headers={"User-Agent": anibis.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            FILE.write_bytes(zipfile.ZipFile(io.BytesIO(data)).read("CH.txt"))
        rows = {}
        for line in FILE.read_text(encoding="utf-8").splitlines():
            f = line.split("\t")
            if len(f) < 11 or not f[9] or not f[10]:
                continue
            lat, lon = float(f[9]), float(f[10])
            rows.setdefault(f[1], []).append((lat, lon, f[4]))
            _places.setdefault(anibis.slugify(f[2]), (lat, lon))
        for z, pts in rows.items():
            _zips[z] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), pts[0][2])
    except Exception as e:  # no data: callers fall back to postcode lists
        from anibis_alert import print  # noqa: A001
        print(f"[!] postcode data not available: {e}")
    return _zips


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def make_area(kind, name, radius, listings):
    """Describe the user's area from the Anibis location and its listings."""
    zips = sorted({l["postcode"] for l in listings if l.get("postcode")})
    cantons = [l["canton"] for l in listings if l.get("canton")]
    canton = max(set(cantons), key=cantons.count) if cantons else ""
    data = _load()
    if kind == "canton" and canton:
        return {"canton": canton, "zips": zips}
    pts = [data[z][:2] for z in zips if z in data]
    center = None
    if kind == "city":
        center = (_places or {}).get(anibis.slugify(name))
    if not center and pts:
        center = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    if center:
        if kind == "city":
            dist = radius or TOWN_KM
        else:  # region: cover where most of its listings are
            d = sorted(km(center, p) for p in pts) or [10]
            dist = max(10, round(d[int(len(d) * 0.9) - 1 if len(d) > 1 else 0] + 3))
        return {"lat": center[0], "lon": center[1], "km": dist, "canton": canton, "zips": zips}
    return {"zips": zips, "canton": canton}


def in_area(area, postcode):
    if not area or not postcode:
        return False
    data = _load()
    if "lat" in area and postcode in data:
        return km((area["lat"], area["lon"]), data[postcode][:2]) <= area["km"]
    if area.get("canton") and "lat" not in area and postcode in data:
        return data[postcode][2] == area["canton"]
    # No coordinates: postcodes seen on Anibis for this area.
    return postcode in set(area.get("zips") or [])


def describe(area):
    if not area:
        return ""
    if "lat" in area:
        return f"{area['km']} km"
    if area.get("canton") and _load():
        return area["canton"]
    return f"{len(area.get('zips') or [])} PLZ"


def postcode_of(place):
    m = re.search(r"\b(\d{4})\b", place or "")
    return m.group(1) if m else ""
