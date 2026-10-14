// Turn what a user typed (any language) into search words: German, French,
// Italian and English, plus similar names. A port of translate.py.
// Uses Google's free translate endpoint (no key), with MyMemory as fallback.

import { sleep } from "./anibis.js";

const TARGETS = ["de", "fr", "it", "en"];
const UA = { "User-Agent": "Mozilla/5.0" };
const PERSIAN = /[؀-ۿ]/;

async function getJson(url) {
  const r = await fetch(url, { headers: UA, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function googleOnce(text, target, source, alts) {
  const url = "https://translate.googleapis.com/translate_a/single?client=gtx&dt=t" +
    (alts ? "&dt=at" : "") + `&sl=${source}&tl=${target}&q=${encodeURIComponent(text)}`;
  const data = await getJson(url);
  const out = (data[0] || []).filter((p) => p && p[0]).map((p) => p[0]).join("").trim();
  if (!alts) return { text: out, others: [] };
  const others = [];
  // Other ways to say it, only when the whole text is one segment.
  if (Array.isArray(data[5]) && data[5].length === 1) {
    for (const a of (data[5][0].length > 2 ? data[5][0][2] : null) || []) {
      if (a && typeof a[0] === "string") others.push(a[0].trim());
    }
  }
  return { text: out, others };
}

async function google(text, target, source = "auto", alts = false) {
  try {
    return await googleOnce(text, target, source, alts);
  } catch {
    await sleep(2000); // Google sometimes refuses a burst of requests; try once more
    return googleOnce(text, target, source, alts);
  }
}

async function myMemory(text, source, target) {
  const data = await getJson(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}` +
    `&langpair=${encodeURIComponent(`${source}|${target}`)}`);
  return ((data.responseData || {}).translatedText || "").trim();
}

async function searchTerms(text, userLang = "en") {
  text = text.trim();
  const terms = [];
  if (/[A-Za-zÀ-ÿ]/.test(text) && !PERSIAN.test(text)) terms.push(text);
  for (const target of TARGETS) {
    let word = "";
    try {
      word = (await google(text, target)).text;
    } catch {
      try {
        word = await myMemory(text, userLang || "en", target);
      } catch {
        word = "";
      }
    }
    if (word && !PERSIAN.test(word)) terms.push(word);
  }
  if (!terms.length) terms.push(text);
  const seen = new Set();
  return terms.filter((t) => {
    const k = t.toLowerCase();
    if (seen.has(k) || t.length > 60) return false;
    seen.add(k);
    return true;
  });
}

const key = (s) => s.toLowerCase().normalize("NFKD").replace(/[^\x00-\x7f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();

function sameThing(a, b) {
  const wa = new Set(key(a).split(" ").filter(Boolean));
  const wb = new Set(key(b).split(" ").filter(Boolean));
  const sub = (x, y) => [...x].every((w) => y.has(w));
  return wa.size > 0 && wb.size > 0 && (sub(wa, wb) || sub(wb, wa));
}

/** [search words, similar names] for something a user wants. */
export async function expand(text, userLang = "en") {
  text = text.trim();
  const terms = await searchTerms(text, userLang);
  const english = new Set();
  const alts = new Map();
  for (const target of TARGETS) {
    let res;
    try {
      res = await google(text, target, "auto", true);
    } catch {
      continue;
    }
    if (target === "en") [res.text, ...res.others].forEach((e) => english.add(e));
    for (const o of res.others) if (!alts.has(o)) alts.set(o, target);
    await sleep(300);
  }
  if (!english.size) return [terms, []];
  const known = new Set(terms.map(key));
  const similar = [];
  for (const [alt, lang] of alts) {
    if (known.has(key(alt)) || similar.some((x) => key(x) === key(alt)) || alt.length > 60) continue;
    if (lang !== "en") {
      let back;
      try {
        back = (await google(alt, "en", lang)).text;
      } catch {
        continue;
      }
      await sleep(300);
      if (![...english].some((e) => sameThing(back, e))) continue;
    }
    similar.push(alt);
  }
  return [terms, similar];
}
