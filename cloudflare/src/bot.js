// The bot itself: conversation, searching and sending. A port of bot.py for
// Cloudflare Workers. Differences from the Python version:
//  * Telegram sends each message to the Worker (webhook) instead of the bot
//    asking for them (long polling).
//  * Searches don't run in a background thread: /check, a new area or a new
//    item becomes a row in `jobs`, and a cron trigger every minute does the
//    waiting jobs, then the users whose 2-hourly check is due.

import * as anibis from "./anibis.js";
import * as geo from "./geo.js";
import * as ricardo from "./ricardo.js";
import * as translate from "./translate.js";
import TEXTS from "./texts.json";

export const CHECK_EVERY_HOURS = 2;
const MAX_WISHES = 20;
const MAX_ALERTS_PER_CHECK = 50; // new listings per user per check, so a broken page can't flood anyone
const FIRST_MAX = 100; // "everything listed now" for a new area or item, per search
const FREE_PAGES = 5;
const WISH_PAGES = 2;
const FIRST_WISH_PAGES = 3;
const ALL_SITES = ["anibis", "tutti", "ricardo"];
const FREE_SITES = ["anibis", "tutti"]; // Ricardo has no free listings and no area filter
export const SITE_NAMES = { anibis: "anibis.ch", tutti: "tutti.ch", ricardo: "ricardo.ch" };
export const LANGS = TEXTS.LANGS;
const sleep = anibis.sleep;
const now = () => Date.now() / 1000;
const log = (...a) => console.log(...a);

export function t(key, lang, kw = null) {
  const entry = TEXTS.T[key];
  const text = entry[lang] || entry.en;
  return kw ? text.replace(/\{(\w+)\}/g, (m, k) => (k in kw ? String(kw[k]) : m)) : text;
}

// ------------------------------------------------------------------ Telegram

export class Telegram {
  constructor(token) {
    this.base = `https://api.telegram.org/bot${token}/`;
  }

  async call(method, params = {}) {
    const body = {};
    for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) body[k] = v;
    for (let attempt = 0; ; attempt++) {
      const r = await fetch(this.base + method, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const res = await r.json().catch(() => ({}));
      if (res.ok) return res.result;
      const wait = (res.parameters || {}).retry_after;
      if (r.status === 429 && wait && attempt < 2) { // too many messages: wait as Telegram asks
        await sleep((wait + 1) * 1000);
        continue;
      }
      throw new Error(`${method}: ${res.description || `HTTP ${r.status}`}`);
    }
  }

  send(chat, text, buttons = null, preview = false) {
    return this.call("sendMessage", {
      chat_id: chat, text, parse_mode: "HTML", disable_web_page_preview: !preview,
      reply_markup: buttons ? { inline_keyboard: buttons } : null,
    });
  }
}

export function esc(s) {
  return String(s ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
const escAttr = (s) => esc(s).replaceAll('"', "&quot;").replaceAll("'", "&#x27;");

export function caption(item, why, lang) {
  const site = SITE_NAMES[item.site] || "anibis.ch";
  const parts = [`🆕 <b>${esc(item.title)}</b>`, `🏷 ${site}`];
  if (item.price) parts.push(`💰 ${esc(item.price)}`);
  if (item.place) parts.push(`📍 ${esc(item.place)}`);
  if (why) parts.push(t("match", lang, { what: esc(why) }));
  const desc = (item.description || "").trim();
  if (desc) parts.push("", esc(desc.slice(0, 450) + (desc.length > 450 ? "…" : "")));
  parts.push("", `<a href="${escAttr(item.url)}">${t("open", lang, { site })}</a>`, esc(item.url));
  let text = parts.join("\n");
  if (text.length > 1024) text = [...parts.slice(0, 5), "", ...parts.slice(-2)].join("\n"); // photo caption limit
  return text;
}

async function sendListing(tg, chat, item, why, lang) {
  const cap = caption(item, why, lang);
  if (item.photo) {
    try {
      return await tg.call("sendPhoto", { chat_id: chat, photo: item.photo, caption: cap, parse_mode: "HTML" });
    } catch (e) {
      log(`[!] sendPhoto failed, sending text: ${e.message}`);
    }
  }
  return tg.call("sendMessage", { chat_id: chat, text: cap, parse_mode: "HTML" });
}

// ------------------------------------------------------------------ searching

function locLabel(opt, lang) {
  let key = { city: "opt_city", region: "opt_region", canton: "opt_canton" }[opt.kind];
  if (opt.kind === "city" && opt.radius) key = "opt_radius";
  return t(key, lang, { name: opt.name, km: opt.radius || "" }).replace(/^[^\p{L}\p{N}_]+/u, "").trim();
}

function userSites(user) {
  return (user.sites || ALL_SITES.join(",")).split(",").filter((x) => ALL_SITES.includes(x));
}

async function userSearches(db, user) {
  const out = [];
  if (user.free_on) out.push({ key: "free", label: t("free_label", user.lang), terms: [null], similar: [], free: true, pages: FREE_PAGES, lo: null, hi: null });
  for (const w of await db.wishes(user.chat_id)) {
    const parsed = JSON.parse(w.terms || "[]");
    const terms = parsed.length ? parsed : [w.keyword];
    let similar;
    if (w.similar === null) { // item added by an older version: look the names up once
      try {
        similar = (await translate.expand(w.keyword, user.lang || "en"))[1];
      } catch {
        similar = [];
      }
      await db.x("UPDATE wishes SET similar=? WHERE id=?", [JSON.stringify(similar), w.id]);
    } else similar = JSON.parse(w.similar || "[]");
    out.push({ key: `w${w.id}`, label: w.keyword, terms, similar, free: false, pages: WISH_PAGES, lo: w.min_price, hi: w.max_price });
  }
  return out;
}

export function priceValue(item) {
  let p = item.price || "";
  if (anibis.isFree(item)) return 0;
  if (p.includes("🛒")) p = p.split("🛒").slice(1).join("🛒");
  const m = p.match(/\d[\d'’ ]*(?:[.,]\d{1,2})?/);
  if (!m) return null;
  const v = Number(m[0].replace(/['’ ]/g, "").replace(",", "."));
  return Number.isNaN(v) ? null : v;
}

export function inPriceRange(item, lo, hi) {
  if (lo === null && hi === null) return true;
  const v = priceValue(item);
  if (v === null) return true; // "price on request" and the like: keep, it may fit
  return (lo === null || v >= lo) && (hi === null || v <= hi);
}

/** '20-100', '20 100', '-100' (max only), '20-' (min only), '0' or '-' (no limit).
 *  Returns [min, max] or null if it can't be read. */
export function parsePriceRange(text) {
  const from = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩";
  text = [...text].map((c) => (from.includes(c) ? String(from.indexOf(c) % 10) : c)).join("");
  text = text.replace(/chf|fr\.?|\.-|['’]/gi, "").trim();
  text = text.replace(/\s*[-–—]\s*|\s+(?:to|bis|à|a|تا)\s+/g, "-");
  text = text.replace(/\s+/g, "-");
  if (["", "-", "0", "0-0"].includes(text)) return [null, null];
  if (/^\d+(?:[.,]\d+)?$/.test(text)) text = "-" + text; // one number = the most you'll pay
  const m = text.match(/^(\d+(?:[.,]\d+)?)?-(\d+(?:[.,]\d+)?)?$/);
  if (!m) return null;
  let [lo, hi] = [m[1], m[2]].map((x) => (x ? Number(x.replace(",", ".")) : null));
  lo = lo || null;
  if (lo !== null && hi !== null && lo > hi) [lo, hi] = [hi, lo];
  return [lo, hi];
}

const fmt = (v) => Math.round(v).toLocaleString("en-US").replaceAll(",", "'");

export function priceLabel(lo, hi, lang) {
  lo = lo ?? null;
  hi = hi ?? null;
  if (lo === null && hi === null) return t("price_any", lang);
  if (hi === null) return t("price_from", lang, { lo: fmt(lo) });
  if (lo === null) return t("price_upto", lang, { hi: fmt(hi) });
  return `${fmt(lo)}–${fmt(hi)} CHF`;
}

const STOP_WORDS = new Set(["les", "des", "une", "pour", "avec", "sans", "und", "der", "die", "das", "ein", "eine",
  "mit", "von", "fur", "the", "and", "for", "with", "del", "della", "per", "con", "uno", "una"]);
const LONG_WORD = 10; // a word this long is specific on its own ("multiprise", "bicyclette")
const PLURAL_ENDINGS = ["s", "es", "e", "en", "n", "x"];

const words = (s) => anibis.slugify(s).split("-").filter((w) => w.length >= 3 && !STOP_WORDS.has(w));

/** w, its plural, or a compound containing it is among the title's words. */
function wordIn(w, titleWords) {
  for (const x of titleWords) {
    if (x === w || (w.length >= 6 && x.includes(w))) return true;
    if (x.startsWith(w) && PLURAL_ENDINGS.includes(x.slice(w.length))) return true;
    if (x.length >= 4 && w.startsWith(x) && PLURAL_ENDINGS.includes(w.slice(x.length))) return true;
    if (w.length >= 5 && x.length === w.length && x.slice(0, -1) === w.slice(0, -1) &&
        "aeio".includes(x.at(-1)) && "aeio".includes(w.at(-1))) return true; // bicicletta / biciclette
  }
  return false;
}

/** Is this listing really about `term`? Every word of the term must be in the
 *  title, except that one long, specific word is enough. */
export function titleMatches(title, term) {
  const ws = words(term);
  const tw = words(title);
  if (!ws.length || !tw.length) return false;
  if (ws.some((w) => w.length >= LONG_WORD && wordIn(w, tw))) return true;
  return ws.every((w) => wordIn(w, tw));
}

export function classify(title, terms, similar) {
  if (terms.some((x) => titleMatches(title, x))) return "exact";
  if (similar.some((x) => titleMatches(title, x))) return "similar";
  return null;
}

/** Everything to type into the sites' search box for one item. */
function searchWords(terms, similar) {
  const out = [];
  const keys = new Set();
  const longs = terms.filter((x) => words(x).length > 1).flatMap((x) => words(x).filter((w) => w.length >= LONG_WORD));
  for (const x of [...terms, ...longs, ...similar]) {
    const k = anibis.slugify(x);
    if (k && !keys.has(k)) {
      keys.add(k);
      out.push(x);
    }
  }
  return out;
}

/** Where the user's area is, for keeping Ricardo results by seller postcode. */
async function ricardoArea(db, user) {
  if (user.ricardo_area) {
    try {
      return JSON.parse(user.ricardo_area);
    } catch { /* look it up again */ }
  }
  const locId = user.loc_id || "";
  const kind = (locId.match(/-/g) || []).length >= 2 ? locId.split("-")[1] : "city";
  const name = locId.split("-").slice(2).join("-") || locId;
  const listings = await anibis.searchNew(null, user.loc_id, user.loc_radius, new Set(), 3, "anibis");
  const area = geo.makeArea(kind, name, user.loc_radius, listings);
  if (area.lat || (area.zips || []).length) {
    await db.set(user.chat_id, { ricardo_area: JSON.stringify(area) });
    return area;
  }
  return null;
}

/** One word on one site -> {items, places, all}. */
async function runSearch(site, term, user, seen, pages, firstTime, cache, area) {
  const ck = JSON.stringify([site, term, user.loc_id, user.loc_radius, firstTime, pages]);
  if (cache.has(ck)) return cache.get(ck);
  let out;
  if (site === "ricardo") {
    const items = await ricardo.search(term);
    const kept = area ? items.filter((i) => geo.inArea(area, i.postcode)) : items;
    out = { items: kept, places: null, all: items.length };
  } else if (firstTime) {
    const res = await anibis.search(term, user.loc_id, user.loc_radius, 1, site);
    const items = [...res.listings];
    const ids = new Set(items.map((i) => i.id));
    for (let page = 2; page <= pages; page++) {
      if (res.listings.length < 20) break; // that was the last page
      await sleep(1000);
      const res2 = await anibis.search(term, user.loc_id, user.loc_radius, page, site);
      if (res2.page !== page) break;
      const more = res2.listings.filter((i) => !ids.has(i.id));
      if (!more.length) break;
      items.push(...more);
      more.forEach((i) => ids.add(i.id));
      if (res2.listings.length < 20) break;
    }
    out = { items, places: res.localities.map((l) => l.name).filter(Boolean), all: res.total };
  } else {
    out = { items: await anibis.searchNew(term, user.loc_id, user.loc_radius, seen, pages, site), places: null, all: null };
  }
  cache.set(ck, out);
  return out;
}

function siteSearchUrl(site, term, user) {
  if (site === "ricardo") return term ? ricardo.searchUrl(term) : ricardo.BASE;
  return anibis.searchUrl(term, user.loc_id, user.loc_radius, 1, site);
}

/** Same ad posted on several sites -> same fingerprint, so it's sent once. */
function fingerprint(item) {
  return "fp:" + `${item.title ?? "None"}|${item.price ?? "None"}|${item.place ?? "None"}`.toLowerCase().replace(/[^\p{L}\p{N}_]+/gu, "").slice(0, 120);
}

const siteLink = (site, url) => `<a href="${escAttr(url)}">${SITE_NAMES[site]}</a>`;

function buildReport(user, rows, sent, kind, area) {
  const lang = user.lang || "en";
  const lines = [t(`rep_head_${kind}`, lang, { label: esc(user.loc_label) })];
  let anyFirst = false;
  for (const [label, siteRows] of rows) {
    lines.push("", `<b>${esc(label)}</b>`);
    for (const r of siteRows) {
      const name = siteLink(r.site, r.url);
      if (r.status === "off") lines.push(t("rep_off", lang, { site: SITE_NAMES[r.site] }));
      else if (r.status === "no_free") lines.push(t("rep_ricardo_free", lang, { site: name }));
      else if (r.status === "error") lines.push(t("rep_err", lang, { site: name, err: esc(r.err).slice(0, 120) }));
      else {
        let where;
        if (r.site === "ricardo") {
          where = area ? t("rep_ric_area", lang, { label: esc(user.loc_label), d: geo.describe(area), all: r.all || 0 }) : t("rep_all_ch", lang);
        } else if (r.places !== null && !r.places.length) where = t("rep_noloc", lang);
        else where = esc(r.places && r.places.length ? r.places.join(", ") : user.loc_label);
        anyFirst = anyFirst || r.first;
        lines.push(t(r.first ? "rep_first" : "rep_ok", lang, { site: name, where, n: r.n, new: r.new }));
      }
    }
  }
  if (kind === "init" && !rows.some(([label]) => label !== t("free_label", lang))) lines.push("", t("rep_no_wishes", lang));
  lines.push("");
  if (anyFirst) lines.push(t("rep_first_note", lang));
  if (kind !== "init" && kind !== "wish") lines.push(t("rep_sent", lang, { n: sent }));
  return lines.join("\n");
}

/** Search all of a user's sites, send listings and (optionally) a report.
 *  report: null, "init" (new area), "wish" (new item), "check" (/check),
 *  "auto" (the 2-hourly run). only: just this search key (e.g. "w12"). */
export async function checkUser(tg, db, user, report = null, cache = new Map(), only = null) {
  const chat = user.chat_id;
  const lang = user.lang || "en";
  if (!user.loc_id) return 0;
  const sites = userSites(user);
  let area = null;
  if (sites.includes("ricardo")) {
    try {
      area = await ricardoArea(db, user);
    } catch (e) {
      log(`[!] Ricardo area for ${chat} failed: ${e.message}`);
    }
  }
  let sent = 0;
  const rows = [];
  for (const s of await userSearches(db, user)) {
    if (only && s.key !== only) continue;
    const ws = s.free ? [null] : searchWords(s.terms, s.similar);
    const toSend = [];
    const siteRows = [];
    let anyFirst = false;
    for (const site of ALL_SITES) {
      const url = siteSearchUrl(site, s.terms[0], user);
      if (!sites.includes(site)) {
        siteRows.push({ site, status: "off", url });
        continue;
      }
      if (s.free && !FREE_SITES.includes(site)) {
        siteRows.push({ site, status: "no_free", url });
        continue;
      }
      const skey = `${s.key}@${site}`;
      const seen = await db.seenIds(chat, skey);
      const firstTime = seen.size === 0;
      anyFirst = anyFirst || firstTime;
      const nPages = !firstTime || s.free ? s.pages : FIRST_WISH_PAGES;
      const ids = new Set();
      const got = new Map();
      const errors = [];
      let places = null;
      let total = 0;
      for (const word of ws) {
        let res;
        try {
          res = await runSearch(site, word, user, seen, nPages, firstTime, cache, area);
        } catch (e) {
          log(`[!] ${site} search failed (${s.label} / ${word}): ${e.message}`);
          errors.push(e.message);
          continue;
        }
        if (res.places !== null) places = [...new Set([...(places || []), ...res.places])].sort();
        total += res.all || 0;
        for (const i of res.items) {
          ids.add(i.id);
          if (seen.has(i.id) || got.has(i.id)) continue;
          if (s.free) {
            if (anibis.isFree(i)) got.set(i.id, [i, "exact"]);
            continue;
          }
          const kind = classify(i.title, s.terms, s.similar);
          if (kind && inPriceRange(i, s.lo ?? null, s.hi ?? null)) got.set(i.id, [i, kind]);
        }
        await sleep(1000);
      }
      if (errors.length && !ids.size) {
        siteRows.push({ site, status: "error", err: errors[0], url });
        continue;
      }
      await db.markSeen(chat, skey, ids.size ? ids : ["-"]);
      const items = [...got.values()].sort((a, b) => (a[1] !== "exact") - (b[1] !== "exact")); // exact matches first
      toSend.push(...items);
      siteRows.push({ site, status: "ok", first: firstTime, n: items.length, new: firstTime ? 0 : items.length,
        places, url, all: total });
    }
    const hasRange = (s.lo ?? null) !== null || (s.hi ?? null) !== null;
    rows.push([s.label + (s.free || !hasRange ? "" : ` · 💰 ${priceLabel(s.lo, s.hi, lang)}`), siteRows]);
    // One message per listing: photo, details and its own link.
    const limit = anyFirst ? FIRST_MAX : MAX_ALERTS_PER_CHECK;
    const fresh = [];
    const freshFps = new Set();
    for (const [item, kind] of toSend) {
      const sid = `${item.site}:${item.id}`;
      const fp = fingerprint(item);
      if (!(await db.wasSent(chat, sid)) && !(await db.wasSent(chat, fp)) && !freshFps.has(fp)) {
        fresh.push([item, kind]);
        freshFps.add(fp);
      }
    }
    if (anyFirst && fresh.length) {
      try {
        await tg.send(chat, t("now_head", lang, { label: esc(s.label), n: Math.min(fresh.length, limit) }));
      } catch (e) {
        log(`[!] could not send to ${chat}: ${e.message}`);
      }
    }
    for (const [n, [item, kind]] of fresh.entries()) {
      if (n >= limit) {
        await tg.send(chat, t("now_more", lang, { n: limit, rest: fresh.length - limit })).catch(() => {});
        break;
      }
      const sid = `${item.site}:${item.id}`;
      const why = s.label + (kind === "similar" ? " · " + t("similar_tag", lang) : "");
      try {
        await sendListing(tg, chat, item, why, lang);
        await db.markSent(chat, sid);
        await db.markSent(chat, fingerprint(item));
        sent++;
        await sleep(1200);
      } catch (e) {
        log(`[!] could not send ${sid} to ${chat}: ${e.message}`);
        const msg = e.message.toLowerCase();
        if (msg.includes("blocked") || msg.includes("chat not found")) {
          await db.set(chat, { active: 0 });
          return sent;
        }
      }
    }
  }
  await db.set(chat, { last_check: now() });
  if (report) {
    try {
      await tg.send(chat, buildReport(await db.user(chat), rows, sent, report, area));
    } catch (e) {
      log(`[!] report to ${chat} failed: ${e.message}`);
    }
  }
  return sent;
}

/** One cron run: waiting jobs first (/check, new area, new item), then the
 *  users whose regular check is due. New work is only started while the run is
 *  younger than budgetMs; the next run (a minute later) carries on. Several
 *  runs may overlap; each job and user is taken by exactly one of them. */
export async function work(tg, db, budgetMs = 45000) {
  const start = Date.now();
  const cache = new Map(); // searches shared within this run
  let done = 0;
  while (Date.now() - start < budgetMs) {
    const job = await db.takeJob();
    if (job) {
      try {
        const user = await db.user(job.chat_id);
        if (user) await checkUser(tg, db, user, job.kind, new Map(), job.only);
      } catch (e) {
        log(`[!] job ${job.kind} for ${job.chat_id} failed: ${e.stack || e}`);
      }
      await db.doneJob(job.id);
      done++;
      continue;
    }
    const user = await db.takeDueUser(CHECK_EVERY_HOURS * 3600);
    if (!user) break;
    try {
      const n = await checkUser(tg, db, user, "auto", cache);
      log(`checked ${user.chat_id}: ${n} sent`);
    } catch (e) {
      log(`[!] checking ${user.chat_id} failed: ${e.stack || e}`);
    }
    done++;
  }
  return done;
}

// ------------------------------------------------------------------ conversation

function siteButtons(user) {
  const on = userSites(user);
  return ALL_SITES.map((s) => [{ text: `${on.includes(s) ? "✅" : "⬜"} ${SITE_NAMES[s]}`, callback_data: `site:${s}` }]);
}

const langButtons = () => Object.entries(LANGS).map(([code, label]) => [{ text: label, callback_data: `lang:${code}` }]);

const yesNo = (lang, tag) => [[{ text: t("yes", lang), callback_data: `${tag}:yes` }, { text: t("no", lang), callback_data: `${tag}:no` }]];

async function askRegion(tg, db, user) {
  await db.setPending(user.chat_id, { type: "await_region" });
  await tg.send(user.chat_id, t("ask_region", user.lang));
}

async function handleRegionText(tg, db, user, text) {
  const chat = user.chat_id;
  const lang = user.lang;
  await tg.send(chat, t("searching_loc", lang, { q: esc(text) }));
  const options = await anibis.findLocations(text);
  if (!options.length) {
    await db.setPending(chat, { type: "await_region" });
    await tg.send(chat, t("loc_not_found", lang, { q: esc(text) }));
    return;
  }
  await db.setPending(chat, { type: "choose_loc", options });
  const buttons = options.map((opt, i) => {
    let label = t(opt.radius ? "opt_radius" : { city: "opt_city", region: "opt_region", canton: "opt_canton" }[opt.kind], lang,
      { name: opt.name, km: opt.radius || "" });
    if (opt.total) label += ` · ${t("listings_count", lang, { n: opt.total.toLocaleString("en-US").replaceAll(",", "'") })}`;
    return [{ text: label, callback_data: `loc:${i}` }];
  });
  buttons.push([{ text: t("opt_other", lang), callback_data: "loc:other" }]);
  await tg.send(chat, t("loc_choose", lang), buttons);
}

async function startWish(tg, db, user, keyword) {
  const chat = user.chat_id;
  const lang = user.lang;
  keyword = keyword.trim().slice(0, 60);
  if (!user.loc_id) return tg.send(chat, t("need_region", lang));
  const wishes = await db.wishes(chat);
  if (wishes.some((w) => w.keyword.toLowerCase() === keyword.toLowerCase())) return tg.send(chat, t("already", lang, { kw: esc(keyword) }));
  if (wishes.length >= MAX_WISHES) return tg.send(chat, t("too_many", lang, { n: MAX_WISHES }));
  await tg.send(chat, t("translating", lang, { kw: esc(keyword) }));
  const [terms, similar] = await translate.expand(keyword, lang);
  await db.setPending(chat, { type: "confirm_wish", keyword, terms, similar });
  let text = t("confirm_terms", lang, { kw: esc(keyword), terms: esc(terms.join(" · ")) });
  if (similar.length) text = text.replace("\n\n", "\n" + t("confirm_similar", lang, { names: esc(similar.join(" · ")) }) + "\n\n");
  await tg.send(chat, text, yesNo(lang, "wish"));
}

function zurichTime(seconds) {
  return new Date(seconds * 1000).toLocaleString("sv-SE", { timeZone: "Europe/Zurich" }).slice(0, 16);
}

async function showList(tg, db, user) {
  const chat = user.chat_id;
  const lang = user.lang;
  if (!user.loc_id) return tg.send(chat, t("need_region", lang));
  const wishes = await db.wishes(chat);
  const items = wishes.map((w) => `  • ${esc(w.keyword)} · 💰 ${priceLabel(w.min_price, w.max_price, lang)}` +
    `\n    <i>(${esc([...JSON.parse(w.terms), ...JSON.parse(w.similar || "[]")].join(" · "))})</i>`).join("\n") || t("list_empty", lang);
  const last = user.last_check ? zurichTime(user.last_check) : "-";
  const buttons = wishes.map((w) => [{ text: `💰 ${w.keyword}`, callback_data: `price:${w.id}` }, { text: `🗑 ${w.keyword}`, callback_data: `del:${w.id}` }]);
  await tg.send(chat, t("list", lang, { label: esc(user.loc_label), free: t(user.free_on ? "on" : "off", lang), items, last }),
    buttons.length ? buttons : null);
}

async function askPrice(tg, db, chat, lang, wishId, keyword, isNew) {
  await db.setPending(chat, { type: "await_price", wish: wishId, keyword, new: isNew });
  const w = (await db.wish(chat, wishId)) || {};
  const cur = isNew ? "" : "\n" + t("price_now", lang, { range: priceLabel(w.min_price, w.max_price, lang) });
  await tg.send(chat, t("ask_price", lang, { kw: esc(keyword) }) + cur, [[{ text: t("price_skip", lang), callback_data: "pskip:1" }]]);
}

async function setPrice(tg, db, user, pending, [lo, hi]) {
  const chat = user.chat_id;
  const lang = user.lang;
  await db.setPending(chat, null);
  if (!(await db.wish(chat, pending.wish))) return;
  await db.setPrice(chat, pending.wish, lo, hi);
  if (pending.new) {
    await tg.send(chat, t("added", lang, { kw: esc(pending.keyword), label: esc(user.loc_label), hours: CHECK_EVERY_HOURS }) +
      "\n💰 " + priceLabel(lo, hi, lang));
  } else await tg.send(chat, t("price_set", lang, { kw: esc(pending.keyword), range: priceLabel(lo, hi, lang) }));
  await db.addJob("wish", chat, `w${pending.wish}`); // send what's listed now in that range
}

async function handleText(tg, db, user, text) {
  const chat = user.chat_id;
  const lang = user.lang;
  text = text.trim();
  const sp = text.indexOf(" ");
  let cmd = sp < 0 ? text : text.slice(0, sp);
  const arg = sp < 0 ? "" : text.slice(sp + 1).trim();
  cmd = cmd.toLowerCase().split("@")[0];
  const pending = db.pending(user);

  if (cmd === "/start") {
    await db.set(chat, { active: 1 });
    await db.setPending(chat, { type: "await_lang" });
    await tg.send(chat, t("choose_lang", lang), langButtons());
  } else if (["/language", "/lang", "/sprache", "/langue"].includes(cmd)) {
    await db.setPending(chat, { type: "await_lang_only" });
    await tg.send(chat, t("choose_lang", lang), langButtons());
  } else if (cmd === "/region") await askRegion(tg, db, user);
  else if (cmd === "/sites" || cmd === "/site") await tg.send(chat, t("sites", lang), siteButtons(user));
  else if (cmd === "/help") await tg.send(chat, t("help", lang));
  else if (cmd === "/add") {
    if (arg) await startWish(tg, db, user, arg);
    else {
      await db.setPending(chat, { type: "await_wish" });
      await tg.send(chat, t("add_usage", lang));
    }
  } else if (cmd === "/remove") {
    const match = (await db.wishes(chat)).find((w) => w.keyword.toLowerCase() === arg.toLowerCase());
    if (match) {
      await db.delWish(chat, match.id);
      await tg.send(chat, t("removed", lang, { kw: esc(match.keyword) }));
    } else await showList(tg, db, await db.user(chat));
  } else if (cmd === "/list") await showList(tg, db, user);
  else if (cmd === "/free") {
    await db.set(chat, { free_on: user.free_on ? 0 : 1 });
    if (user.free_on) await db.x("DELETE FROM seen WHERE chat_id=? AND search_key LIKE 'free@%'", [chat]);
    await tg.send(chat, t("free_toggled", lang, { state: t(user.free_on ? "off" : "on", lang) }));
  } else if (cmd === "/check") {
    if (!user.loc_id) await tg.send(chat, t("need_region", lang));
    else {
      await tg.send(chat, t("checking", lang));
      await db.addJob("check", chat);
    }
  } else if (cmd === "/stop") {
    await db.set(chat, { active: 0 });
    await tg.send(chat, t("stopped", lang));
  } else if (cmd === "/price") {
    const wishes = await db.wishes(chat);
    if (!wishes.length) await tg.send(chat, t("add_usage", lang));
    else {
      await tg.send(chat, t("price_choose", lang), wishes.map((w) => [{
        text: `💰 ${w.keyword} (${priceLabel(w.min_price, w.max_price, lang)})`, callback_data: `price:${w.id}`,
      }]));
    }
  } else if (cmd.startsWith("/")) await tg.send(chat, t("help", lang));
  else if (pending.type === "await_price") {
    const rng = parsePriceRange(text);
    if (rng === null) await tg.send(chat, t("price_bad", lang), [[{ text: t("price_skip", lang), callback_data: "pskip:1" }]]);
    else await setPrice(tg, db, user, pending, rng);
  } else if (pending.type === "await_region" || pending.type === "choose_loc" || !user.loc_id) {
    await handleRegionText(tg, db, user, text);
  } else await startWish(tg, db, user, text); // plain text = something they want
}

async function handleButton(tg, db, user, cb) {
  const chat = user.chat_id;
  await tg.call("answerCallbackQuery", { callback_query_id: cb.id }).catch(() => {});
  const data = cb.data || "";
  const i = data.indexOf(":");
  const tag = i < 0 ? data : data.slice(0, i);
  const value = i < 0 ? "" : data.slice(i + 1);
  const pending = db.pending(user);

  if (tag === "lang" && value in LANGS) {
    await db.set(chat, { lang: value });
    user = await db.user(chat);
    await tg.send(chat, t("lang_set", value));
    if (pending.type === "await_lang" || !user.loc_id) {
      await tg.send(chat, t("welcome", value));
      await db.setPending(chat, { type: "await_region" });
    } else await db.setPending(chat, null);
    return;
  }
  const lang = user.lang;
  if (tag === "site" && ALL_SITES.includes(value)) {
    let on = userSites(user);
    on = on.includes(value) ? on.filter((x) => x !== value) : [...on, value];
    on = ALL_SITES.filter((x) => on.includes(x));
    if (!on.length) on = ["anibis"];
    await db.set(chat, { sites: on.join(",") });
    await tg.call("editMessageReplyMarkup", { chat_id: chat, message_id: cb.message.message_id,
      reply_markup: { inline_keyboard: siteButtons(await db.user(chat)) } }).catch(() => {});
    return;
  }
  if (tag === "loc" && pending.type === "choose_loc") {
    if (value === "other") return askRegion(tg, db, user);
    const opt = pending.options[Number(value)];
    if (!opt) return;
    const label = locLabel(opt, lang);
    await db.set(chat, { loc_id: opt.id, loc_radius: opt.radius || null, loc_label: label, active: 1, ricardo_area: null });
    await db.resetSearches(chat); // new area: start fresh
    await db.setPending(chat, null);
    await tg.send(chat, t("region_saved", lang, { label: esc(label), hours: CHECK_EVERY_HOURS, free: t(user.free_on ? "on" : "off", lang) }));
    await db.addJob("init", chat);
  } else if (tag === "wish" && pending.type === "confirm_wish") {
    await db.setPending(chat, null);
    if (value === "yes") {
      const wid = await db.addWish(chat, pending.keyword, pending.terms, pending.similar);
      await askPrice(tg, db, chat, lang, wid, pending.keyword, true);
    } else await tg.send(chat, t("cancelled", lang));
  } else if (tag === "price" && /^\d+$/.test(value)) { // change the price range from /list
    const w = await db.wish(chat, Number(value));
    if (w) await askPrice(tg, db, chat, lang, w.id, w.keyword, false);
  } else if (tag === "pskip" && pending.type === "await_price") {
    await setPrice(tg, db, user, pending, [null, null]);
  } else if (tag === "del" && /^\d+$/.test(value)) {
    const kw = await db.delWish(chat, Number(value));
    if (kw) await tg.send(chat, t("removed", lang, { kw: esc(kw) }));
  }
}

export const COMMANDS = [
  ["start", "Start / Starten / Démarrer"], ["add", "Add item / Hinzufügen / Ajouter"],
  ["list", "My list / Liste"], ["free", "Free items on/off / Gratis"],
  ["check", "Search now / Jetzt suchen / Chercher"], ["region", "Change area / Gebiet / Zone"],
  ["language", "Language / Sprache / Langue / زبان"],
  ["sites", "Anibis / tutti / Ricardo"], ["price", "Price range / Preis / Prix / قیمت"], ["help", "Help / Hilfe / Aide"],
  ["stop", "Stop alerts / Stopp / Arrêter"],
].map(([command, description]) => ({ command, description }));

/** Handle one Telegram update (a message or a button press). */
export async function handleUpdate(tg, db, up, allowed) {
  const msg = up.message || {};
  const cb = up.callback_query || null;
  const frm = (cb || msg).from || {};
  const chatObj = msg.chat || ((cb || {}).message || {}).chat || {};
  const chat = chatObj.id === undefined ? "" : String(chatObj.id);
  if (!chat || (chatObj.type || "private") !== "private") return;
  if (allowed.size && !allowed.has(chat)) return;
  const tgLang = (frm.language_code || "en").slice(0, 2);
  const user = await db.ensureUser(chat, frm.first_name || "", tgLang in LANGS ? tgLang : "en");
  try {
    if (cb) await handleButton(tg, db, user, cb);
    else if (msg.text) await handleText(tg, db, user, msg.text);
  } catch (e) {
    log(`[!] handling message from ${chat} failed: ${e.stack || e}`);
  }
}
