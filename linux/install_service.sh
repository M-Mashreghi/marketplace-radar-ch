#!/usr/bin/env bash
# Runs the bot as a systemd service on Linux: it starts at boot, restarts if it
# crashes, and keeps running after you log out.
#   bash linux/install_service.sh          (asks for your sudo password)
# Logs:   journalctl -u marketplace-radar -f   (and anibis_alert.log)
# Stop:   bash linux/remove_service.sh
set -euo pipefail

NAME=marketplace-radar
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3 || true)"
RUN_AS="${SUDO_USER:-$(id -un)}"

if [ -z "$PYTHON" ]; then
    echo "python3 isn't installed. Install it first, e.g.: sudo apt install python3" >&2
    exit 1
fi
if [ ! -f "$DIR/config.json" ]; then
    echo "Create $DIR/config.json first (cp config.example.json config.json, then paste your token)." >&2
    exit 1
fi

UNIT="[Unit]
Description=marketplace-radar-ch Telegram bot (anibis, tutti, ricardo)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$RUN_AS
WorkingDirectory=$DIR
ExecStart=$PYTHON $DIR/bot.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"

echo "$UNIT" | sudo tee /etc/systemd/system/$NAME.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now $NAME
echo "Installed and started '$NAME' (runs as $RUN_AS from $DIR)."
echo "Status: systemctl status $NAME    Logs: journalctl -u $NAME -f"
