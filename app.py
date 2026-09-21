"""
Social Downloader — Web API + Frontend (FastAPI)
Run: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import shutil
import urllib.parse
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from pydantic import BaseModel
from dotenv import load_dotenv

from aiogram.types import Update

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from downloader import detect_platform, is_supported, get_info, download_media

ROOT_PATH = os.getenv("ROOT_PATH", "").strip()  # e.g. "/dl" for site.com/dl — empty for subdomain/root
if ROOT_PATH and not ROOT_PATH.startswith("/"):
    ROOT_PATH = "/" + ROOT_PATH
if ROOT_PATH == "/":
    ROOT_PATH = ""

WEBHOOK_PATH = "/bot/webhook"
WEBHOOK_TOKEN_SECRET = os.getenv("WEBHOOK_TOKEN_SECRET", "").strip()

# ── Telegram bot (webhook), optional ─────────────────────────────────────
# Runs inside the same process as the web app on cloud deploys.
bot = None
dp = None
botmodule = None
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip("\"'")
USE_WEBHOOK = bool(BOT_TOKEN and "PUT-YOUR" not in BOT_TOKEN and os.getenv("WEBHOOK_URL", "").strip())
if USE_WEBHOOK:
    try:
        from aiogram import Bot, Dispatcher
        import bot as botmodule  # noqa: E402  (registers handlers via its router)
        WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=botmodule.MemoryStorage())
        dp.include_router(botmodule.router)
    except Exception as e:
        # Never take the web app down because of a bot misconfiguration.
        logging.error(f"Telegram bot disabled: {e}")
        bot = None
        dp = None
        botmodule = None
        USE_WEBHOOK = False

app = FastAPI(title="Social Downloader", version="1.0.0", root_path=ROOT_PATH)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

(STATIC_DIR := BASE_DIR / "static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class InfoReq(BaseModel):
    url: str


class DlReq(BaseModel):
    url: str
    quality: str = "best"  # best | 720 | 480 | 360 | audio


def _cleanup_dir(path: Path) -> None:
    """Delete the temp download dir after the file has been streamed out."""
    shutil.rmtree(path, ignore_errors=True)


@app.get("/", response_class=HTMLResponse)
def index():
    html = STATIC_DIR / "index.html"
    if html.exists():
        text = html.read_text(encoding="utf-8")
        # Inject <base> so relative "api/..." works under subfolder like /dl/
        base = (ROOT_PATH or "") + "/"
        if "<base" not in text:
            text = text.replace("<head>", f"<head>\n<base href=\"{base}\">", 1)
        return HTMLResponse(text)
    return HTMLResponse("<h1>Social Downloader API is running. See docs</h1>")


@app.get("/api/health")
def health():
    return {"ok": True, "bot": USE_WEBHOOK}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Telegram posts bot updates here. Secret path keeps it private."""
    if not USE_WEBHOOK or bot is None or dp is None:
        # Webhook route exists but bot is not configured — always answer 200
        # so Telegram doesn't retry forever and fill the update queue.
        return {"ok": True, "bot": False}
    if WEBHOOK_TOKEN_SECRET:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != WEBHOOK_TOKEN_SECRET:
            raise HTTPException(403, "Forbidden")
    payload = await request.json()
    update = Update(**payload)
    await dp.feed_webhook_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def setup_webhook():
    if USE_WEBHOOK and bot is not None and dp is not None:
        await bot.set_webhook(
            f"{WEBHOOK_URL}{WEBHOOK_PATH}",
            allowed_updates=dp.resolve_used_update_types(),
            secret_token=WEBHOOK_TOKEN_SECRET or None,
        )
        if botmodule is not None:
            await bot.set_my_commands(botmodule.COMMANDS)
        logging.info(f"Telegram webhook set: {WEBHOOK_URL}{WEBHOOK_PATH}")


@app.on_event("shutdown")
async def delete_webhook():
    if bot is not None:
        try:
            await bot.delete_webhook()
            await bot.session.close()
        except Exception:
            pass


@app.post("/api/info")
async def api_info(req: InfoReq):
    url = req.url.strip()
    if not url or not is_supported(url):
        raise HTTPException(400, "لینک پشتیبانی نمی‌شود. اینستاگرام، یوتیوب، تیک‌تاک، ایکس و پینترست.")
    try:
        info = await get_info(url)
    except Exception as e:
        raise HTTPException(422, f"خطا در بررسی لینک: {e}")
    return {
        "platform": info.platform,
        "title": info.title,
        "uploader": info.uploader,
        "duration": info.duration,
        "thumbnail": info.thumbnail,
        "qualities": [
            {"id": "best", "label": "🎬 بهترین کیفیت"},
            {"id": "720", "label": "📺 720p"},
            {"id": "480", "label": "📱 480p"},
            {"id": "360", "label": "📲 360p (کم‌حجم)"},
            {"id": "audio", "label": "🎵 فقط صدا MP3"},
        ],
    }


@app.post("/api/download")
async def api_download(req: DlReq):
    url = req.url.strip()
    if not url or not is_supported(url):
        raise HTTPException(400, "لینک نامعتبر است.")
    if req.quality not in ("best", "720", "480", "360", "audio"):
        raise HTTPException(400, "کیفیت نامعتبر است.")
    try:
        files = await download_media(url, req.quality)
    except Exception as e:
        raise HTTPException(422, f"دانلود ناموفق: {e}")
    # biggest file = main (or first)
    main = max(files, key=lambda p: p.stat().st_size)
    # delete sibling leftovers now, and the temp dir after the response is sent
    for f in files:
        if f != main:
            try: f.unlink()
            except Exception: pass
    filename = urllib.parse.quote(main.name)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return FileResponse(
        str(main),
        headers=headers,
        background=BackgroundTask(_cleanup_dir, main.parent),
    )
