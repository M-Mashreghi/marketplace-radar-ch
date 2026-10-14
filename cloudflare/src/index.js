// Cloudflare Worker entry point.
//   POST /telegram   Telegram sends every message here (webhook).
//   GET  /setup      Connects the bot to this Worker and checks that the
//                    marketplaces can be reached from Cloudflare. Open it once
//                    after every deploy.
//   cron (every minute)  /check, new areas and new items, then the 2-hourly
//                    checks that are due.
// Settings: the secret TELEGRAM_BOT_TOKEN (wrangler secret put) and, optionally,
// ALLOWED_CHAT_IDS (comma separated) in wrangler.toml [vars].

import * as anibis from "./anibis.js";
import * as ricardo from "./ricardo.js";
import { COMMANDS, Telegram, esc, handleUpdate, work } from "./bot.js";
import { DB } from "./db.js";

function settings(env) {
  const token = (env.TELEGRAM_BOT_TOKEN || "").trim();
  if (!token) throw new Error("TELEGRAM_BOT_TOKEN is not set. Run: npx wrangler secret put TELEGRAM_BOT_TOKEN");
  const allowed = new Set(String(env.ALLOWED_CHAT_IDS || "").split(/[,\s]+/).filter(Boolean));
  return { token, allowed, tg: new Telegram(token), db: new DB(env.DB) };
}

/** Secret Telegram sends with every webhook call, so nobody else can post
 *  fake messages to /telegram. Derived from the bot token: nothing extra to set. */
async function webhookSecret(token) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`webhook:${token}`));
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 48);
}

async function selfTest(tg) {
  const checks = [
    ["Telegram", async () => `bot @${(await tg.call("getMe")).username}`],
    ["anibis.ch", async () => {
      const r = await anibis.search(null, "geo-city-lausanne", null, 1, "anibis");
      return `${r.listings.length} listings on the first page`;
    }],
    ["tutti.ch", async () => {
      const r = await anibis.search(null, "geo-city-lausanne", null, 1, "tutti");
      return `${r.listings.length} listings on the first page`;
    }],
    ["ricardo.ch", async () => `${(await ricardo.search("velo")).length} results for "velo"`],
    ["Google Translate", async () => {
      const r = await fetch("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=en&tl=de&q=bike");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return `"bike" -> "${(await r.json())[0][0][0]}"`;
    }],
  ];
  const out = [];
  for (const [name, fn] of checks) {
    try {
      out.push([name, true, await fn()]);
    } catch (e) {
      out.push([name, false, e.message]);
    }
  }
  return out;
}

async function setup(request, env) {
  const { token, tg, db } = settings(env);
  await db.init();
  const last = Number(await db.meta("setup_at", 0));
  if (Date.now() / 1000 - last < 30) return new Response("Opened a moment ago; wait 30 seconds and reload.", { status: 429 });
  await db.setMeta("setup_at", Date.now() / 1000);

  const url = new URL("/telegram", request.url).href;
  const lines = [];
  try {
    await tg.call("setWebhook", {
      url, secret_token: await webhookSecret(token), max_connections: 10,
      allowed_updates: ["message", "callback_query"], drop_pending_updates: false,
    });
    await tg.call("setMyCommands", { commands: COMMANDS });
    lines.push(["Webhook", true, `Telegram now sends the bot's messages to ${url}`]);
  } catch (e) {
    lines.push(["Webhook", false, e.message]);
  }
  lines.push(...(await selfTest(tg)));
  const ok = lines.every((l) => l[1]);
  const rows = lines.map(([n, good, d]) => `<tr><td>${good ? "✅" : "❌"}</td><td>${esc(n)}</td><td>${esc(d)}</td></tr>`).join("");
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>marketplace-radar-ch setup</title>
<body style="font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.5">
<h1>marketplace-radar-ch</h1>
<p>${ok ? "Everything works. Open your bot in Telegram and send /start." :
    "Something failed (see below). If a marketplace fails, it may be blocking Cloudflare; the other sites keep working, and the Python version on your own computer is the fallback."}</p>
<table cellpadding="6">${rows}</table>
<p>Logs: <code>npx wrangler tail</code></p></body>`;
  return new Response(html, { status: ok ? 200 : 500, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

async function webhook(request, env) {
  const { token, allowed, tg, db } = settings(env);
  if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== (await webhookSecret(token))) {
    return new Response("forbidden", { status: 403 });
  }
  const update = await request.json();
  await db.init();
  // Telegram resends an update when the answer is slow; handle each one once.
  if (update.update_id !== undefined && !(await db.firstTime(update.update_id))) return new Response("ok");
  await handleUpdate(tg, db, update, allowed);
  return new Response("ok");
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    try {
      if (pathname === "/telegram" && request.method === "POST") return await webhook(request, env);
      if (pathname === "/setup") return await setup(request, env);
      if (pathname === "/") return new Response("marketplace-radar-ch is running. Open /setup after a deploy.");
      return new Response("not found", { status: 404 });
    } catch (e) {
      console.log(`[!] ${pathname}: ${e.stack || e}`);
      // Answer Telegram with 200 anyway, or it keeps resending the same update.
      return new Response(pathname === "/telegram" ? "ok" : `error: ${e.message}`, { status: pathname === "/telegram" ? 200 : 500 });
    }
  },

  async scheduled(controller, env, ctx) {
    const { tg, db } = settings(env);
    await db.init();
    const n = await work(tg, db);
    if (n) console.log(`cron: ${n} jobs/checks done`);
  },
};
