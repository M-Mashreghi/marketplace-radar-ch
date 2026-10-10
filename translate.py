"""Turn what a user typed (any language) into search words for Anibis.

Anibis listings are written in German, French, Italian or English, and the
site's search only matches the words in a listing. So a wish like "دوچرخه"
is searched as "Velo", "vélo", "bicicletta" and "bicycle".

Uses Google's free translate endpoint (no key); falls back to MyMemory.
If both fail, the word is searched as typed.
"""

import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

TARGETS = ("de", "fr", "it", "en")
UA = {"User-Agent": "Mozilla/5.0"}


def _google(text, target, source="auto", alts=False):
    try:
        return _google_once(text, target, source, alts)
    except Exception:
        time.sleep(2)  # Google sometimes refuses a burst of requests; try once more
        return _google_once(text, target, source, alts)


def _google_once(text, target, source="auto", alts=False):
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t"
           + ("&dt=at" if alts else "") + "&sl=" + source + "&tl=" + target
           + "&q=" + urllib.parse.quote(text))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = "".join(part[0] for part in data[0] if part and part[0])
    source = data[2] if len(data) > 2 and isinstance(data[2], str) else ""
    if not alts:
        return out.strip(), source
    others = []
    # Other ways to say it (e.g. "Mehrfachsteckdose" next to "Steckdosenleiste").
    # Only when the whole text is one segment, so they are full alternatives.
    if len(data) > 5 and isinstance(data[5], list) and len(data[5]) == 1:
        for a in (data[5][0][2] if len(data[5][0]) > 2 else None) or []:
            if a and isinstance(a[0], str):
                others.append(a[0].strip())
    return out.strip(), source, others


def _mymemory(text, source, target):
    url = ("https://api.mymemory.translated.net/get?q=" + urllib.parse.quote(text)
           + "&langpair=" + urllib.parse.quote(f"{source}|{target}"))
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("responseData") or {}).get("translatedText", "").strip()


def search_terms(text, user_lang="en"):
    """Distinct search words for Anibis, the typed word first if it is in Latin script."""
    text = text.strip()
    terms = []
    if re.search(r"[A-Za-zÀ-ÿ]", text) and not re.search(r"[؀-ۿ]", text):
        terms.append(text)
    for target in TARGETS:
        word = ""
        try:
            word, _ = _google(text, target)
        except Exception:
            try:
                word = _mymemory(text, user_lang or "en", target)
            except Exception:
                word = ""
        if word and not re.search(r"[؀-ۿ]", word):
            terms.append(word)
    if not terms:
        terms = [text]
    seen, out = set(), []
    for t in terms:
        key = t.lower()
        if key not in seen and len(t) <= 60:
            seen.add(key)
            out.append(t)
    return out


def _key(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s.lower())
                  .encode("ascii", "ignore").decode()).strip()


def _same_thing(a, b):
    """'multiple socket' and 'multiple socket block' name the same thing."""
    wa, wb = set(_key(a).split()), set(_key(b).split())
    return bool(wa) and bool(wb) and (wa <= wb or wb <= wa)


def expand(text, user_lang="en"):
    """(search words, similar names) for something a user wants.

    Search words: the text as typed (if in Latin script) and its German,
    French, Italian and English translation. Similar names: the translator's
    other common names for it, kept only when they translate back into
    English as the same thing (so "Moto" for "Velo" or "letto" for "divano"
    are dropped).
    """
    text = text.strip()
    terms = search_terms(text, user_lang)
    english, alts = set(), {}
    for target in TARGETS:
        try:
            main, _, others = _google(text, target, alts=True)
        except Exception:
            continue
        if target == "en":
            english.update([main] + others)
        for o in others:
            alts.setdefault(o, target)
        time.sleep(0.3)
    if not english:
        return terms, []
    known = {_key(t) for t in terms}
    similar = []
    for alt, lang in alts.items():
        if _key(alt) in known or _key(alt) in {_key(x) for x in similar} or len(alt) > 60:
            continue
        if lang != "en":
            try:
                back, _ = _google(alt, "en", source=lang)
            except Exception:
                continue
            time.sleep(0.3)
            if not any(_same_thing(back, e) for e in english):
                continue
        similar.append(alt)
    return terms, similar
