#!/usr/bin/env bash
# yt-dlp ni yangilaydi va botni qayta ishga tushiradi.
# Saytlar (YouTube/Instagram) o'zgarganda yuklash buzilmasligi uchun kunlik ishlatiladi.
#
# Qo'lda ishga tushirish:
#   sudo /opt/save-bot/deploy/update-ytdlp.sh
set -euo pipefail

APP_DIR="/opt/save-bot"
SERVICE_NAME="bot.service"
VENV_PIP="${APP_DIR}/.venv/bin/pip"

echo "[$(date '+%F %T')] yt-dlp yangilanmoqda..."

# savebot foydalanuvchisi nomidan o'rnatamiz (venv egasi shu foydalanuvchi bo'lishi kerak).
runuser -u savebot -- "${VENV_PIP}" install --upgrade --no-cache-dir yt-dlp

echo "[$(date '+%F %T')] Bot qayta ishga tushirilmoqda..."
systemctl restart "${SERVICE_NAME}"

echo "[$(date '+%F %T')] Tayyor. Versiya:"
runuser -u savebot -- "${APP_DIR}/.venv/bin/python" -c "import yt_dlp; print(yt_dlp.version.__version__)"
