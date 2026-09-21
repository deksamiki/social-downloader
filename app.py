"""
Social Downloader — Web API + Frontend (FastAPI)
Run: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import shutil
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from downloader import detect_platform, is_supported, get_info, download_media

ROOT_PATH = os.getenv("ROOT_PATH", "").strip()  # e.g. "/dl" for site.com/dl — empty for subdomain/root
if ROOT_PATH and not ROOT_PATH.startswith("/"):
    ROOT_PATH = "/" + ROOT_PATH
if ROOT_PATH == "/":
    ROOT_PATH = ""

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
    return {"ok": True}


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
    # cleanup siblings later — schedule simple: leave tmpdir, OS cleans? Better: keep file, delete rest now
    for f in files:
        if f != main:
            try: f.unlink()
            except Exception: pass
    filename = urllib.parse.quote(main.name)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return FileResponse(str(main), headers=headers, background=None)
