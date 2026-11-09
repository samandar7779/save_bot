# 📥 Telegram Save Bot — Instagram va YouTube

Instagram va YouTube havolalaridan **video (MP4, 720p gacha)** yoki **audio (MP3, 192 kbps)** yuklab, Telegram orqali yuboruvchi bot.

- **Til:** Python 3.10+
- **Kutubxona:** aiogram 3 (asinxron)
- **Yuklash:** yt-dlp
- **Audio/merge:** FFmpeg
- **Deploy:** systemd **yoki** Docker

---

## 📁 Loyiha tuzilishi

```
save-bot/
├── bot.py                     # Asosiy bot kodi
├── requirements.txt           # Python kutubxonalari
├── .env.example               # Muhit o'zgaruvchilari namunasi
├── .gitignore                 # .env va cookies gitga tushmasligi uchun
├── .dockerignore              # Docker image ichiga keraksiz fayllar tushmasligi uchun
├── Dockerfile                 # Docker obraz (ffmpeg + aria2 bilan)
├── docker-compose.yml         # Docker Compose konfiguratsiyasi
├── README.md                  # Ushbu qo'llanma
└── deploy/
    ├── bot.service            # systemd unit (Variant A)
    ├── update-ytdlp.sh        # yt-dlp ni yangilash skripti
    ├── update-ytdlp.service   # systemd timer uchun service
    ├── update-ytdlp.timer     # kunlik avtomatik yangilash
    ├── update-bot.sh          # kodni yangilash skripti
    └── cleanup-downloads.sh   # eskirgan fayllarni tozalash
```

### Bot imkoniyatlari

| Talab | Holat |
|---|---|
| `/start` — salomlashuv va yo'riqnoma | ✅ |
| Instagram / YouTube havolasini aniqlash | ✅ |
| Inline tugmalar: **Video** va **Audio (MP3)** | ✅ |
| Video — MP4, 720p gacha | ✅ |
| Audio — MP3, 192 kbps | ✅ |
| 50 MB limitdan oshsa tushunarli xabar | ✅ |
| Yuborilgandan keyin faylni o'chirish | ✅ |
| Holat xabarlari («Yuklanmoqda...», «Yuborilmoqda...») | ✅ |
| Xatolarni ushlash (yopiq akkaunt, noto'g'ri havola, katta fayl) | ✅ |
| Parallel yuklash cheklovi (3 ta) + asinxronlik | ✅ |
| Instagram uchun ixtiyoriy `cookies.txt` | ✅ |
| `BOT_TOKEN` / `COOKIES_FILE` faqat muhitdan | ✅ |
| 4 ta menyu tugmasi (2 qator): Start, Admin, YouTube, Instagram | ✅ |
| Majburiy kanalga a'zolikni tekshirish | ✅ |
| Tez yuklash (aria2, parallel fragmentlar) | ✅ |

---

## 🎛 Asosiy menyu va majburiy kanal

### Menyu tugmalari (4 ta, 2 qator)

Botda doimiy klaviatura bor:

```
┌──────────────┬──────────────┐
│  🚀 Start    │  👤 Admin    │
├──────────────┼──────────────┤
│  ▶️ YouTube  │  📸 Instagram│
└──────────────┴──────────────┘
```

- **Start** — yo'riqnoma va menyu
- **Admin** — `ADMIN_USERNAME` ga havola
- **YouTube / Instagram** — shu platforma bo'yicha qisqa yo'riqnoma

### Majburiy kanalga a'zolik

Botdan foydalanishdan oldin foydalanuvchi kanalga a'zo bo'lishi shart.

1. Botni kanalga **administrator** qiling (a'zolarni tekshirish uchun shart).
2. `.env` fayliga yozing:

```env
REQUIRED_CHANNEL=@kanalingiz
CHANNEL_URL=https://t.me/kanalingiz
ADMIN_USERNAME=@adminingiz
```

Yopiq kanal uchun:

```env
REQUIRED_CHANNEL=-1001234567890
CHANNEL_URL=https://t.me/+AbCdEfGhIjK
```

3. Botni qayta ishga tushiring.

A'zo bo'lmagan foydalanuvchi havola yuborsa, bot **«📢 Kanalga qo'shilish»** va **«✅ A'zo bo'ldim»** tugmalarini ko'rsatadi. Har bir `/start` bosilganda a'zolik **keshsiz, yangidan** tekshiriladi; qolgan xabarlarda esa tekshiruv keshlanadi (`SUB_CACHE_TTL`, default 600 s) — Telegram API har safar chaqirilmaydi va bot tez ishlaydi.

> `REQUIRED_CHANNEL` bo'sh bo'lsa, tekshiruv butunlay o'chiriladi.

### Tez yuklash

| Sozlama | Default | Vazifasi |
|---|---|---|
| `FRAGMENT_CONCURRENCY` | `10` | Parallel fragmentlar soni |
| `HTTP_CHUNK_SIZE_MB` | `10` | Katta HTTP bo'laklari (throttling kamayadi) |
| `USE_ARIA2` | `auto` | `aria2c` mavjud bo'lsa — ko'p ulanishli yuklash |
| `ARIA2_CONNECTIONS` | `8` | aria2 ulanishlar soni |

Serverga aria2 o'rnatsangiz, tezlik sezilarli oshadi:

```bash
sudo apt install -y aria2
sudo systemctl restart bot.service
```

Docker obrazida `aria2` allaqachon bor. Muammo bo'lsa: `.env` da `USE_ARIA2=false`.

Video uchun 720p tayyor (progressive) MP4 bo'lsa, bot uni bitta fayl sifatida oladi — merge qilinmaydi va tezroq bo'ladi. Aks holda 720p video + audio avtomatik birlashtiriladi.

---

## 1️⃣ Bot yaratish (@BotFather)

1. Telegramda [@BotFather](https://t.me/BotFather) ga o'ting.
2. `/newbot` → bot nomi → username (`..._bot` bilan tugashi shart).
3. Olingan tokenni saqlang:
   ```
   123456789:AAExampleTokenReplaceMe
   ```
4. Token **hech qachon** kodga yoki gitga yozilmaydi — faqat `.env` fayliga.

Foydali buyruqlar: `/setdescription`, `/setuserpic`, `/revoke` (token o'g'irlansa).

---

## 2️⃣ Lokal sinov (kompyuterda)

### Windows (PowerShell)

```powershell
cd C:\save-bot

# Virtual muhit
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# Kutubxonalar
python -m pip install -U pip
pip install -r requirements.txt

# FFmpeg (bir marta)
winget install --id Gyan.FFmpeg -e
# Tekshirish (yangi terminalda):
ffmpeg -version

# Sozlamalar
copy .env.example .env
notepad .env        # BOT_TOKEN ni yozing

# Ishga tushirish
python bot.py
```

### Linux / macOS

```bash
cd save-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

sudo apt install -y ffmpeg      # Debian/Ubuntu
# brew install ffmpeg           # macOS

cp .env.example .env
nano .env
python bot.py
```

Tokenda xato bo'lsa terminalda tushunarli xabar chiqadi. Bot ishlayapti degani — terminalda `Bot ishga tushdi ...` yozuvi paydo bo'ladi.

---

## 3️⃣ Server tanlash

**Minimal talab:** Ubuntu 22.04 / 24.04 LTS, **1 vCPU, 1–2 GB RAM, 20 GB SSD**.
Bu bot uchun ~$4–6/oy yetarli.

Mos provayderlar:

| Provayder | Izoh |
|---|---|
| **Hetzner** (CX22) | Eng yaxshi narx/sifat, Yevropa |
| **DigitalOcean** | Oson interfeys, hujjatlar ko'p |
| **Vultr** | Ko'p regionlar |
| **Contabo** | Arzon, lekin disk I/O sekinroq |
| **Aeza / Timeweb Cloud / Beget** | CIS/hudud uchun qulay |

> ⚠️ Instagram/YouTube ba'zi datacenter IP larini bloklashi mumkin. Muammo bo'lsa, provayder yoki regionni almashtirib ko'ring.

Ubuntu 22.04 yoki 24.04 ni tanlang. Debian 12 ham mos.

---

## 4️⃣ Serverni tayyorlash

### 4.1. SSH orqali ulanish

```bash
ssh root@SERVER_IP
```

### 4.2. Tizimni yangilash va kerakli paketlar

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip ffmpeg git ufw ca-certificates
```

Tekshirish:

```bash
python3 --version     # 3.10+
ffmpeg -version
```

### 4.3. Alohida (root bo'lmagan) foydalanuvchi

```bash
adduser --disabled-password --gecos "" savebot
usermod -aG sudo savebot
```

Keyingi ishlarni `savebot` nomidan bajaring:

```bash
su - savebot
```

### 4.4. Firewall (SSH ni yopib qo'ymaslik uchun tartib muhim!)

```bash
ufw allow OpenSSH
ufw enable
ufw status
```

---

## 5️⃣ Loyihani serverga ko'chirish

### Variant 1 — Git orqali (tavsiya etiladi)

Avval kodni GitHub/GitLab ga yuklang (`.env` va `cookies.txt` gitga tushmasligi kerak — `.gitignore` buni ta'minlaydi).

```bash
sudo mkdir -p /opt/save-bot
sudo chown savebot:savebot /opt/save-bot

# savebot foydalanuvchisi sifatida:
git clone https://github.com/USERNAME/save-bot.git /tmp/save-bot-src
cp -r /tmp/save-bot-src/. /opt/save-bot/
rm -rf /tmp/save-bot-src
cd /opt/save-bot
```

`/opt/save-bot` bo'sh bo'lsa, to'g'ridan-to'g'ri `git clone URL /opt/save-bot` ham mumkin.

### Variant 2 — `scp` orqali (Windows kompyuterdan)

```powershell
scp -r C:\save-bot\* savebot@SERVER_IP:/opt/save-bot/
```

### Virtual muhit va kutubxonalar

```bash
cd /opt/save-bot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### Sozlamalar

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

`.env` ichida kamida:

```env
BOT_TOKEN=123456789:AAExampleTokenReplaceMe
```

### Qo'lda sinov

```bash
cd /opt/save-bot
.venv/bin/python bot.py
```

Telegramda botga havola yuborib tekshiring. `Ctrl+C` bilan to'xtating — endi systemd sozlaymiz.

---

## 6️⃣ `.env` fayli

`.env.example` dan nusxa oling va to'ldiring:

```env
# Majburiy
BOT_TOKEN=123456789:AAExampleTokenReplaceMe

# Ixtiyoriy
COOKIES_FILE=/opt/save-bot/cookies.txt
DOWNLOAD_DIR=./downloads
MAX_CONCURRENT=3
MAX_FILE_SIZE_MB=50
DOWNLOAD_TIMEOUT=900
# FFMPEG_LOCATION=/usr/bin

# Majburiy kanal (bo'sh = tekshiruv o'chirilgan)
REQUIRED_CHANNEL=@kanalingiz
CHANNEL_URL=https://t.me/kanalingiz
ADMIN_USERNAME=@adminingiz
SUB_CACHE_TTL=600

# Tez yuklash
FRAGMENT_CONCURRENCY=10
HTTP_CHUNK_SIZE_MB=10
USE_ARIA2=auto
ARIA2_CONNECTIONS=8
```

Xavfsizlik:

```bash
chmod 600 /opt/save-bot/.env
chmod 600 /opt/save-bot/cookies.txt   # agar ishlatilsa
```

`.gitignore` da `.env` va `cookies.txt` borligiga ishonch hosil qiling:

```gitignore
.env
cookies.txt
downloads/
```

---

## 7️⃣ Variant A — systemd (tavsiya etiladi)

`deploy/bot.service` faylini o'rnating:

```bash
sudo cp /opt/save-bot/deploy/bot.service /etc/systemd/system/bot.service
sudo nano /etc/systemd/system/bot.service
```

Fayl mazmuni (yo'llar `savebot` foydalanuvchisiga mos):

```ini
[Unit]
Description=Telegram Save Bot (Instagram / YouTube)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=savebot
Group=savebot
WorkingDirectory=/opt/save-bot
EnvironmentFile=/opt/save-bot/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/save-bot/.venv/bin/python -u /opt/save-bot/bot.py
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/save-bot/downloads

[Install]
WantedBy=multi-user.target
```

Yoqish va ishga tushirish:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bot.service

# Holat
sudo systemctl status bot.service --no-pager

# Real vaqtda loglar
sudo journalctl -u bot.service -f

# Oxirgi 100 qator
sudo journalctl -u bot.service -n 100 --no-pager
```

Boshqarish:

```bash
sudo systemctl restart bot.service   # qayta ishga tushirish
sudo systemctl stop bot.service      # to'xtatish
sudo systemctl disable bot.service   # avtostartdan olib tashlash
```

`Restart=always` tufayli bot qulasa 5 soniyada o'zi qayta ko'tariladi. `EnvironmentFile` orqali `.env` avtomatik o'qiladi.

---

## 8️⃣ Variant B — Docker

### Docker o'rnatish (agar yo'q bo'lsa)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

### Ishga tushirish

```bash
cd /opt/save-bot
cp .env.example .env
nano .env                 # BOT_TOKEN
mkdir -p downloads

docker compose up -d --build
```

### Loglar va boshqarish

```bash
docker compose logs -f
docker compose ps
docker compose restart
docker compose down
```

`docker-compose.yml` ichida:

- `restart: unless-stopped` — server qayta yuklansa ham bot ko'tariladi;
- `env_file: .env` — tokenlar fayldan o'qiladi (obraz ichiga `.env` **kirmaydi**);
- `./downloads:/app/downloads` — vaqtinchalik fayllar uchun volume;
- log rotatsiyasi (`max-size: 10m`) — disk to'lib ketmasligi uchun.

> **Windows (Docker Desktop):** buyruqlar PowerShell da ham xuddi shunday ishlaydi.
> Avval lokal `python bot.py` nusxasini to'xtating — aks holda `TelegramConflictError` chiqadi.
>
> ```powershell
> cd C:\save-bot
> docker compose up -d --build
> docker compose logs -f
> ```

### ⚠️ `TelegramConflictError` (Docker)

Agar logda `Conflict: terminated by other getUpdates request` chiqsa, **bir vaqtda bir nechta bot nusxasi** ishlayapti:

```bash
docker ps -a                 # ortiqcha konteynerlarni toping
docker rm -f <orteqcha_nomi> # faqat bittasi qolsin
```

Windowsda lokal `python` nusxalarini ham tekshiring:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*bot.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### Kodni yangilash (Docker)

```bash
cd /opt/save-bot
git pull
docker compose up -d --build
```

### Instagram cookies (Docker)

1. `cookies.txt` ni loyiha papkasiga qo'ying.
2. `.env` da: `COOKIES_FILE=/app/cookies.txt`
3. `docker-compose.yml` dagi volume qatorini oching:
   ```yaml
   - ./cookies.txt:/app/cookies.txt:ro
   ```
4. `docker compose up -d`

---

## 9️⃣ Yangilash tartibi

### 9.1. Kodni yangilash

```bash
sudo /opt/save-bot/deploy/update-bot.sh
```

yoki qo'lda:

```bash
cd /opt/save-bot
sudo -u savebot git pull --ff-only
sudo -u savebot .venv/bin/pip install --upgrade -r requirements.txt
sudo systemctl restart bot.service
```

### 9.2. yt-dlp ni muntazam yangilash (muhim!)

YouTube/Instagram tez-tez o'zgaradi. Eski `yt-dlp` bilan **403**, **login required**, **Unable to extract** kabi xatolar boshlanadi. Shuning uchun kunlik avtomatik yangilashni yoqing:

```bash
sudo chmod +x /opt/save-bot/deploy/update-ytdlp.sh
sudo cp /opt/save-bot/deploy/update-ytdlp.service /etc/systemd/system/
sudo cp /opt/save-bot/deploy/update-ytdlp.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now update-ytdlp.timer

# Tekshirish
systemctl list-timers | grep update-ytdlp
sudo systemctl start update-ytdlp.service     # hoziroq sinab ko'rish
sudo journalctl -u update-ytdlp.service -n 50 --no-pager
```

Timer har kuni **04:00** da `yt-dlp` ni yangilab, botni qayta ishga tushiradi.

**Cron varianti** (timer o'rniga):

```bash
sudo crontab -e
# quyidagi qatorni qo'shing:
0 4 * * * /opt/save-bot/deploy/update-ytdlp.sh >> /var/log/save-bot-update.log 2>&1
```

Qo'lda yangilash:

```bash
sudo /opt/save-bot/deploy/update-ytdlp.sh
```

Docker uchun:

```bash
docker compose build --no-cache && docker compose up -d
```

---

## 🔟 Xavfsizlik

### 10.1. Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status verbose
```

Faqat kerakli port ochiladi. Bot tashqi port ochmaydi (Telegramga o'zi ulanadi), shuning uchun 80/443 shart emas.

### 10.2. SSH xavfsizligi

1. SSH kalit yarating (lokal kompyuterda):
   ```powershell
   ssh-keygen -t ed25519 -C "savebot-server"
   type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh savebot@SERVER_IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
   ```
2. Kalit bilan kirish ishlayotganiga ishonch hosil qiling.
3. Keyin `/etc/ssh/sshd_config` da:
   ```conf
   PermitRootLogin no
   PasswordAuthentication no
   PubkeyAuthentication yes
   ```
4. Tekshirish va qayta yuklash:
   ```bash
   sudo sshd -t
   sudo systemctl restart ssh
   ```
5. Root o'rniga `savebot` + `sudo` dan foydalaning.
6. Ixtiyoriy: `sudo apt install -y fail2ban`.

> ⚠️ `PasswordAuthentication no` qilishdan oldin kalit bilan kirish ishlayotganini albatta tekshiring, aks holda serverdan chiqib ketishingiz mumkin.

### 10.3. Token va cookies

- `BOT_TOKEN` faqat `.env` da, `chmod 600`.
- Token gitga tushmasin: `.gitignore` ni tekshiring.
- Token oshkor bo'lsa: @BotFather → `/revoke` → yangi token.
- `cookies.txt` — bu Instagram akkauntingiz sessiyasi. Uni **hech kimga** bermang, gitga qo'shmang.
- Cookies uchun alohida (asosiy bo'lmagan) Instagram akkaunt ishlatish tavsiya etiladi.
- Serverda faqat kerakli foydalanuvchi (`savebot`) ishlaydi; bot root emas.
- Docker ishlatilsa, `docker` guruhi amalda root huquqiga teng — faqat ishonchli foydalanuvchilarga bering.

### 10.4. Telegram limiti haqida

Bot API orqali yuboriladigan fayl **50 MB** bilan cheklangan. Kattaroq fayllar uchun **local Bot API server** kerak bo'ladi (murakkab variant). Standart holatda bot katta faylni yuklab, keyin tushunarli xabar beradi.

---

## 1️⃣1️⃣ Monitoring va disk

### Loglar

```bash
# systemd
sudo journalctl -u bot.service -f
sudo journalctl -u bot.service -n 200 --no-pager

# Docker
docker compose logs -f --tail=200
```

### Xizmat holati

```bash
systemctl is-active bot.service
systemctl status bot.service --no-pager
```

### Disk

```bash
df -h
du -sh /opt/save-bot/downloads
```

Bot har bir yuklashdan keyin o'z faylini o'chiradi. Qo'shimcha himoya uchun eskirgan fayllarni tozalash:

```bash
sudo chmod +x /opt/save-bot/deploy/cleanup-downloads.sh
sudo crontab -e
```

Qo'shimcha qator:

```cron
0 * * * * /opt/save-bot/deploy/cleanup-downloads.sh >> /var/log/save-bot-cleanup.log 2>&1
```

Bu soatiga bir marta 2 soatdan eski fayllarni o'chiradi.

### Monitoring maslahatlari

- Kuniga bir marta `systemctl is-active bot.service` ni tekshiruvchi cron + Telegram alert yozish mumkin.
- Tashqi monitoring: **UptimeRobot**, **BetterStack** (bot HTTP ochmasa ham, server pingini kuzatish).
- `Restart=always` tufayli oddiy qulashlar avtomatik tuzaladi.

---

## 1️⃣2️⃣ Muammolarni hal qilish

### ❌ `FFmpeg topilmadi` / `ffmpeg not found`

Bot FFmpeg ni avtomatik topadi: `tools/ffmpeg/bin`, `PATH`, `/usr/bin`, `/usr/local/bin`, `/snap/bin`, `C:\ffmpeg\bin`.

**Windows (eng oson):**

```powershell
powershell -ExecutionPolicy Bypass -File C:\save-bot\deploy\setup-ffmpeg-windows.ps1
```

Skript FFmpeg ni `C:\save-bot\tools\ffmpeg` ga o'rnatadi. So'ng botni qayta ishga tushiring. Tekshirish:

```powershell
C:\save-bot\tools\ffmpeg\bin\ffmpeg.exe -version
```

Agar FFmpeg boshqa joyda bo'lsa, `.env` ga yozing (to'g'ri `/` belgilar bilan):

```env
FFMPEG_LOCATION=C:/ffmpeg/bin
```

**Linux (server):**

```bash
sudo apt update && sudo apt install -y ffmpeg
ffmpeg -version
sudo systemctl restart bot.service
```

```env
FFMPEG_LOCATION=/usr/bin
```

Dockerda ffmpeg obraz ichida bor. Eski jarayonlar hali eski kod bilan ishlayotgan bo'lsa, ularni to'xtatib, botni qayta ishga tushiring.

### 🔒 Instagram login/cookies so'rayapti

Sabablari: yopiq akkaunt, login talab qiladigan post, datacenter IP bloklanishi.

Yechim:

1. Brauzerda Instagramga kiring.
2. «Get cookies.txt LOCALLY» kengaytmasi bilan **instagram.com** uchun `cookies.txt` eksport qiling.
3. Faylni serverga yuklang:
   ```powershell
   scp C:\cookies.txt savebot@SERVER_IP:/opt/save-bot/cookies.txt
   ```
4. Ruxsatlar:
   ```bash
   chmod 600 /opt/save-bot/cookies.txt
   chown savebot:savebot /opt/save-bot/cookies.txt
   ```
5. `.env`:
   ```env
   COOKIES_FILE=/opt/save-bot/cookies.txt
   ```
6. Qayta ishga tushiring:
   ```bash
   sudo systemctl restart bot.service
   ```

> Cookies vaqti-vaqti bilan eskiradi — qayta eksport qilish kerak bo'ladi. Akkaunt xavfsizligi uchun alohida akkaunt ishlating.

### 🚫 `403 Forbidden` / `Unable to extract`

1. `yt-dlp` ni yangilang:
   ```bash
   sudo /opt/save-bot/deploy/update-ytdlp.sh
   ```
2. Cookies qo'shing (yuqoridagi bo'lim).
3. IP bloklangan bo'lishi mumkin — VPN yoki boshqa server/region sinab ko'ring.
4. Loglarda aniq sababni ko'ring:
   ```bash
   sudo journalctl -u bot.service -n 100 --no-pager
   ```

### 📦 `File is too big` / fayl 50 MB dan katta

- Audio (MP3) variantini tanlang.
- Video odatda 720p da ham 50 MB dan oshishi mumkin (uzun videolar).
- Kattaroq limit kerak bo'lsa — **local Bot API server** o'rnatish kerak (ilg'or daraja).

### 🔁 `Conflict: terminated by other getUpdates request`

Bir vaqtda **ikkita bot nusxasi** ishlayapti (masalan, qo'lda `python bot.py` + systemd).

```bash
sudo systemctl stop bot.service
ps aux | grep bot.py
# ortiqcha jarayonni o'chiring
sudo systemctl start bot.service
```

### 🤖 Bot umuman javob bermayapti

1. `systemctl status bot.service --no-pager`
2. `journalctl -u bot.service -n 100 --no-pager`
3. `.env` da token to'g'riligini tekshiring.
4. Serverda internet borligini: `curl -I https://api.telegram.org`
5. Token revoke qilingan bo'lsa — yangisini oling.

### 🔒 «Kanalga a'zo bo'ling» deb turibdi, lekin a'zo bo'ldim

1. Bot kanalda **administrator** ekanini tekshiring — `getChatMember` uchun shu shart.
2. `REQUIRED_CHANNEL` to'g'ri yozilganini tekshiring: `@kanal_username` yoki `-100...` id (bot username emas!).
3. Yopiq kanal bo'lsa, `CHANNEL_URL` ga invite havola qo'ying.
4. Kesh 30 soniya (salbiy natija) yoki 10 daqiqa (ijobiy) saqlanadi. Kutishni xohlamasangiz:
   ```env
   SUB_CACHE_TTL=0
   ```
   So'ng `sudo systemctl restart bot.service`.
5. Startup loglarini ko'ring:
   ```bash
   sudo journalctl -u bot.service -n 100 --no-pager | grep -i kanal
   ```
6. Agar bot kanalni tekshira olmasa, u logga ogohlantirish yozadi va **fail-open** rejimida ishlaydi (hammani qabul qiladi). Shuning uchun loglarni tekshirish muhim.

### ⚡️ Yuklash sekin

1. `aria2` o'rnating:
   ```bash
   sudo apt install -y aria2
   sudo systemctl restart bot.service
   ```
2. `.env`:
   ```env
   USE_ARIA2=true
   ARIA2_CONNECTIONS=16
   FRAGMENT_CONCURRENCY=16
   HTTP_CHUNK_SIZE_MB=16
   ```
3. Server tarmog'i sekin bo'lsa, boshqa provayder/regionni sinab ko'ring.
4. Instagram ba'zi datacenter IP larini sekinlashtiradi — cookies yordam berishi mumkin.

### 🧨 aria2 bilan xato (`aria2c failed`)

Ba'zi saytlar aria2 bilan ishlamasligi mumkin. Uni o'chiring:

```env
USE_ARIA2=false
```

So'ng botni qayta ishga tushiring. Bot yana yt-dlp ning ichki downloaderidan foydalanadi.

### 💾 Disk to'lib qoldi

```bash
df -h
du -sh /opt/save-bot/downloads
sudo rm -rf /opt/save-bot/downloads/*
sudo systemctl restart bot.service
```

Keyin `cleanup-downloads.sh` ni cron ga qo'shing (11-bo'lim).

### 🐍 `externally-managed-environment` xatosi

Tizim Pythonga paket o'rnatish taqiqlangan. Har doim venv ishlatilsin:

```bash
cd /opt/save-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 🔐 SSL / certificate xatolari

```bash
sudo apt install -y ca-certificates
sudo update-ca-certificates
```

### ⚙️ `Too many open files` / sekin ishlash

`MAX_CONCURRENT` ni kamaytiring (masalan, `2` yoki `1`):

```env
MAX_CONCURRENT=2
DOWNLOAD_TIMEOUT=1200
```

So'ng `sudo systemctl restart bot.service`.

---

## ✅ Tezkor buyruqlar (cheat sheet)

```bash
# Holat va loglar
sudo systemctl status bot.service --no-pager
sudo journalctl -u bot.service -f

# Qayta ishga tushirish
sudo systemctl restart bot.service

# yt-dlp yangilash
sudo /opt/save-bot/deploy/update-ytdlp.sh

# Kodni yangilash
sudo /opt/save-bot/deploy/update-bot.sh

# Docker
cd /opt/save-bot && docker compose logs -f
cd /opt/save-bot && docker compose up -d --build
```

---

## 📌 Eslatmalar

- Bot faqat **ochiq (public)** kontentni yuklaydi. Yopiq akkauntlar uchun cookies ham har doim yordam bermasligi mumkin.
- Kontent mualliflik huquqini hurmat qiling — faqat shaxsiy foydalanish uchun yuklab oling.
- `yt-dlp` yangilanmasa, vaqt o'tishi bilan yuklash buzilishi mumkin. Avtomatik yangilanishni o'chirmang.
- Bir vaqtda 3 ta yuklash cheklovi server resurslarini (RAM/CPU) himoya qiladi.
- Majburiy kanal tekshiruvi bot kanalda admin bo'lishini talab qiladi — botni kanaldan chiqarib yubormang.
- `.env.example` faylida **hech qachon** haqiqiy token qoldirmang. Token faqat `.env` da bo'lsin.
