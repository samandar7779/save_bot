# Save-bot uchun Docker obraz.
# Ichida Python 3.12, ffmpeg va barcha kutubxonalar bor.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DOWNLOAD_DIR=/app/downloads

# ffmpeg — audio konvertatsiya va video/audio birlashtirish uchun.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg aria2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Avval faqat kutubxonalarni o'rnatamiz — Docker cache tezroq ishlaydi.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Root bo'lmagan foydalanuvchi.
RUN useradd --create-home --shell /usr/sbin/nologin botuser \
    && mkdir -p /app/downloads \
    && chown -R botuser:botuser /app

USER botuser

CMD ["python", "-u", "bot.py"]
