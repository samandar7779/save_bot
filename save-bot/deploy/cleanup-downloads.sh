#!/usr/bin/env bash
# downloads papkasidagi eskirgan vaqtinchalik fayllarni o'chiradi.
# Bot o'zi ham fayllarni o'chiradi, bu — qo'shimcha xavfsizlik to'ri
# (masalan, bot kutilmaganda o'chib qolgan bo'lsa).
set -euo pipefail

DOWNLOADS_DIR="/opt/save-bot/downloads"

if [ -d "${DOWNLOADS_DIR}" ]; then
    find "${DOWNLOADS_DIR}" -mindepth 1 -mmin +120 -exec rm -rf {} + 2>/dev/null || true
    echo "[$(date '+%F %T')] ${DOWNLOADS_DIR} tozalandi."
else
    echo "[$(date '+%F %T')] ${DOWNLOADS_DIR} topilmadi."
fi
