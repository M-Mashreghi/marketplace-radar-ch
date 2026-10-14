// Searching ricardo.ch. A port of ricardo.py: only the plain search page
// (/de/s/<words>/) is read, as Ricardo's robots.txt allows; the results are
// for all of Switzerland and are filtered by seller postcode in geo.js.

import { fetchText, nextData, slugify } from "./anibis.js";

export const BASE = "https://www.ricardo.ch";

export function searchUrl(text) {
  return `${BASE}/de/s/${encodeURIComponent(text.trim())}/`;
}

function money(v) {
  if (v === null || v === undefined || v === "" || v === 0) return "";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const [i, d] = n.toFixed(2).split(".");
  return `${i.replace(/\B(?=(\d{3})+(?!\d))/g, "'")}.${d}`;
}

function image(node) {
  for (const key of ["image", "imageUrl", "image_url", "thumbnail", "mainImage", "picture"]) {
    const v = node[key];
    if (typeof v === "string" && v.startsWith("http")) return v;
    if (v && typeof v === "object") {
      for (const k of ["url", "src", "large", "medium"]) {
        if (typeof v[k] === "string" && v[k].startsWith("http")) return v[k];
      }
    }
  }
  const imgs = node.images;
  if (Array.isArray(imgs) && imgs.length) {
    if (typeof imgs[0] === "string") return imgs[0];
    if (imgs[0] && typeof imgs[0] === "object") return imgs[0].url || imgs[0].src || "";
  }
  return "";
}

/** Walk the page data and collect anything that looks like an article. */
function fromJson(nd) {
  const found = new Map();
  const walk = (o) => {
    if (Array.isArray(o)) return o.forEach(walk);
    if (!o || typeof o !== "object") return;
    const aid = o.id || o.articleId;
    const title = o.title;
    if (aid && typeof title === "string" && /^\d{6,}$/.test(String(aid)) &&
        ["buyNowPrice", "bidPrice", "price", "currentBidPrice", "startPrice"].some((k) => k in o)) {
      const buy = o.buyNowPrice || (o.price && typeof o.price !== "object" ? o.price : null);
      const bid = o.bidPrice || o.currentBidPrice || o.startPrice;
      const parts = [];
      if (bid) parts.push(`🔨 ${money(bid)}`);
      if (buy) parts.push(`🛒 ${money(buy)}`);
      const link = o.url || o.link || `/de/a/${slugify(title)}-${aid}/`;
      const desc = o.description || o.subtitle || "";
      if (!found.has(String(aid))) {
        found.set(String(aid), {
          site: "ricardo", id: String(aid), title: title.trim(),
          description: typeof desc === "string" ? desc.trim() : "",
          price: parts.join(" · "),
          place: typeof o.location === "string" ? o.location : "",
          photo: image(o), time: o.startDate || "",
          url: new URL(link, BASE).href,
        });
      }
    }
    Object.values(o).forEach(walk);
  };
  walk(nd);
  return [...found.values()];
}

/** The search page has a schema.org ItemList (JSON-LD) with every result. */
function fromLd(page) {
  const m = page.match(/<script type="application\/ld\+json" id="srps-json-ld">([\s\S]*?)<\/script>/);
  if (!m) return [];
  let data;
  try {
    data = JSON.parse(m[1]);
  } catch {
    return [];
  }
  const items = [];
  for (const g of data["@graph"] || []) {
    if (g["@type"] !== "ItemList") continue;
    for (const el of g.itemListElement || []) {
      const prod = el.item || {};
      const url = prod.url || "";
      const aid = url.match(/-(\d{6,})\/?$/);
      if (!aid || !prod.name) continue;
      const offers = prod.offers || {};
      const price = offers && typeof offers === "object" && !Array.isArray(offers) ? money(offers.price) : "";
      let img = prod.image;
      if (Array.isArray(img)) img = img[0] || "";
      items.push({
        site: "ricardo", id: aid[1], title: prod.name.trim(), description: "",
        price: price ? `${price} CHF` : "", place: "",
        photo: typeof img === "string" ? img : "", time: "", url,
      });
    }
  }
  return items;
}

/** End index (exclusive) of the JSON value that starts at s[start]. */
function jsonEnd(s, start) {
  let depth = 0;
  let inStr = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (c === "\\") i++;
      else if (c === '"') inStr = false;
    } else if (c === '"') inStr = true;
    else if (c === "{" || c === "[") depth++;
    else if (c === "}" || c === "]") {
      depth--;
      if (depth === 0) return i + 1;
    }
  }
  return -1;
}

/** The page's own data (Next.js stream) has every article with the seller's
 *  postcode and town. */
function fromRsc(page, urls) {
  const chunks = [...page.matchAll(/self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)/g)].map((m) => m[1]);
  let s;
  try {
    s = chunks.map((c) => JSON.parse(`"${c}"`)).join("");
  } catch {
    return [];
  }
  const items = new Map();
  for (const m of s.matchAll(/\{"id":"(\d{6,})","title":/g)) {
    const end = jsonEnd(s, m.index);
    if (end < 0) continue;
    let o;
    try {
      o = JSON.parse(s.slice(m.index, end));
    } catch {
      continue;
    }
    if (items.has(o.id) || typeof o.title !== "string") continue;
    const ship = (o.shipping || []).filter((x) => x && typeof x === "object");
    const loc = ship.find((x) => x.zipCode) || {};
    const parts = [];
    if (o.hasAuction && o.bidPrice !== null && o.bidPrice !== undefined) parts.push(`🔨 ${money(o.bidPrice) || "0"} CHF`);
    if (o.buyNowPrice) parts.push(`🛒 ${money(o.buyNowPrice)} CHF`);
    items.set(o.id, {
      site: "ricardo", id: o.id, title: o.title.trim(), description: "",
      price: parts.join(" · "),
      place: [loc.city, loc.zipCode].filter(Boolean).join(", "),
      postcode: String(loc.zipCode || ""),
      pickup: ship.some((x) => x.key === "get_by_buyer"),
      photo: typeof o.image === "string" ? o.image : "",
      time: o.startDate || "",
      url: urls[o.id] || `${BASE}/de/a/${slugify(o.title)}-${o.id}/`,
    });
  }
  return [...items.values()];
}

/** Fallback: article links look like /de/a/<slug>-<id>/. */
function fromLinks(page) {
  const items = new Map();
  for (const m of page.matchAll(/href="(\/(?:de|fr|it)\/a\/([^"/]*?)-(\d{6,})\/?)"[^>]*>([\s\S]*?)<\/a>/g)) {
    const [, href, , aid, inner] = m;
    if (!items.has(aid)) {
      items.set(aid, { site: "ricardo", id: aid, title: "", description: "", price: "", place: "", photo: "", time: "", url: BASE + href });
    }
    const it = items.get(aid);
    const text = inner.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (text.length > it.title.length) it.title = text.slice(0, 150);
    const img = inner.match(/<img[^>]+src="(https:\/\/img\.ricardostatic\.ch\/[^"]+)"/);
    if (img && !it.photo) it.photo = img[1];
  }
  for (const it of items.values()) {
    if (!it.title) it.title = it.url.replace(/\/+$/, "").split("/").pop().replace(/-[^-]*$/, "").replaceAll("-", " ");
  }
  return [...items.values()];
}

export function parseSearchPage(page) {
  const ld = fromLd(page);
  let items = fromRsc(page, Object.fromEntries(ld.map((i) => [i.id, i.url])));
  if (items.length) return items;
  items = ld;
  if (!items.length) {
    const nd = nextData(page);
    items = nd ? fromJson(nd) : [];
  }
  return items.length ? items : fromLinks(page);
}

export async function search(text) {
  return parseSearchPage(await fetchText(searchUrl(text)));
}
