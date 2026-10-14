// The bot's database on Cloudflare D1. Same tables as bot.db in the Python
// version (so an existing bot.db can be copied over, see tools/export_to_d1.py),
// plus `jobs` (work waiting for the next cron run) and `updates` (Telegram
// updates already handled, so a retried webhook isn't handled twice).

export const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
    chat_id      TEXT PRIMARY KEY,
    name         TEXT,
    lang         TEXT,
    loc_id       TEXT,
    loc_radius   INTEGER,
    loc_label    TEXT,
    free_on      INTEGER DEFAULT 1,
    active       INTEGER DEFAULT 1,
    pending      TEXT,
    last_check   REAL DEFAULT 0,
    created      REAL,
    sites        TEXT DEFAULT 'anibis,tutti,ricardo',
    ricardo_area TEXT
);
CREATE TABLE IF NOT EXISTS wishes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   TEXT,
    keyword   TEXT,
    terms     TEXT,
    created   REAL,
    similar   TEXT,
    min_price REAL,
    max_price REAL
);
CREATE TABLE IF NOT EXISTS seen (
    chat_id    TEXT,
    search_key TEXT,
    listing_id TEXT,
    PRIMARY KEY (chat_id, search_key, listing_id)
);
CREATE TABLE IF NOT EXISTS sent (
    chat_id    TEXT,
    listing_id TEXT,
    sent_at    REAL,
    PRIMARY KEY (chat_id, listing_id)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind    TEXT,
    chat_id TEXT,
    only    TEXT,
    created REAL,
    taken   REAL
);
CREATE TABLE IF NOT EXISTS updates (update_id INTEGER PRIMARY KEY, at REAL);
CREATE INDEX IF NOT EXISTS seen_key ON seen (chat_id, search_key);
`;

const now = () => Date.now() / 1000;
const clean = (args) => args.map((a) => (a === undefined ? null : a));
let ready = false; // schema created in this isolate

export class DB {
  constructor(d1) {
    this.d1 = d1;
  }

  stmt(sql, args = []) {
    const s = this.d1.prepare(sql);
    return args.length ? s.bind(...clean(args)) : s;
  }

  async init() {
    if (ready) return;
    // D1's batch runs these in one transaction; exec() would also work but
    // can't take statements with newlines inside them.
    const parts = SCHEMA.split(";").map((s) => s.trim()).filter(Boolean);
    await this.d1.batch(parts.map((p) => this.d1.prepare(p)));
    ready = true;
  }

  async q(sql, args = []) {
    return (await this.stmt(sql, args).all()).results;
  }

  async x(sql, args = []) {
    return (await this.stmt(sql, args).run()).meta;
  }

  // users
  async user(chatId) {
    return (await this.q("SELECT * FROM users WHERE chat_id=?", [chatId]))[0] || null;
  }

  async ensureUser(chatId, name, lang) {
    await this.x("INSERT OR IGNORE INTO users (chat_id, name, lang, created) VALUES (?,?,?,?)", [chatId, name, lang, now()]);
    return this.user(chatId);
  }

  async set(chatId, fields) {
    const keys = Object.keys(fields);
    await this.x(`UPDATE users SET ${keys.map((k) => `${k}=?`).join(", ")} WHERE chat_id=?`, [...keys.map((k) => fields[k]), chatId]);
  }

  pending(user) {
    try {
      return JSON.parse(user.pending || "null") || {};
    } catch {
      return {};
    }
  }

  async setPending(chatId, data) {
    await this.set(chatId, { pending: data ? JSON.stringify(data) : null });
  }

  // wishes
  async wishes(chatId) {
    return this.q("SELECT * FROM wishes WHERE chat_id=? ORDER BY id", [chatId]);
  }

  async addWish(chatId, keyword, terms, similar) {
    const meta = await this.x("INSERT INTO wishes (chat_id, keyword, terms, similar, created) VALUES (?,?,?,?,?)",
      [chatId, keyword, JSON.stringify(terms), JSON.stringify(similar || []), now()]);
    return meta.last_row_id;
  }

  async wish(chatId, wishId) {
    return (await this.q("SELECT * FROM wishes WHERE chat_id=? AND id=?", [chatId, wishId]))[0] || null;
  }

  async setPrice(chatId, wishId, lo, hi) {
    await this.x("UPDATE wishes SET min_price=?, max_price=? WHERE chat_id=? AND id=?", [lo, hi, chatId, wishId]);
    // Start this item fresh, so listings that now fit the range are sent.
    await this.x("DELETE FROM seen WHERE chat_id=? AND search_key LIKE ?", [chatId, `w${wishId}@%`]);
  }

  async delWish(chatId, wishId) {
    const w = await this.wish(chatId, wishId);
    await this.x("DELETE FROM wishes WHERE chat_id=? AND id=?", [chatId, wishId]);
    await this.x("DELETE FROM seen WHERE chat_id=? AND search_key LIKE ?", [chatId, `w${wishId}@%`]);
    return w ? w.keyword : null;
  }

  // seen / sent
  async seenIds(chatId, key) {
    const rows = await this.q("SELECT listing_id FROM seen WHERE chat_id=? AND search_key=?", [chatId, key]);
    return new Set(rows.map((r) => r.listing_id));
  }

  async markSeen(chatId, key, ids) {
    const list = [...ids];
    for (let i = 0; i < list.length; i += 50) { // one round trip per 50 rows
      await this.d1.batch(list.slice(i, i + 50).map((id) => this.stmt("INSERT OR IGNORE INTO seen VALUES (?,?,?)", [chatId, key, id])));
    }
  }

  async wasSent(chatId, listingId) {
    return (await this.q("SELECT 1 AS x FROM sent WHERE chat_id=? AND listing_id=?", [chatId, listingId])).length > 0;
  }

  async markSent(chatId, listingId) {
    await this.x("INSERT OR IGNORE INTO sent VALUES (?,?,?)", [chatId, listingId, now()]);
  }

  async resetSearches(chatId) {
    await this.x("DELETE FROM seen WHERE chat_id=?", [chatId]);
  }

  // jobs: ("check" | "init" | "wish", chat, only)
  async addJob(kind, chatId, only = null) {
    await this.x("INSERT INTO jobs (kind, chat_id, only, created) VALUES (?,?,?,?)", [kind, chatId, only, now()]);
  }

  /** Take the oldest waiting job, atomically, so two cron runs never do the same one. */
  async takeJob() {
    await this.x("DELETE FROM jobs WHERE taken IS NOT NULL AND taken < ?", [now() - 1800]);
    return (await this.q(
      "UPDATE jobs SET taken=? WHERE id=(SELECT id FROM jobs WHERE taken IS NULL ORDER BY id LIMIT 1) RETURNING *",
      [now()]))[0] || null;
  }

  async doneJob(id) {
    await this.x("DELETE FROM jobs WHERE id=?", [id]);
  }

  /** Take the user whose regular check is most overdue, atomically. */
  async takeDueUser(everySeconds) {
    return (await this.q(
      "UPDATE users SET last_check=? WHERE chat_id=(SELECT chat_id FROM users WHERE active=1 AND loc_id IS NOT NULL " +
      "AND last_check < ? ORDER BY last_check LIMIT 1) RETURNING *", [now(), now() - everySeconds]))[0] || null;
  }

  /** True the first time an update id is seen. */
  async firstTime(updateId) {
    const meta = await this.x("INSERT OR IGNORE INTO updates VALUES (?,?)", [updateId, now()]);
    if (Math.random() < 0.02) await this.x("DELETE FROM updates WHERE at < ?", [now() - 7 * 86400]);
    return meta.changes > 0;
  }

  async meta(key, dflt = null) {
    const rows = await this.q("SELECT value FROM meta WHERE key=?", [key]);
    return rows.length ? rows[0].value : dflt;
  }

  async setMeta(key, value) {
    await this.x("INSERT OR REPLACE INTO meta VALUES (?,?)", [key, String(value)]);
  }
}
