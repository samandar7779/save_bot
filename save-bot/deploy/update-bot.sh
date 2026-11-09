#!/usr/bin/env bash
# Kodni git orqali yangilash + kutubxonalarni yangilash + botni qayta ishga tushirish.
# Ishlatish: sudo /opt/save-bot/deploy/update-bot.sh
set -euo pipefail

APP_DIR="/opt/save-bot"

cd "${APP_DIR}"
echo "[$(date '+%F %T')] Git dan yangi kod olinmoqda..."
runuser -u savebot -- git -C "${APP_DIR}" pull --ff-only

echo "[$(date '+%F %T')] Kutubxonalar tekshirilmoqda..."
runuser -u savebot -- "${APP_DIR}/.venv/bin/pip" install --upgrade -r "${APP_DIR}/requirements.txt"

echo "[$(date '+%F %T')] Bot qayta ishga tushirilmoqda..."
systemctl restart bot.service
systemctl --no-pager status bot.service
