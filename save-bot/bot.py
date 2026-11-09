"""
Telegram "save bot" — Instagram va YouTube havolalaridan video yoki audio yuklab beradi.

Texnologiyalar:
  * Python 3.10+
  * aiogram 3 (asinxron)
  * yt-dlp  (yuklash)
  * FFmpeg  (audio -> MP3, video + audio birlashtirish)

O'rnatish:
  pip install -U aiogram python-dotenv yt-dlp

Muhit o'zgaruvchilari (.env faylidan o'qiladi):
  BOT_TOKEN          — majburiy, @BotFather dan olingan token
  COOKIES_FILE       — ixtiyoriy, cookies.txt yo'li (Instagram/YouTube uchun)
  DOWNLOAD_DIR       — ixtiyoriy, vaqtinchalik fayllar papkasi (default: ./downloads)
  MAX_CONCURRENT     — bir vaqtda yuklashlar soni (default: 3)
  MAX_FILE_SIZE_MB   — Telegram limiti (default: 50)
  DOWNLOAD_TIMEOUT   — bitta yuklash uchun maksimal soniya (default: 900)
  FFMPEG_LOCATION    — ixtiyoriy, ffmpeg papkasi (PATH da bo'lsa shart emas)
  REQUIRED_CHANNEL   — ixtiyoriy, majburiy a'zolik kanali (@username yoki -100... id)
  CHANNEL_URL        — ixtiyoriy, kanalga qo'shilish havolasi (yopiq kanal uchun shart)
  ADMIN_USERNAME     — ixtiyoriy, «Admin» tugmasi uchun @username yoki havola
  SUB_CACHE_TTL      — a'zolik tekshiruvi keshi (soniya, default: 600)
  FRAGMENT_CONCURRENCY — parallel fragmentlar soni (default: 10)
  HTTP_CHUNK_SIZE_MB — HTTP bo'lak hajmi (default: 10, 0 = o'chirilgan)
  USE_ARIA2          — auto/true/false, tez yuklash uchun aria2c (default: auto)
  ARIA2_CONNECTIONS  — aria2 ulanishlar soni (default: 8)
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramConflictError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv
from yt_dlp.utils import DownloadError

# ---------------------------------------------------------------------------
# Konfiguratsiya
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Docker/systemd da o'zgaruvchilar tashqaridan beriladi — fayl shart emas.
# Fayl faqat BOT_TOKEN muhitda bo'lmasa o'qiladi (avval .env, keyin .env.example).
ENV_FILE: Path | None = None
if not os.getenv("BOT_TOKEN", "").strip():
    for _name in (".env", ".env.txt", ".env.example"):
        _candidate = BASE_DIR / _name
        if _candidate.is_file():
            ENV_FILE = _candidate
            load_dotenv(_candidate, encoding="utf-8-sig")
            break


def detect_ffmpeg() -> str | None:
    """FFmpeg papkasini avtomatik topadi (lokal tools -> PATH -> odatiy joylar)."""
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates = [
        BASE_DIR / "tools" / "ffmpeg" / "bin",  # Windows portativ o'rnatma
        Path(r"C:\ffmpeg\bin"),
        Path(r"C:\Program Files\ffmpeg\bin"),
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/snap/bin"),
    ]
    for folder in candidates:
        if (folder / exe).is_file():
            return str(folder)
    found = shutil.which("ffmpeg")
    return str(Path(found).resolve().parent) if found else None


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip() or None
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
MAX_CONCURRENT = max(1, int(os.getenv("MAX_CONCURRENT", "3")))
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "900"))
FFMPEG_LOCATION = os.getenv("FFMPEG_LOCATION", "").strip() or None
if not FFMPEG_LOCATION:
    FFMPEG_LOCATION = detect_ffmpeg()

# --- Majburiy kanalga a'zolik ------------------------------------------------
def normalize_channel(value: str | None) -> str | None:
    """
    Kanal manzilini Telegram API uchun to'g'ri ko'rinishga keltiradi.

    t.me/kanal, https://t.me/kanal, @kanal  ->  @kanal
    -1001234567890                          ->  -1001234567890
    """
    if not value:
        return None
    value = value.strip().strip('"').strip("'")
    low = value.lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "telegram.me/"):
        if low.startswith(prefix):
            value = value[len(prefix):].strip("/")
            break
    if not value:
        return None
    if value.lstrip("-").isdigit():
        return value
    if value.startswith("@"):
        return value
    return "@" + value


REQUIRED_CHANNEL = normalize_channel(os.getenv("REQUIRED_CHANNEL", ""))
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip() or None
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip() or None
SUB_CACHE_TTL = max(0, int(os.getenv("SUB_CACHE_TTL", "600")))

# --- Tez yuklash sozlamalari -------------------------------------------------
FRAGMENT_CONCURRENCY = max(1, int(os.getenv("FRAGMENT_CONCURRENCY", "10")))
HTTP_CHUNK_MB = max(0, int(os.getenv("HTTP_CHUNK_SIZE_MB", "10")))
USE_ARIA2_MODE = os.getenv("USE_ARIA2", "auto").strip().lower()
ARIA2_CONNECTIONS = max(1, int(os.getenv("ARIA2_CONNECTIONS", "8")))
ARIA2_FOUND = shutil.which("aria2c") is not None
USE_ARIA2 = USE_ARIA2_MODE in ("1", "true", "yes", "on") or (
        USE_ARIA2_MODE == "auto" and ARIA2_FOUND
)

# Telegram bot API orqali yuborish mumkin bo'lgan maksimal fayl hajmi.
TELEGRAM_HARD_LIMIT_MB = 50

# Havolani aniqlash uchun regex (Instagram, YouTube, YouTube Shorts, youtu.be).
URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?"
    r"(?:instagram\.com|youtube\.com|youtu\.be|music\.youtube\.com)"
    r"/[^\s<>\"']+",
    re.IGNORECASE,
)

# Havola qancha vaqt tugmalar bilan "yashaydi" (soniya).
PENDING_TTL = 30 * 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("save-bot")

router = Router(name="main")

# Bir vaqtda bajariladigan yuklashlar uchun semafor (global limit).
DOWNLOAD_SEM = asyncio.Semaphore(MAX_CONCURRENT)

# Har bir foydalanuvchi uchun bitta faol yuklash.
_user_locks: dict[int, asyncio.Lock] = {}

# Yuborilgan havolalar: token -> (url, yaratilgan vaqt).
_pending: dict[str, tuple[str, float]] = {}

# A'zolik keshi: user_id -> (natija, vaqt). Natija None bo'lsa — tekshirib bo'lmadi.
_sub_cache: dict[int, tuple[bool | None, float]] = {}

# --- Asosiy menyu (4 ta tugma, 2 qator) --------------------------------------
BTN_START = "🚀 Start"
BTN_ADMIN = "👤 Admin"
BTN_YOUTUBE = "▶️ YouTube"
BTN_INSTAGRAM = "📸 Instagram"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_START), KeyboardButton(text=BTN_ADMIN)],
        [KeyboardButton(text=BTN_YOUTUBE), KeyboardButton(text=BTN_INSTAGRAM)],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Havola yuboring yoki menyudan tanlang",
)


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------


def extract_url(text: str) -> str | None:
    """Matndan birinchi Instagram/YouTube havolasini ajratib oladi."""
    match = URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,;!?\"'»")


def detect_platform(url: str) -> str:
    """Havola qaysi platformaga tegishli ekanini qaytaradi."""
    if "instagram.com" in url.lower():
        return "Instagram"
    return "YouTube"


def put_pending(url: str) -> str:
    """Havolani vaqtinchalik xotiraga saqlaydi va qisqa token qaytaradi."""
    token = uuid.uuid4().hex[:12]
    _pending[token] = (url, time.time())
    return token


def take_pending(token: str) -> str | None:
    """Tokenni bir marta ishlatib, havolani qaytaradi (TTL tekshiriladi)."""
    item = _pending.pop(token, None)
    if not item:
        return None
    url, created = item
    if time.time() - created > PENDING_TTL:
        return None
    return url


def human_size(num_bytes: int) -> str:
    """Baytlarni o'qilishi qulay ko'rinishga keltiradi."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def short(text: str, limit: int) -> str:
    """Matnni belgilangan uzunlikka qisqartiradi."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def safe_edit(message: Message, text: str) -> None:
    """Xabarni xavfsiz tahrirlaydi (bir xil matn / flood / tarmoq xatolarida yiqilmaydi)."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        try:
            await message.edit_text(text, parse_mode=ParseMode.HTML)
        except Exception:  # noqa: BLE001
            pass
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("edit_text xatosi: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.debug("edit_text kutilmagan xatosi: %s", exc)


async def safe_remove_keyboard(message: Message) -> None:
    """Inline tugmalarni olib tashlaydi."""
    try:
        await message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


def get_user_lock(user_id: int) -> asyncio.Lock:
    """Foydalanuvchi uchun lock qaytaradi (bir vaqtda bitta yuklash)."""
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


# ---------------------------------------------------------------------------
# Majburiy kanalga a'zolikni tekshirish
# ---------------------------------------------------------------------------


JOIN_TEXT = (
    "🔒 <b>Botdan foydalanish uchun avval kanalimizga a'zo bo'ling.</b>\n\n"
    "📢 Kanal: <b>{channel}</b>\n\n"
    "A'zo bo'lgach, <b>«✅ A'zo bo'ldim»</b> tugmasini bosing."
)


def admin_url() -> str | None:
    """Admin bilan bog'lanish havolasini qaytaradi."""
    if not ADMIN_USERNAME:
        return None
    if ADMIN_USERNAME.startswith(("http://", "https://")):
        return ADMIN_USERNAME
    return f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"


async def get_channel_url(bot: Bot) -> str | None:
    """Kanalga qo'shilish havolasini aniqlaydi."""
    if not REQUIRED_CHANNEL:
        return None
    if CHANNEL_URL:
        return CHANNEL_URL
    if REQUIRED_CHANNEL.startswith("@"):
        return f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    # Yopiq kanal: bot admin bo'lsa, invite link olinadi.
    try:
        chat = await bot.get_chat(REQUIRED_CHANNEL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kanal havolasini olish imkonsiz: %s", exc)
        return None
    if getattr(chat, "invite_link", None):
        return chat.invite_link
    username = getattr(chat, "username", None)
    return f"https://t.me/{username}" if username else None


async def check_subscription(
        bot: Bot, user_id: int, *, use_cache: bool = True
) -> bool | None:
    """
    Foydalanuvchining kanalga a'zoligini tekshiradi.

    Qaytaradi:
      True  — a'zo
      False — a'zo emas
      None  — tekshirib bo'lmadi (bot kanalda admin emas va h.k.)
              Bu holatda bot ishlashda davom etadi (fail-open).
    """
    if not REQUIRED_CHANNEL:
        return True

    now = time.monotonic()
    if use_cache and SUB_CACHE_TTL:
        cached = _sub_cache.get(user_id)
        if cached is not None:
            result, checked_at = cached
            # Ijobiy natija uzoqroq, salbiy natija qisqaroq keshlanadi.
            ttl = SUB_CACHE_TTL if result else min(SUB_CACHE_TTL, 30)
            if now - checked_at < ttl:
                return result

    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
    except TelegramBadRequest as exc:
        logger.warning(
            "A'zolikni tekshirib bo'lmadi (%s). Botni kanalga ADMIN qilib qo'ying: %s",
            REQUIRED_CHANNEL,
            exc,
        )
        _sub_cache[user_id] = (None, now)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("A'zolik tekshiruvi xatosi: %s", exc)
        return None

    status = getattr(member.status, "value", member.status)
    is_member = status in ("creator", "administrator", "member")
    if status == "restricted":
        is_member = bool(getattr(member, "is_member", False))

    _sub_cache[user_id] = (is_member, now)
    return is_member


async def send_join_prompt(message: Message, bot: Bot) -> None:
    """Kanalga qo'shilish tugmalarini yuboradi."""
    url = await get_channel_url(bot)
    rows: list[list[InlineKeyboardButton]] = []
    if url:
        rows.append(
            [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=url)]
        )
    rows.append(
        [InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="sub:check")]
    )
    await message.answer(
        JOIN_TEXT.format(channel=html.escape(REQUIRED_CHANNEL or "")),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        disable_web_page_preview=True,
    )


async def ensure_subscribed(
    message: Message, bot: Bot, *, fresh: bool = False
) -> bool:
    """
    A'zo bo'lmasa join prompt yuboradi va False qaytaradi.

    fresh=True — keshni chetlab o'tib, Telegramdan qayta tekshiradi.
    Yangi foydalanuvchi /start bosganda shu rejim ishlatiladi.
    """
    if message.from_user is None:
        return True
    result = await check_subscription(
        bot, message.from_user.id, use_cache=not fresh
    )
    if result is False:
        await send_join_prompt(message, bot)
        return False
    return True


def humanize_error(exc: Exception) -> str:
    """yt-dlp xatolarini foydalanuvchiga tushunarli matnga aylantiradi."""
    raw = str(exc)
    low = raw.lower()

    if "ffmpeg" in low or "ffprobe" in low:
        return (
            "❌ <b>FFmpeg topilmadi.</b>\n"
            "Serverda <code>ffmpeg</code> o'rnatilmagan yoki PATH da yo'q.\n\n"
            "Windows: <code>deploy/setup-ffmpeg-windows.ps1</code> ni ishga tushiring.\n"
            "Linux: <code>sudo apt install -y ffmpeg</code>.\n"
            "Yoki <code>.env</code> da <code>FFMPEG_LOCATION</code> ni ko'rsating."
        )
    if any(
            k in low
            for k in (
                    "login", "sign in", "cookies", "rate-limit", "rate limit",
                    "empty media response", "checkpoint", "not a bot",
            )
    ):
        return (
            "🔒 <b>Sayt login/cookies talab qilmoqda.</b>\n"
            "Bu yopiq/cheklangan kontent yoki bot deb gumon qilingan so'rov bo'lishi mumkin. "
            "Serverda <code>cookies.txt</code> sozlash kerak."
        )
    if "private" in low or "members-only" in low:
        return "🔒 Bu post/video yopiq (private). Faqat ochiq (public) kontent yuklanadi."
    if "403" in low or "forbidden" in low:
        return (
            "🚫 <b>403 (Forbidden) xatosi.</b>\n"
            "Sayt so'rovni rad etdi. <code>yt-dlp</code> ni yangilang yoki cookiesdan foydalaning."
        )
    if "unsupported url" in low:
        return "❌ Havola qo'llab-quvvatlanmaydi. Instagram post/reel yoki YouTube havolasini yuboring."
    if any(k in low for k in ("video unavailable", "not available", "removed", "deleted", "does not exist")):
        return "❌ Video mavjud emas: o'chirilgan, bloklangan yoki noto'g'ri havola."
    if "timed out" in low or "timeout" in low:
        return "⏱ Yuklash vaqti tugadi. Keyinroq qayta urinib ko'ring."
    if "no space left" in low:
        return "💾 Serverda disk joyi qolmadi. Administrator downloads papkasini tozalashi kerak."

    logger.warning("yt-dlp xatosi: %s", raw)
    return (
        "❌ Yuklab bo'lmadi.\n"
        "Havola to'g'riligini tekshiring va birozdan keyin qayta urinib ko'ring."
    )


# ---------------------------------------------------------------------------
# yt-dlp sozlamalari va yuklash
# ---------------------------------------------------------------------------


@dataclass
class DownloadResult:
    path: Path
    title: str
    duration: int = 0
    width: int = 0
    height: int = 0


class FileTooLargeError(Exception):
    """Fayl Telegram limitidan katta bo'lganda ko'tariladi."""

    def __init__(self, size: int):
        self.size = size
        super().__init__(f"Fayl juda katta: {human_size(size)}")


def build_ydl_opts(mode: str, outtmpl: str, progress_hook=None) -> dict:
    """yt-dlp uchun sozlamalar to'plamini tayyorlaydi."""
    opts: dict = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        # Tez yuklash: bir nechta fragmentni parallel yuklaymiz.
        "concurrent_fragment_downloads": FRAGMENT_CONCURRENCY,
        "buffersize": 1024 * 1024,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "overwrites": True,
    }
    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    if FFMPEG_LOCATION:
        opts["ffmpeg_location"] = FFMPEG_LOCATION

    # Katta HTTP bo'laklari YouTube'ning sekinlashtirishini kamaytiradi.
    if HTTP_CHUNK_MB and not USE_ARIA2:
        opts["http_chunk_size"] = HTTP_CHUNK_MB * 1024 * 1024

    # aria2c mavjud bo'lsa — ko'p ulanishli tez yuklash.
    if USE_ARIA2:
        opts["external_downloader"] = {"default": "aria2c"}
        opts["external_downloader_args"] = {
            "aria2c": [
                "-x", str(ARIA2_CONNECTIONS),
                "-s", str(ARIA2_CONNECTIONS),
                "-k", "1M",
                "--summary-interval=0",
                "--console-log-level=warn",
            ]
        }

    if mode == "audio":
        # Eng yaxshi audio oqim + FFmpeg orqali 192 kbps MP3.
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # MP4, maksimal 720p.
        # 1) 720p mp4 video + m4a audio (eng sifatli)
        # 2) 720p tayyor (progressive) mp4 — bitta fayl, merge yo'q => tezroq
        # 3) boshqa 720p variantlar
        opts["format"] = (
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
            "b[height=720][ext=mp4]/"
            "bv*[height<=720]+ba/"
            "b[height<=720]/"
            "b"
        )
        opts["merge_output_format"] = "mp4/mkv"

    return opts


def make_progress_hook(loop: asyncio.AbstractEventLoop, on_progress):
    """
    yt-dlp progress hook yaratadi.
    Hook alohida threadda chaqiriladi, shuning uchun UI yangilanishi
    asosiy event loop ga xavfsiz tarzda uzatiladi.
    """
    state = {"last_time": 0.0, "last_pct": -10}

    def hook(data: dict) -> None:
        if data.get("status") != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        downloaded = data.get("downloaded_bytes") or 0
        percent = int(downloaded * 100 / total) if total else -1

        # Fragmentlar bo'yicha foiz (ba'zi saytlarda total_bytes bo'lmaydi).
        if percent < 0 and data.get("fragment_count"):
            percent = int((data.get("fragment_index") or 0) * 100 / data["fragment_count"])

        now = time.monotonic()
        # Telegramni flood qilmaslik uchun: 3 soniya yoki 5% dan kam bo'lsa o'tkazib yuboramiz.
        if now - state["last_time"] < 3 or percent - state["last_pct"] < 5:
            return
        state["last_time"] = now
        state["last_pct"] = percent

        try:
            asyncio.run_coroutine_threadsafe(on_progress(percent, downloaded, total), loop)
        except RuntimeError:
            # Event loop yopilgan — yuklash bekor qilinmoqda.
            pass

    return hook


def _download_blocking(url: str, mode: str, workdir: Path, hook) -> DownloadResult:
    """
    yt-dlp ni sinxron rejimda ishga tushiradi.
    Bu funksiya `asyncio.to_thread` orqali alohida threadda bajariladi.
    """
    outtmpl = str(workdir / "%(title).80s-%(id)s.%(ext)s")
    opts = build_ydl_opts(mode, outtmpl, hook)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise DownloadError("Bo'sh javob qaytdi")

    # Playlist bo'lsa ham faqat birinchi elementni olamiz.
    if info.get("_type") == "playlist":
        entries = [entry for entry in (info.get("entries") or []) if entry]
        if entries:
            info = entries[0]

    files = [
        p
        for p in workdir.iterdir()
        if p.is_file() and not p.name.endswith((".part", ".ytdl", ".temp"))
    ]
    if not files:
        raise DownloadError("Yuklangan fayl topilmadi")

    wanted_suffix = ".mp3" if mode == "audio" else ""
    preferred = [p for p in files if not wanted_suffix or p.suffix.lower() == wanted_suffix]
    path = max(preferred or files, key=lambda p: p.stat().st_size)

    return DownloadResult(
        path=path,
        title=info.get("title") or path.stem,
        duration=int(info.get("duration") or 0),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
    )


# ---------------------------------------------------------------------------
# Bot handlerlari
# ---------------------------------------------------------------------------

START_TEXT = (
    "👋 <b>Salom!</b>\n\n"
    "Men Instagram va YouTube havolalaridan <b>video</b> yoki <b>audio (MP3)</b> yuklab beraman.\n\n"
    "📌 <b>Qanday foydalanish:</b>\n"
    "1. Instagram post/reel yoki YouTube video havolasini yuboring.\n"
    "2. Chiqqan tugmalardan <b>Video</b> yoki <b>Audio (MP3)</b> ni tanlang.\n"
    "3. Bot yuklab, Telegramga yuboradi.\n\n"
    "⚠️ <b>Cheklovlar:</b>\n"
    "• Video — MP4, 720p gacha\n"
    "• Audio — MP3, 192 kbps\n"
    f"• Fayl hajmi — {TELEGRAM_HARD_LIMIT_MB} MB gacha (Telegram limiti)\n"
    f"• Bir vaqtda serverda {MAX_CONCURRENT} ta yuklash\n\n"
    "👇 Pastdagi menyudan ham foydalanishingiz mumkin.\n"
    "🔗 Havolani yuboring yoki menyudan tanlang:"
)

HELP_TEXT = (
    "ℹ️ <b>Yordam</b>\n\n"
    "• <code>/start</code> — botni ishga tushirish\n"
    "• <code>/help</code> — ushbu yordam\n\n"
    "<b>Menyu tugmalari:</b>\n"
    "🚀 <b>Start</b> — yo'riqnoma\n"
    "👤 <b>Admin</b> — admin bilan bog'lanish\n"
    "▶️ <b>YouTube</b> — YouTube haqida ma'lumot\n"
    "📸 <b>Instagram</b> — Instagram haqida ma'lumot\n\n"
    "Qo'llab-quvvatlanadigan havolalar:\n"
    "• <code>https://www.instagram.com/reel/...</code>\n"
    "• <code>https://www.youtube.com/watch?v=...</code>\n"
    "• <code>https://youtu.be/...</code>\n\n"
    "❗️ Faqat ochiq (public) kontent yuklanadi. "
    "Yopiq Instagram postlari uchun serverda cookies.txt kerak bo'ladi."
)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    # Yangi foydalanuvchi /start bosganda a'zolikni keshsiz, qaytadan tekshiramiz.
    if not await ensure_subscribed(message, bot, fresh=True):
        return
    await message.answer(START_TEXT, reply_markup=MAIN_MENU)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=MAIN_MENU)


@router.message(F.text == BTN_START)
async def menu_start(message: Message, bot: Bot) -> None:
    await cmd_start(message, bot)


@router.message(F.text == BTN_ADMIN)
async def menu_admin(message: Message) -> None:
    url = admin_url()
    if url:
        await message.answer(
            "👤 <b>Admin</b>\n\n"
            "Savol, taklif yoki muammo bo'lsa, admin bilan bog'laning.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✍️ Admin bilan bog'lanish", url=url)]
                ]
            ),
        )
    else:
        await message.answer(
            "👤 <b>Admin</b>\n\n"
            "Bog'lanish uchun <code>ADMIN_USERNAME</code> sozlanmagan.\n"
            "Server administratoriga murojaat qiling.",
            reply_markup=MAIN_MENU,
        )


@router.message(F.text == BTN_YOUTUBE)
async def menu_youtube(message: Message, bot: Bot) -> None:
    if not await ensure_subscribed(message, bot):
        return
    await message.answer(
        "▶️ <b>YouTube</b>\n\n"
        "Havolani yuboring:\n"
        "• <code>https://www.youtube.com/watch?v=...</code>\n"
        "• <code>https://youtu.be/...</code>\n"
        "• YouTube Shorts ham ishlaydi.\n\n"
        "🎬 Video — MP4, 720p gacha\n"
        "🎵 Audio — MP3, 192 kbps",
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )


@router.message(F.text == BTN_INSTAGRAM)
async def menu_instagram(message: Message, bot: Bot) -> None:
    if not await ensure_subscribed(message, bot):
        return
    await message.answer(
        "📸 <b>Instagram</b>\n\n"
        "Post, Reel yoki IGTV havolasini yuboring:\n"
        "• <code>https://www.instagram.com/reel/...</code>\n"
        "• <code>https://www.instagram.com/p/...</code>\n\n"
        "🔒 Yopiq akkauntlar uchun serverda <code>cookies.txt</code> kerak bo'ladi.",
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "sub:check")
async def on_sub_check(callback: CallbackQuery, bot: Bot) -> None:
    """«✅ A'zo bo'ldim» tugmasi bosilganda kanalni qayta tekshiradi."""
    result = await check_subscription(bot, callback.from_user.id, use_cache=False)
    if result is None:
        await callback.answer(
            "Tekshirib bo'lmadi. Bot kanalga admin qilinganini tekshiring.",
            show_alert=True,
        )
        return
    if not result:
        await callback.answer(
            "❌ Siz hali kanalga a'zo emassiz. A'zo bo'lib, qayta bosing.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Rahmat!")
    message = callback.message
    if isinstance(message, Message):
        await safe_edit(message, "✅ <b>A'zolik tasdiqlandi!</b>")
        # A'zo bo'lgandan keyin to'liq start menyusini ko'rsatamiz.
        await message.answer(START_TEXT, reply_markup=MAIN_MENU)


@router.message(F.chat.type == "private", F.text)
async def on_link(message: Message, bot: Bot) -> None:
    """Foydalanuvchi yuborgan matndan havolani topadi va tugmalarni chiqaradi."""
    if not await ensure_subscribed(message, bot):
        return

    url = extract_url(message.text or "")
    if not url:
        await message.answer(
            "🔗 Iltimos, Instagram yoki YouTube havolasini yuboring.\n"
            "Misol: <code>https://youtu.be/dQw4w9WgXcQ</code>",
        )
        return

    platform = detect_platform(url)
    token = put_pending(url)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Video", callback_data=f"dl:video:{token}"),
                InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data=f"dl:audio:{token}"),
            ]
        ]
    )

    await message.answer(
        f"🔎 <b>{platform}</b> havolasi aniqlandi.\n\n"
        "Nima qilib beray?\n"
        "🎬 <b>Video</b> — MP4, 720p gacha\n"
        "🎵 <b>Audio</b> — MP3, 192 kbps",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("dl:"))
async def on_choice(callback: CallbackQuery, bot: Bot) -> None:
    """Inline tugma bosilganda yuklashni boshlaydi."""
    try:
        _, mode, token = (callback.data or "").split(":", 2)
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    if mode not in ("video", "audio"):
        await callback.answer("Noto'g'ri tanlov.", show_alert=True)
        return

    # Yuklashdan oldin a'zolikni qayta tekshiramiz (kesh bilan).
    user_id = callback.from_user.id
    subscribed = await check_subscription(bot, user_id)
    if subscribed is False:
        await callback.answer("❌ Avval kanalga a'zo bo'ling.", show_alert=True)
        if isinstance(callback.message, Message):
            await send_join_prompt(callback.message, bot)
        return

    url = take_pending(token)
    if not url:
        await callback.answer(
            "⌛️ Havola eskirgan. Iltimos, havolani qaytadan yuboring.",
            show_alert=True,
        )
        return

    await callback.answer()

    message = callback.message
    if not isinstance(message, Message):
        message = await bot.send_message(user_id, "⏳ Boshlanmoqda...")

    await safe_remove_keyboard(message)

    user_lock = get_user_lock(user_id)

    if user_lock.locked():
        await safe_edit(
            message,
            "⚠️ Sizda allaqachon yuklash ketmoqda.\n"
            "Iltimos, u tugashini kuting va keyin qayta urinib ko'ring.",
        )
        return

    async with user_lock:
        label = "Video" if mode == "video" else "Audio (MP3)"
        if DOWNLOAD_SEM.locked():
            await safe_edit(message, f"⏳ Navbatda... (boshqa yuklashlar tugashini kutmoqda)\n🎯 {label}")
        else:
            await safe_edit(message, f"⬇️ Yuklanmoqda...\n🎯 {label}")

        workdir: Path | None = None
        try:
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            workdir = Path(tempfile.mkdtemp(prefix=f"{mode}-", dir=DOWNLOAD_DIR))

            loop = asyncio.get_running_loop()
            progress_done = False

            async def on_progress(percent: int, downloaded: int, total: int) -> None:
                # Yuklash tugagach kechikkan progress xabarlari holatni buzmasin.
                if progress_done:
                    return
                if percent >= 0:
                    progress = f"{min(percent, 100)}%"
                    details = (
                        f"{human_size(downloaded)} / {human_size(total)}"
                        if total
                        else human_size(downloaded)
                    )
                    text = f"⬇️ Yuklanmoqda... {progress} ({details})\n🎯 {label}"
                else:
                    text = f"⬇️ Yuklanmoqda... {human_size(downloaded)}\n🎯 {label}"
                await safe_edit(message, text)

            hook = make_progress_hook(loop, on_progress)

            async with DOWNLOAD_SEM:
                await safe_edit(message, f"⬇️ Yuklanmoqda...\n🎯 {label}")
                result = await asyncio.wait_for(
                    asyncio.to_thread(_download_blocking, url, mode, workdir, hook),
                    timeout=DOWNLOAD_TIMEOUT,
                )

            progress_done = True
            size = result.path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise FileTooLargeError(size)

            await safe_edit(message, f"⬆️ Yuborilmoqda... ({human_size(size)})\n🎯 {label}")

            safe_title = html.escape(short(result.title, 300))
            caption = f"🎬 <b>{safe_title}</b>\n\n📦 {human_size(size)} · {label}"

            if mode == "video":
                extra: dict = {"supports_streaming": True}
                if result.duration:
                    extra["duration"] = result.duration
                if result.width and result.height:
                    extra["width"] = result.width
                    extra["height"] = result.height
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=FSInputFile(str(result.path)),
                    caption=caption,
                    **extra,
                )
            else:
                extra = {}
                if result.duration:
                    extra["duration"] = result.duration
                await bot.send_audio(
                    chat_id=message.chat.id,
                    audio=FSInputFile(str(result.path)),
                    caption=caption,
                    title=short(result.title, 64),
                    **extra,
                )

            await safe_edit(message, f"✅ Yuborildi: <b>{safe_title}</b> ({human_size(size)})")
            logger.info(
                "OK | user=%s | mode=%s | %s | %s | %s",
                user_id, mode, result.path.name, human_size(size), url,
            )

        except FileTooLargeError as exc:
            await safe_edit(
                message,
                f"📦 <b>Fayl juda katta.</b>\n"
                f"Fayl hajmi: <b>{human_size(exc.size)}</b>\n"
                f"Telegram bot API orqali maksimal: <b>{MAX_FILE_MB} MB</b>.\n\n"
                f"💡 Audio (MP3) variantini tanlab ko'ring.",
            )
            logger.info("KATTA FAYL | user=%s | %s | %s", user_id, human_size(exc.size), url)

        except asyncio.TimeoutError:
            await safe_edit(
                message,
                "⏱ <b>Yuklash vaqti tugadi.</b>\n"
                "Internet sekin yoki fayl juda katta bo'lishi mumkin. Qayta urinib ko'ring.",
            )
            logger.warning("TIMEOUT | user=%s | %s", user_id, url)

        except DownloadError as exc:
            await safe_edit(message, humanize_error(exc))

        except TelegramBadRequest as exc:
            text = str(exc).lower()
            if "too large" in text:
                await safe_edit(
                    message,
                    f"📦 <b>Telegram faylni qabul qilmadi.</b>\n"
                    f"Bot API limiti — {MAX_FILE_MB} MB. Audio variantini sinab ko'ring.",
                )
            else:
                await safe_edit(
                    message,
                    f"❌ Telegram xatosi: <code>{html.escape(short(str(exc), 200))}</code>",
                )
            logger.warning("TELEGRAM XATOSI | user=%s | %s", user_id, exc)

        except Exception:  # noqa: BLE001
            logger.exception("Kutilmagan xato | user=%s | %s", user_id, url)
            await safe_edit(
                message,
                "❌ <b>Kutilmagan xato.</b>\n"
                "Havolani tekshirib, birozdan keyin qayta urinib ko'ring.",
            )

        finally:
            # Yuborilgandan keyin faylni serverdan o'chiramiz.
            if workdir is not None:
                shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------


async def pending_gc() -> None:
    """Eskirgan havola tokenlarini vaqti-vaqti bilan tozalaydi."""
    while True:
        await asyncio.sleep(300)
        now = time.time()
        for token, (_, created) in list(_pending.items()):
            if now - created > PENDING_TTL:
                _pending.pop(token, None)


async def main() -> None:
    if BOT_TOKEN:
        if ENV_FILE is not None:
            logger.info("Sozlamalar fayli: %s", ENV_FILE.name)
        else:
            logger.info("Sozlamalar: muhit o'zgaruvchilari (Docker/systemd)")
    else:
        raise SystemExit(
            f"XATO: BOT_TOKEN topilmadi. {BASE_DIR} papkasida .env yarating "
            "yoki BOT_TOKEN ni muhit o'zgaruvchisi sifatida bering."
        )

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if COOKIES_FILE and not Path(COOKIES_FILE).is_file():
        logger.warning("COOKIES_FILE ko'rsatilgan, lekin fayl topilmadi: %s", COOKIES_FILE)

    if FFMPEG_LOCATION:
        logger.info("FFmpeg: %s", FFMPEG_LOCATION)
    else:
        logger.warning(
            "FFmpeg topilmadi! Audio (MP3) va video birlashtirish ishlamaydi. "
            "Windows: deploy/setup-ffmpeg-windows.ps1 ni ishga tushiring yoki "
            ".env da FFMPEG_LOCATION ko'rsating. Linux: sudo apt install -y ffmpeg."
        )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    gc_task: asyncio.Task | None = None
    try:
        # Token to'g'riligini darhol tekshiramiz.
        me = await bot.get_me()
        logger.info("Bot: @%s (id=%s)", me.username, me.id)

        if REQUIRED_CHANNEL:
            logger.info("Majburiy kanal: %s", REQUIRED_CHANNEL)
            try:
                chat = await bot.get_chat(REQUIRED_CHANNEL)
                logger.info(
                    "Kanal topildi: %s (id=%s). Bot kanalda ADMIN bo'lishi kerak.",
                    chat.title,
                    chat.id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "REQUIRED_CHANNEL tekshirilmadi (%s): %s. "
                    "Kanal usernameini va botning adminligini tekshiring.",
                    REQUIRED_CHANNEL,
                    exc,
                )
        else:
            logger.info(
                "Majburiy kanal o'chirilgan (REQUIRED_CHANNEL bo'sh). "
                "/start da a'zolik tekshirilmaydi."
            )

        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Botni ishga tushirish"),
                BotCommand(command="help", description="Yordam"),
            ]
        )

        # Eski webhook va to'planib qolgan xabarlarni tozalaymiz.
        await bot.delete_webhook(drop_pending_updates=True)

        gc_task = asyncio.create_task(pending_gc())
        logger.info(
            "Bot ishga tushdi | concurrency=%s | max_file=%s MB | download_dir=%s",
            MAX_CONCURRENT, MAX_FILE_MB, DOWNLOAD_DIR,
        )
        logger.info(
            "Tez rejim | aria2=%s | fragment_concurrency=%s | http_chunk=%s MB",
            USE_ARIA2, FRAGMENT_CONCURRENCY, HTTP_CHUNK_MB,
        )

        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except TelegramUnauthorizedError:
        raise SystemExit("XATO: BOT_TOKEN noto'g'ri. @BotFather dan yangi token oling.")
    except TelegramConflictError:
        raise SystemExit(
            "XATO: Shu token bilan boshqa bot nusxasi ishlayapti. "
            "Eski jarayonni to'xtating va qayta ishga tushiring."
        )
    finally:
        if gc_task is not None:
            gc_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
    except SystemExit as exc:
        # Xato sababini yutib yubormasdan ko'rsatamiz.
        if exc.code not in (None, 0):
            logger.error("%s", exc.code)
            sys.exit(1)
        raise
