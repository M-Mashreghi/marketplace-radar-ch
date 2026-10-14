// Talking to anibis.ch and tutti.ch (same platform): search URLs, results,
// locations. A port of anibis.py; see that file for the details.

export const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36";
export const SITES = { anibis: "https://www.anibis.ch", tutti: "https://www.tutti.ch" };
const RADII_KM = [5, 10, 20, 50];

// Canton short name (as Anibis returns it) -> candidate locality ids.
const CANTON_IDS = {
  AG: ["aargau", "argovie"], AI: ["appenzell-innerrhoden", "appenzell-rhodes-interieures"],
  AR: ["appenzell-ausserrhoden", "appenzell-rhodes-exterieures"], BE: ["bern", "berne"],
  BL: ["basel-landschaft", "bale-campagne"], BS: ["basel-stadt", "bale-ville"],
  FR: ["fribourg", "freiburg"], GE: ["geneve", "genf", "geneva"], GL: ["glarus", "glaris"],
  GR: ["graubunden", "grisons", "graubuenden"], JU: ["jura"], LU: ["luzern", "lucerne"],
  NE: ["neuchatel", "neuenburg"], NW: ["nidwalden", "nidwald"], OW: ["obwalden", "obwald"],
  SG: ["st-gallen", "saint-gall", "sankt-gallen"], SH: ["schaffhausen", "schaffhouse"],
  SO: ["solothurn", "soleure"], SZ: ["schwyz"], TG: ["thurgau", "thurgovie"],
  TI: ["ticino", "tessin"], UR: ["uri"], VD: ["vaud", "waadt"], VS: ["valais", "wallis"],
  ZG: ["zug", "zoug"], ZH: ["zurich", "zuerich"],
};
// Common alternative names people type -> Anibis slug.
const ALIASES = {
  geneva: "geneve", genf: "geneve", ginevra: "geneve", zuerich: "zurich", zurigo: "zurich",
  biel: "biel-bienne", bienne: "biel-bienne", sitten: "sion", lucerne: "luzern",
  berne: "bern", bale: "basel", basle: "basel", neuenburg: "neuchatel",
  freiburg: "fribourg", waadt: "vaud", wallis: "valais", tessin: "ticino",
  "st-gall": "st-gallen", "saint-gall": "st-gallen", "sankt-gallen": "st-gallen",
};

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ------------------------------------------------------------------ low level

function msgpack(o) {
  if (o === null || o === undefined) return [0xc0];
  if (o === true) return [0xc3];
  if (o === false) return [0xc2];
  if (typeof o === "number") {
    if (o >= 0 && o < 128) return [o];
    return [0xcd, (o >> 8) & 0xff, o & 0xff];
  }
  if (typeof o === "string") {
    const b = [...new TextEncoder().encode(o)];
    if (b.length < 32) return [0xa0 | b.length, ...b];
    return [0xd9, b.length, ...b];
  }
  if (Array.isArray(o)) return [0x90 | o.length, ...o.flatMap(msgpack)];
  throw new TypeError(String(o));
}

function b64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function slugify(s) {
  return (s || "")
    .normalize("NFKD")
    .replace(/[^\x00-\x7f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function searchUrl(text, locality, radius, page = 1, site = "anibis", lang = "de") {
  const loc = locality ? [["location", locality, radius || null]] : null;
  const token = "A" + b64url(msgpack([text || null, null, [null, null, null, loc]]));
  const url = `${SITES[site]}/${lang}/q/${slugify(text || "") || "inserate"}/${token}`;
  return url + (page > 1 ? `?page=${page}` : "");
}

export async function fetchText(url) {
  const r = await fetch(url, {
    headers: {
      "User-Agent": USER_AGENT,
      "Accept-Language": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7",
      Accept: "text/html,application/xhtml+xml",
    },
    signal: AbortSignal.timeout(30000),
  });
  const body = await r.text();
  if (!r.ok) throw new Error(`HTTP Error ${r.status}: ${r.statusText || "error"}`);
  return body;
}

export function nextData(page) {
  const m = page.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  return m ? JSON.parse(m[1]) : null;
}

function searchData(nd) {
  for (const q of nd?.props?.pageProps?.dehydratedState?.queries || []) {
    if ((q.queryKey || [null])[0] === "SearchListingsByConstraints") return q.state.data;
  }
  return null;
}

// ------------------------------------------------------------------ search

function listing(node, site) {
  const loc = node.localization || {};
  const pc = node.postcodeInformation || {};
  const canton = pc.canton || {};
  const thumb = node.thumbnail || {};
  const photo = (thumb.retinaRendition || {}).src || (thumb.normalRendition || {}).src || "";
  const slug = (node.seoInformation || {}).deSlug;
  const lid = String(node.listingID);
  const base = SITES[site];
  return {
    site,
    id: lid,
    title: (loc.title || "").trim(),
    description: (loc.body || "").trim(),
    price: (node.formattedPrice || "").trim(),
    place: [pc.locationName, pc.postcode].filter(Boolean).join(", "),
    postcode: String(pc.postcode || ""),
    canton: canton.shortName || "",
    canton_name: canton.name || "",
    photo,
    time: node.timestamp || "",
    url: slug ? `${base}/de/vi/${slug}/${lid}` : `${base}/de/vi/${lid}`,
  };
}

/** One page (about 30 listings, newest first) of an Anibis or tutti search. */
export function parseSearchPage(html, page = 1, site = "anibis") {
  const nd = nextData(html);
  const data = nd ? searchData(nd) : null;
  if (!data) throw new Error(`${site}: page layout not recognised (no search data)`);
  const edges = (data.listings || {}).edges || [];
  const listings = edges.filter((e) => e.node).map((e) => listing(e.node, site));
  const total = (data.listings || {}).totalCount ?? null;
  let localities = [];
  for (const f of data.filters || []) {
    if (f.name === "location") localities = (f.value || {}).selectedLocalities || [];
  }
  let served = page;
  const p = nd?.props?.pageProps?.initialReduxState?.searchResultPage?.page;
  if (p !== undefined && p !== null) served = p;
  return { listings, total, localities, page: served };
}

export async function search(text, locality, radius, page = 1, site = "anibis") {
  return parseSearchPage(await fetchText(searchUrl(text, locality, radius, page, site)), page, site);
}

/** Listings not in seenIds, reading further pages while everything is new. */
export async function searchNew(text, locality, radius, seenIds, maxPages = 5, site = "anibis") {
  const found = [];
  const ids = new Set();
  for (let page = 1; page <= maxPages; page++) {
    const res = await search(text, locality, radius, page, site);
    if (res.page !== page) break; // the site ignored the page number
    const fresh = res.listings.filter((l) => !seenIds.has(l.id) && !ids.has(l.id));
    found.push(...fresh);
    fresh.forEach((l) => ids.add(l.id));
    if (fresh.length < res.listings.length || !res.listings.length) break;
    await sleep(1000);
  }
  return found;
}

export function isFree(listing) {
  const price = listing.price || "";
  return /gratis|gratuit|gratuito|free|verschenk/i.test(price) || /^(CHF\s*)?0+(\.0+)?(\.-)?$/.test(price.trim());
}

// ------------------------------------------------------------------ locations

async function probe(locality, radius = null) {
  let res;
  try {
    res = await search(null, locality, radius);
  } catch {
    return null;
  }
  for (const loc of res.localities) {
    if (loc.localityID === locality) return { name: loc.name || locality, total: res.total, res };
  }
  return null;
}

export function mostCommon(values) {
  const counts = new Map();
  for (const v of values) counts.set(v, (counts.get(v) || 0) + 1);
  let best = null;
  for (const [v, n] of counts) if (best === null || n > counts.get(best)) best = v;
  return best;
}

/** All Anibis location options matching what the user typed:
 *  [{id, radius, name, kind: city|region|canton, total}] */
export async function findLocations(userText) {
  const base = slugify(userText);
  if (!base) return [];
  const variants = [base];
  for (const [a, b] of [["ae", "a"], ["oe", "o"], ["ue", "u"]]) {
    if (base.includes(a) && !variants.includes(base.replaceAll(a, b))) variants.push(base.replaceAll(a, b));
  }
  for (const v of [...variants]) {
    if (ALIASES[v] && !variants.includes(ALIASES[v])) variants.push(ALIASES[v]);
  }

  const options = [];
  const cantons = [];
  for (const v of variants) {
    const city = await probe(`geo-city-${v}`);
    if (city) {
      options.push({ id: `geo-city-${v}`, radius: null, name: city.name, kind: "city", total: city.total });
      for (const km of RADII_KM) options.push({ id: `geo-city-${v}`, radius: km, name: city.name, kind: "city", total: null });
      cantons.push(...city.res.listings.map((l) => l.canton).filter(Boolean));
      break;
    }
  }
  for (const v of variants) {
    const region = await probe(`geo-region-${v}`);
    if (region) {
      options.push({ id: `geo-region-${v}`, radius: null, name: region.name, kind: "region", total: region.total });
      break;
    }
  }
  // Canton: the one the user typed, or the one most listings in the town are in.
  let candidates = [...variants];
  if (cantons.length) candidates = [...(CANTON_IDS[mostCommon(cantons)] || []), ...candidates];
  for (const v of [...new Set(candidates)]) {
    const canton = await probe(`geo-canton-${v}`);
    if (canton) {
      options.push({ id: `geo-canton-${v}`, radius: null, name: canton.name, kind: "canton", total: canton.total });
      break;
    }
  }
  return options;
}
