"""Copy the bot's messages from texts.py into cloudflare/src/texts.json, so the
Cloudflare version says exactly what the Python version says.
Run after changing texts.py:   python cloudflare/scripts/export_texts.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import texts  # noqa: E402

out = ROOT / "cloudflare" / "src" / "texts.json"
out.write_text(json.dumps({"LANGS": texts.LANGS, "T": texts.T}, ensure_ascii=False, indent=1) + "\n",
               encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)}")
