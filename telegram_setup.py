"""Finish the Telegram setup: finds your chat id and sends a test message.

Steps:
  1. Paste your bot token into config.json ("telegram_bot_token").
  2. In Telegram, open your bot and send it any message (e.g. "hi").
  3. Run:  python telegram_setup.py
The chat id is saved into config.json. Nothing secret is printed.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).with_name("config.json")


def api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(url, data=data, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        return json.load(e)


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    token = cfg.get("telegram_bot_token", "").strip()
    if not token or token.startswith("PASTE_"):
        sys.exit("Put your bot token in config.json first.")

    me = api(token, "getMe")
    if not me.get("ok"):
        sys.exit("Telegram rejected the token. Check it in config.json.")
    print(f"Token OK, bot is @{me['result']['username']}")

    if not cfg.get("telegram_chat_id"):
        updates = api(token, "getUpdates").get("result", [])
        chats = [u["message"]["chat"]["id"] for u in updates if "message" in u]
        if not chats:
            sys.exit("No messages found. Send your bot a message in Telegram, then run this again.")
        cfg["telegram_chat_id"] = str(chats[-1])
        CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print("Chat id found and saved to config.json")

    sent = api(token, "sendMessage", {
        "chat_id": cfg["telegram_chat_id"],
        "text": "Anibis alarm is connected. New listings will show up here.",
    })
    if sent.get("ok"):
        print("Test message sent. Check Telegram!")
    else:
        sys.exit(f"Sending failed: {sent.get('description')}")


if __name__ == "__main__":
    main()
