// Swiss postcodes -> coordinates, so Ricardo results can be kept to the
// user's area. A port of geo.py; the postcode list (GeoNames, CC BY 4.0) is the
// same ch_postcodes.txt, bundled into the Worker.

import POSTCODES from "../../ch_postcodes.txt";
import { mostCommon, slugify } from "./anibis.js";

const TOWN_KM = 6;
let zips = null; // postcode -> [lat, lon, canton]
let places = null; // slug of place name -> [lat, lon]

function load() {
  if (zips) return zips;
  zips = new Map();
  places = new Map();
  const rows = new Map();
  for (const line of POSTCODES.split(/\r?\n/)) {
    const f = line.split("\t");
    if (f.length < 11 || !f[9] || !f[10]) continue;
    const lat = Number(f[9]);
    const lon = Number(f[10]);
    if (!rows.has(f[1])) rows.set(f[1], []);
    rows.get(f[1]).push([lat, lon, f[4]]);
    const slug = slugify(f[2]);
    if (!places.has(slug)) places.set(slug, [lat, lon]);
  }
  for (const [z, pts] of rows) {
    zips.set(z, [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length, pts[0][2]]);
  }
  return zips;
}

export function km(a, b) {
  const r = (x) => (x * Math.PI) / 180;
  const [la1, lo1, la2, lo2] = [r(a[0]), r(a[1]), r(b[0]), r(b[1])];
  const h = Math.sin((la2 - la1) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin((lo2 - lo1) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

/** Describe the user's area from the Anibis location and its listings. */
export function makeArea(kind, name, radius, listings) {
  const zs = [...new Set(listings.map((l) => l.postcode).filter(Boolean))].sort();
  const cantons = listings.map((l) => l.canton).filter(Boolean);
  const canton = cantons.length ? mostCommon(cantons) : "";
  const data = load();
  if (kind === "canton" && canton) return { canton, zips: zs };
  const pts = zs.filter((z) => data.has(z)).map((z) => data.get(z).slice(0, 2));
  let center = null;
  if (kind === "city") center = places.get(slugify(name)) || null;
  if (!center && pts.length) {
    center = [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
  }
  if (center) {
    let dist;
    if (kind === "city") dist = radius || TOWN_KM;
    else { // region: cover where most of its listings are
      const d = pts.length ? pts.map((p) => km(center, p)).sort((a, b) => a - b) : [10];
      dist = Math.max(10, Math.round(d[d.length > 1 ? Math.floor(d.length * 0.9) - 1 : 0] + 3));
    }
    return { lat: center[0], lon: center[1], km: dist, canton, zips: zs };
  }
  return { zips: zs, canton };
}

export function inArea(area, postcode) {
  if (!area || !postcode) return false;
  const data = load();
  if ("lat" in area && data.has(postcode)) return km([area.lat, area.lon], data.get(postcode)) <= area.km;
  if (area.canton && !("lat" in area) && data.has(postcode)) return data.get(postcode)[2] === area.canton;
  // No coordinates: postcodes seen on Anibis for this area.
  return (area.zips || []).includes(postcode);
}

export function describe(area) {
  if (!area) return "";
  if ("lat" in area) return `${area.km} km`;
  if (area.canton && load().size) return area.canton;
  return `${(area.zips || []).length} PLZ`;
}
