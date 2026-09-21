# 📥 ربات دانلودر سوشال (تلگرام + وب)

پشتیبانی از: 📸 اینستاگرام • ▶️ یوتیوب • 🎵 تیک‌تاک (بدون واترمارک) • ✖️ ایکس • 📌 پینترست

## 🚀 نصب سریع

```bash
pip install -r requirements.txt
cp .env.example .env
# توی .env مقدار BOT_TOKEN رو از @BotFather بذار
```

ffmpeg لازمه (برای تبدیل کیفیت):
- ویندوز: `winget install ffmpeg`
- اوبونتو: `sudo apt install ffmpeg`

## 🤖 اجرای ربات تلگرام

```bash
python bot.py
```

## 🌐 اجرای وب‌اپ

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# باز کن: http://localhost:8000
```

## 🐳 داکر (هر دو با هم)

```bash
docker build -t social-dl .
docker run -p 8000:8000 --env-file .env social-dl
```

## ⚠️ نکته اینستاگرام

اینستا گاهی لاگین می‌خواد. راه حل:
1. با افزونه Get cookies.txt لاگین کن و خروجی بگیر
2. بذار کنار پروژه با اسم `cookies.txt`
3. توی `.env` هم `COOKIES_FILE=cookies.txt` هست

## 📁 ساختار

```
downloader.py  → هسته yt-dlp (تشخیص پلتفرم، info، دانلود)
bot.py         → ربات تلگرام (aiogram)
app.py         → API + وب (FastAPI)
static/index.html → فرانت فارسی
```

## 🔌 API

- `POST /api/info` → `{url}` → مشخصات + کیفیت‌ها
- `POST /api/download` → `{url, quality}` → فایل (best/720/480/360/audio)
