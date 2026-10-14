#!/usr/bin/env bash
# Stops the bot and removes the systemd service created by install_service.sh.
set -euo pipefail
NAME=marketplace-radar
sudo systemctl disable --now $NAME 2>/dev/null || true
sudo rm -f /etc/systemd/system/$NAME.service
sudo systemctl daemon-reload
echo "Removed '$NAME'."
