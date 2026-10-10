"""Entry point for Task Scheduler: starts the interactive Telegram bot (bot.py).
The bot keeps running, answers you in Telegram and searches Anibis every 2 hours.
If it is already running, this exits straight away.
The old one-shot check is still available: python anibis_alert.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "bot.py"), run_name="__main__")
