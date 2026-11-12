"""Offline tests for the Telegram bot: following several areas at once.

Nothing goes to the internet: Telegram, the marketplaces and the translator
are replaced by small fakes.
    python -m unittest discover tests
"""

import os
import queue
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT))

import anibis  # noqa: E402
import bot  # noqa: E402
import geo  # noqa: E402
import ricardo  # noqa: E402
import translate  # noqa: E402

CHAT = "42"
PLZ = {"geo-city-lausanne": "1003", "geo-city-geneve": "1201", "geo-canton-vaud": "1003"}

# What each place has on Anibis / tutti now. The Vaud canton includes Lausanne,
# so the bike sold in Lausanne shows up in both.
LISTINGS = {
    "geo-city-lausanne": [("l1", "Velo rouge", "CHF 120.-"), ("l2", "Chaise", "Gratis")],
    "geo-city-geneve": [("g1", "Velo bleu", "CHF 90.-"), ("g2", "Table", "Gratis")],
    "geo-canton-vaud": [("l1", "Velo rouge", "CHF 120.-"), ("v2", "Lampe", "Gratis")],
}


def listing(loc, lid, title, price, site):
    return {"id": lid, "title": title, "price": price, "place": f"{PLZ[loc]} {loc.split('-')[-1].title()}",
            "url": f"https://www.{site}.ch/{lid}", "site": site, "photo": None, "description": "",
            "postcode": PLZ[loc]}


def fake_search(text=None, locality=None, radius=None, page=1, site="anibis"):
    items = [listing(locality, *x, site) for x in LISTINGS.get(locality, [])]
    if text:
        items = [i for i in items if text.lower() in i["title"].lower()]
    return anibis.SearchResult(items, len(items), [{"name": locality.split("-")[-1].title()}], page)


def fake_search_new(text, locality, radius, seen_ids, max_pages=5, site="anibis"):
    return [i for i in fake_search(text, locality, radius, 1, site).listings if i["id"] not in seen_ids]


def fake_find_locations(text):
    loc = {"lausanne": "geo-city-lausanne", "geneve": "geo-city-geneve", "vaud": "geo-canton-vaud"}.get(text.lower())
    if not loc:
        return []
    kind = loc.split("-")[1]
    return [{"id": loc, "kind": kind, "name": text.title(), "total": 10}]


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def call(self, method, http_timeout=40, **params):
        self.calls.append((method, params))
        return {"message_id": len(self.calls)}

    def send(self, chat, text, buttons=None, preview=False):
        return self.call("sendMessage", chat_id=chat, text=text, reply_markup={"inline_keyboard": buttons} if buttons else None)

    def texts(self):
        return [p.get("text") or p.get("caption") for m, p in self.calls if m in ("sendMessage", "sendPhoto")]

    def listings(self):
        """URLs of the listings sent (each listing message ends with its link)."""
        return [x.split("\n")[-1] for x in self.texts() if x and x.startswith("🆕")]


class MultiAreaTest(unittest.TestCase):
    def setUp(self):
        self.patches = [
            (anibis, "search", fake_search), (anibis, "search_new", fake_search_new),
            (anibis, "find_locations", fake_find_locations),
            (ricardo, "search", lambda text: [listing("geo-city-geneve", "r1", "Velo de course", "CHF 300.-", "ricardo")]),
            (translate, "expand", lambda text, lang="en": ([text], [])),
            (geo, "make_area", lambda kind, name, radius, ls: {"zips": sorted({x["postcode"] for x in ls})}),
            (geo, "in_area", lambda area, plz: bool(area) and plz in area["zips"]),
            (bot.time, "sleep", lambda s: None),
        ]
        self.saved = [(mod, name, getattr(mod, name)) for mod, name, _ in self.patches]
        for mod, name, fn in self.patches:
            setattr(mod, name, fn)
        self.tmp = tempfile.TemporaryDirectory()
        self.db = bot.DB(Path(self.tmp.name) / "bot.db")
        self.tg = FakeTelegram()
        self.jobs = queue.Queue()
        self.db.ensure_user(CHAT, "Test", "en")
        self.db.set(CHAT, lang="en")

    def tearDown(self):
        for mod, name, fn in self.saved:
            setattr(mod, name, fn)
        self.db.con.close()
        self.tmp.cleanup()

    # helpers: what the user types / taps, then the background checker's work
    def say(self, text):
        bot.handle_text(self.tg, self.db, self.jobs, self.db.user(CHAT), text)

    def press(self, data):
        bot.handle_button(self.tg, self.db, self.jobs, self.db.user(CHAT), {"id": "cb", "data": data, "message": {"message_id": 1}})

    def run_jobs(self):
        while not self.jobs.empty():
            kind, chat, *only = self.jobs.get()
            bot.check_user(self.tg, self.db, self.db.user(chat), report=kind, only=only[0] if only else None)

    def add_area(self, name):
        self.say("/region")
        if self.db.areas(CHAT):
            self.press("aadd:1")
        self.say(name)
        self.press("loc:0")
        self.run_jobs()

    def test_two_areas_send_from_both(self):
        self.add_area("Lausanne")
        self.assertEqual(self.tg.listings(), ["https://www.anibis.ch/l2"])  # free item in Lausanne
        self.add_area("Geneve")
        self.assertEqual(self.tg.listings()[1:], ["https://www.anibis.ch/g2"], "only the new area's free items")
        user = self.db.user(CHAT)
        self.assertEqual(user["loc_label"], "Lausanne (town only) + Geneve (town only)")
        self.assertIn("Lausanne (town only) + Geneve (town only)", self.tg.texts()[-1])  # the report

        n = len(self.tg.listings())
        self.say("velo")
        self.press("wish:yes")
        self.press("pskip:1")
        self.run_jobs()
        sent = self.tg.listings()[n:]
        self.assertEqual(sorted(sent), ["https://www.anibis.ch/g1", "https://www.anibis.ch/l1",
                                        "https://www.ricardo.ch/r1"])

        # The 2-hourly check: nothing new in either area, so nothing is sent.
        n = len(self.tg.listings())
        bot.check_user(self.tg, self.db, self.db.user(CHAT), report="auto")
        self.assertEqual(self.tg.listings()[n:], [])

        # Something new in Geneva is found.
        LISTINGS["geo-city-geneve"].append(("g3", "Velo enfant", "CHF 40.-"))
        try:
            bot.check_user(self.tg, self.db, self.db.user(CHAT), report="auto")
        finally:
            LISTINGS["geo-city-geneve"].pop()
        self.assertEqual(self.tg.listings()[n:], ["https://www.anibis.ch/g3"])

    def test_overlapping_areas_send_a_listing_once(self):
        self.add_area("Lausanne")
        self.add_area("Vaud")
        self.say("velo")
        self.press("wish:yes")
        self.press("pskip:1")
        self.run_jobs()
        self.assertEqual(self.tg.listings().count("https://www.anibis.ch/l1"), 1)

    def test_remove_area_and_limit(self):
        self.add_area("Lausanne")
        self.add_area("Geneve")
        self.add_area("Geneve")
        self.assertIn("already follow", self.tg.texts()[-1])
        geneve = self.db.areas(CHAT)[1]
        self.press(f"adel:{geneve['id']}")
        self.assertEqual([a["loc_label"] for a in self.db.areas(CHAT)], ["Lausanne (town only)"])
        self.assertEqual(self.db.user(CHAT)["loc_label"], "Lausanne (town only)")
        self.assertFalse(self.db.q("SELECT 1 FROM seen WHERE search_key LIKE ?", (f"%#{geneve['id']}",)))

        for i in range(bot.MAX_AREAS - 1):
            self.db.add_area(CHAT, f"geo-city-x{i}", None, f"X{i}")
        self.say("/region")
        self.assertIn("at most", self.tg.texts()[-1])
        self.assertNotIn("aadd:1", str(self.tg.calls[-1]))

        for a in self.db.areas(CHAT):
            self.press(f"adel:{a['id']}")
        self.assertIsNone(self.db.user(CHAT)["loc_id"])
        self.say("/check")
        self.assertIn("/region", self.tg.texts()[-1])

    def test_old_single_area_is_moved_over(self):
        path = Path(self.tmp.name) / "old.db"
        old = bot.DB(path)
        old.ensure_user(CHAT, "Old", "en")
        old.set(CHAT, loc_id="geo-city-lausanne", loc_label="Lausanne (town only)")
        old.x("DELETE FROM areas")
        old.mark_seen(CHAT, "free@anibis", {"l2"})
        old.mark_seen(CHAT, "w1@tutti", {"l1"})
        old.con.close()

        new = bot.DB(path)  # opening it moves the area to the new table
        areas = new.areas(CHAT)
        self.assertEqual([(a["loc_id"], a["loc_label"]) for a in areas], [("geo-city-lausanne", "Lausanne (town only)")])
        keys = sorted(r["search_key"] for r in new.q("SELECT search_key FROM seen"))
        self.assertEqual(keys, [f"free@anibis#{areas[0]['id']}", f"w1@tutti#{areas[0]['id']}"])
        bot.DB(path)  # opening it again changes nothing
        self.assertEqual(len(new.areas(CHAT)), 1)
        new.con.close()


if __name__ == "__main__":
    unittest.main()
