// End-to-end test of the Worker in the real Workers runtime (Miniflare), with
// a local D1 database. Nothing goes to the internet: Telegram, the marketplaces
// and Google Translate are answered from saved pages in tests/fixtures.
//   cd cloudflare && npm test
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import * as miniflare from "miniflare";

const root = new URL("../../", import.meta.url);
const fixture = (name) => readFileSync(new URL(`tests/fixtures/${name}`, root), "utf8");
const ANIBIS = fixture("anibis_search_lausanne.html");
const RICARDO = fixture("ricardo_search.html");
const TOKEN = "123456:TEST";
const CHAT = 4242;

const WORDS = { de: "Velo", fr: "vélo", it: "bicicletta", en: "bicycle" };
const calls = []; // Telegram API calls the Worker made
const fetched = []; // other URLs it fetched

function telegram(method, body) {
  calls.push({ method, body });
  const result = {
    getMe: { username: "test_bot" },
    sendMessage: { message_id: calls.length },
    sendPhoto: { message_id: calls.length },
  }[method] ?? true;
  return Response.json({ ok: true, result });
}

/** The locality the Worker asked for, read back from the search URL. */
function locality(url) {
  const token = url.pathname.split("/").pop();
  const bytes = Buffer.from(token.slice(1), "base64url").toString("latin1");
  return (bytes.match(/geo-[a-z-]+/) || [null])[0];
}

async function outbound(request) {
  const url = new URL(request.url);
  if (url.hostname === "api.telegram.org") {
    return telegram(url.pathname.split("/").pop(), await request.json());
  }
  fetched.push(url.href);
  if (url.hostname === "www.anibis.ch" || url.hostname === "www.tutti.ch") {
    const loc = locality(url);
    // The fixture is the Lausanne town page; Anibis knows other ids only as "Lausanne" region/canton Vaud.
    const known = { "geo-city-lausanne": "Lausanne", "geo-region-lausanne": "Lausanne", "geo-canton-vaud": "Waadt" };
    if (loc && !known[loc]) return new Response(ANIBIS.replaceAll("geo-city-lausanne", "geo-unknown"));
    return new Response(loc ? ANIBIS.replaceAll("geo-city-lausanne", loc).replaceAll('"name":"Lausanne"', `"name":"${known[loc]}"`) : ANIBIS);
  }
  if (url.hostname === "www.ricardo.ch") return new Response(RICARDO);
  if (url.hostname === "translate.googleapis.com") {
    const tl = url.searchParams.get("tl");
    const word = WORDS[tl] ?? "bike";
    return Response.json([[[word, url.searchParams.get("q"), null, null, 1]], null, "en"]);
  }
  return new Response("unexpected request in test: " + url.href, { status: 500 });
}

const dist = new URL("../dist/", import.meta.url);
const txt = readdirSync(dist).find((f) => f.endsWith(".txt"));
const options = {
  modules: [
    { type: "ESModule", path: new URL("index.js", dist).pathname },
    { type: "Text", path: new URL(txt, dist).pathname },
  ],
  compatibilityDate: "2026-10-01",
  d1Databases: ["DB"],
  bindings: { TELEGRAM_BOT_TOKEN: TOKEN, ALLOWED_CHAT_IDS: "" },
  outboundService: outbound,
};
// Miniflare 5 takes a new option format and converts the classic one.
const mf = new miniflare.Miniflare(miniflare.convertV4MiniflareOptions ? miniflare.convertV4MiniflareOptions(options) : options);

const secret = createHash("sha256").update(`webhook:${TOKEN}`).digest("hex").slice(0, 48);
let updateId = 1000;
const post = (update, headers = { "X-Telegram-Bot-Api-Secret-Token": secret }) =>
  mf.dispatchFetch("https://radar.example.workers.dev/telegram", { method: "POST", headers, body: JSON.stringify(update) });
const from = { id: CHAT, first_name: "Test", language_code: "en" };
const chat = { id: CHAT, type: "private" };
const say = (text) => post({ update_id: ++updateId, message: { message_id: updateId, from, chat, text } });
const press = (data) => post({ update_id: ++updateId, callback_query: { id: `cb${updateId}`, from, data, message: { message_id: 1, chat } } });
const sent = () => calls.filter((c) => c.method === "sendMessage" || c.method === "sendPhoto");
const lastText = () => { const s = sent().at(-1); return s.body.text ?? s.body.caption; };
const cron = async () => (await mf.getWorker()).scheduled({ cron: "* * * * *" });
let step = 0;
const ok = (what) => console.log(`ok ${++step} - ${what}`);

try {
  // /setup connects the webhook and checks every site
  let r = await mf.dispatchFetch("https://radar.example.workers.dev/setup");
  const page = await r.text();
  assert.equal(r.status, 200, page);
  const hook = calls.find((c) => c.method === "setWebhook").body;
  assert.equal(hook.url, "https://radar.example.workers.dev/telegram");
  assert.equal(hook.secret_token, secret);
  assert.ok(calls.some((c) => c.method === "setMyCommands"));
  assert.match(page, /30 listings on the first page/);
  assert.match(page, /60 results for "velo"/);
  ok("/setup sets the webhook and the self-test passes");

  r = await post({ update_id: 1, message: { from, chat, text: "/start" } }, {});
  assert.equal(r.status, 403);
  ok("webhook calls without the secret are refused");

  await say("/start");
  assert.equal(lastText(), "Choose the bot's language:");
  assert.equal(sent().at(-1).body.reply_markup.inline_keyboard.length, 4);
  r = await post({ update_id: updateId, message: { message_id: 1, from, chat, text: "/start" } });
  assert.equal(sent().length, 1);
  ok("/start asks for the language; a resent update is handled once");

  await press("lang:en");
  assert.match(lastText(), /^Hi! 👋/);
  await say("Lausanne");
  const opts = sent().at(-1).body.reply_markup.inline_keyboard.map((row) => row[0].text);
  assert.deepEqual(opts.slice(0, 6), ["📍 Lausanne (town only) · 26'833 listings", "⭕ Lausanne + 5 km", "⭕ Lausanne + 10 km",
    "⭕ Lausanne + 20 km", "⭕ Lausanne + 50 km", "🗺 Lausanne region · 26'833 listings"]);
  assert.equal(opts.at(-2), "🏔 Canton Waadt · 26'833 listings");
  ok("typing a town lists the town, radius, region and canton options");

  await press("loc:2");
  assert.match(lastText(), /Area: <b>Lausanne \+ 10 km<\/b>|Lausanne \+ 10 km/);
  const n0 = sent().length;
  await cron();
  const init = sent().slice(n0);
  const photos = init.filter((c) => c.method === "sendPhoto");
  assert.equal(photos.length, 1, "the fixture has one free listing (anibis and tutti copies are sent once)");
  assert.match(photos[0].body.caption, /🏷 anibis\.ch/);
  assert.match(init.at(-1).body.text, /anibis\.ch/);
  assert.match(init.at(-1).body.text, /ricardo\.ch/);
  ok("choosing an area runs the first check on the next cron run: free items + report");

  await say("velo");
  assert.match(lastText(), /<b>velo · vélo · bicicletta · bicycle<\/b>/);
  await press("wish:yes");
  assert.match(lastText(), /price/i);
  await say("20-500");
  assert.match(lastText(), /20–500 CHF/);
  const n1 = sent().length;
  await cron();
  const wish = sent().slice(n1);
  const titles = wish.filter((c) => c.method === "sendPhoto").map((c) => c.body.caption.split("\n")[0]);
  assert.ok(titles.some((x) => x.includes("Fourche Suntour neuve pour vélo Cargo")), titles.join("\n"));
  for (const c of wish.filter((x) => x.method === "sendPhoto")) {
    const m = c.body.caption.match(/💰 (.*)/);
    assert.ok(m, c.body.caption);
  }
  // Ricardo has 60 results per search word (3 words) for all of Switzerland; 2 sellers are within 10 km, neither selling a "velo".
  assert.match(wish.at(-1).body.text, /seller in Lausanne \+ 10 km \(10 km\), by postcode · out of 180 results/);
  ok(`a new item is translated, priced and searched on all three sites (${titles.length} listings)`);

  const n2 = sent().length;
  await cron();
  assert.equal(sent().length, n2);
  ok("nothing is due a minute later");

  await say("/check");
  await cron();
  const check = sent().slice(n2);
  assert.equal(check.filter((c) => c.method === "sendPhoto").length, 0, "no listing is sent twice");
  assert.match(check.at(-1).body.text, /Sent 0 new listings/);
  ok("/check runs a search and reports; already-sent listings are not repeated");

  const d1 = await mf.getD1Database("DB");
  await d1.prepare("UPDATE users SET last_check = last_check - 7300").run();
  const n3 = sent().length;
  await cron();
  assert.match(sent().at(-1).body.text, /Sent 0 new listings/);
  assert.equal(sent().length, n3 + 1);
  ok("the 2-hourly check runs when it is due");

  await say("/list");
  assert.match(lastText(), /velo · 💰 20–500 CHF/);
  await press("del:1");
  assert.match(lastText(), /velo/);
  await say("/stop");
  assert.match(lastText(), /stopped/i);
  ok("/list, removing an item and /stop work");

  const db = await mf.getD1Database("DB");
  const user = await db.prepare("SELECT * FROM users").first();
  assert.equal(user.active, 0);
  assert.equal(user.loc_id, "geo-city-lausanne");
  assert.equal((await db.prepare("SELECT COUNT(*) AS n FROM jobs").first()).n, 0);
  ok("database state is consistent");
  console.log(`\nall ${step} passed (${fetched.length} marketplace/translate requests, ${calls.length} Telegram calls)`);
} finally {
  await mf.dispose();
}
