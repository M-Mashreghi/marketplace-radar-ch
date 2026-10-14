"""Copy everyone's settings from bot.db (the Python version) to the Cloudflare
version, so nobody has to set the bot up again after the move.

    python tools/export_to_d1.py              -> writes d1_import.sql
    cd cloudflare
    npx wrangler d1 execute marketplace-radar --remote --file ../d1_import.sql

d1_import.sql contains every user's chat id and wish list: it is in
.gitignore, never commit it, and delete it once imported.
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anibis_alert import DATA_DIR  # noqa: E402

TABLES = {  # table -> columns copied (the Cloudflare schema has the same ones)
    "users": ["chat_id", "name", "lang", "loc_id", "loc_radius", "loc_label", "free_on", "active",
              "last_check", "created", "sites", "ricardo_area"],
    "wishes": ["id", "chat_id", "keyword", "terms", "created", "similar", "min_price", "max_price"],
    "seen": ["chat_id", "search_key", "listing_id"],
    "sent": ["chat_id", "listing_id", "sent_at"],
}


def sql_value(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def main():
    db_file = DATA_DIR / "bot.db"
    if not db_file.exists():
        sys.exit(f"{db_file} not found. Run this in the folder where the Python bot ran.")
    con = sqlite3.connect(str(db_file))
    out = ROOT / "d1_import.sql"
    lines = []
    for table, cols in TABLES.items():
        have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        use = [c for c in cols if c in have]
        rows = con.execute(f"SELECT {', '.join(use)} FROM {table}").fetchall()
        for row in rows:
            lines.append(f"INSERT OR REPLACE INTO {table} ({', '.join(use)}) VALUES "
                         f"({', '.join(sql_value(v) for v in row)});")
        print(f"{table}: {len(rows)} rows")
    out.write_text(CREATE + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.name}")


# The tables, in case the Worker hasn't created them yet (same as cloudflare/src/db.js).
CREATE = """CREATE TABLE IF NOT EXISTS users (chat_id TEXT PRIMARY KEY, name TEXT, lang TEXT, loc_id TEXT,
  loc_radius INTEGER, loc_label TEXT, free_on INTEGER DEFAULT 1, active INTEGER DEFAULT 1, pending TEXT,
  last_check REAL DEFAULT 0, created REAL, sites TEXT DEFAULT 'anibis,tutti,ricardo', ricardo_area TEXT);
CREATE TABLE IF NOT EXISTS wishes (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, keyword TEXT, terms TEXT,
  created REAL, similar TEXT, min_price REAL, max_price REAL);
CREATE TABLE IF NOT EXISTS seen (chat_id TEXT, search_key TEXT, listing_id TEXT,
  PRIMARY KEY (chat_id, search_key, listing_id));
CREATE TABLE IF NOT EXISTS sent (chat_id TEXT, listing_id TEXT, sent_at REAL, PRIMARY KEY (chat_id, listing_id));
"""

if __name__ == "__main__":
    main()
