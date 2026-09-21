import os
import re
import asyncio
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import yt_dlp

def _resolve_download_dir() -> Path:
    """First writable candidate wins — hosts like blitz.cloud may mount /app read-only."""
    candidates = [
        Path(os.getenv("DOWNLOAD_DIR", "downloads")),
        Path(tempfile.gettempdir()) / "social-dl",
    ]
    last_err: Optional[Exception] = None
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            probe = c / ".writetest"
            probe.touch()
            probe.unlink(missing_ok=True)
            return c
        except OSError as e:
            last_err = e
            continue
    raise RuntimeError(f"No writable download dir ({last_err})")


DOWNLOAD_DIR = _resolve_download_dir()
MAX_TELEGRAM_MB = int(os.getenv("MAX_TELEGRAM_MB", "48"))
COOKIES_FILE = os.getenv("COOKIES_FILE", "")  # e.g. cookies.txt for Instagram

PLATFORM_PATTERNS = {
    "instagram": r"(instagram\.com|instagr\.am)",
    "youtube": r"(youtube\.com|youtu\.be)",
    "tiktok": r"(tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com)",
    "twitter": r"(twitter\.com|x\.com)",
    "pinterest": r"(pinterest\.com|pin\.it)",
}


def detect_platform(url: str) -> str:
    url_l = url.lower()
    for name, pat in PLATFORM_PATTERNS.items():
        if re.search(pat, url_l):
            return name
    return "unknown"


def is_supported(url: str) -> bool:
    return detect_platform(url) != "unknown"


def base_opts() -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 30,
        # TikTok watermark-free + Instagram best fidelity
        "extractor_args": {},
    }
    if COOKIES_FILE and Path(COOKIES_FILE).exists():
        opts["cookiefile"] = COOKIES_FILE
    # Spoof a real browser — critical for TikTok / Instagram / X
    opts["http_headers"] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    return opts


@dataclass
class MediaInfo:
    platform: str
    title: str
    uploader: str
    duration: Optional[int]
    thumbnail: Optional[str]
    formats_summary: list  # [{format_id, ext, resolution, filesize_approx, vcodec, acodec}]
    is_video: bool = True


def _summarize_formats(info: dict) -> list:
    out = []
    for f in info.get("formats", [])[-30:]:  # last ones = best usually
        if f.get("vcodec") == "none":
            continue  # skip audio-only here (handled separately)
        out.append({
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "resolution": f.get("resolution") or f"{f.get('width', '?')}x{f.get('height', '?')}",
            "height": f.get("height") or 0,
            "filesize_approx": f.get("filesize") or f.get("filesize_approx"),
            "fps": f.get("fps"),
        })
    # dedupe by height, keep best ext
    seen = {}
    for x in out:
        h = x["height"]
        if h not in seen:
            seen[h] = x
    return sorted(seen.values(), key=lambda x: x["height"])


def get_info_sync(url: str) -> MediaInfo:
    opts = base_opts()
    opts.update({"skip_download": True})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # playlist edge (e.g. youtube list url) → take first entry
    if info.get("_type") == "playlist":
        entries = [e for e in info.get("entries", []) if e]
        if not entries:
            raise ValueError("پلی‌لیست خالی است یا خصوصی است.")
        info = entries[0]
    return MediaInfo(
        platform=detect_platform(url),
        title=info.get("title", "بدون عنوان")[:200],
        uploader=str(info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        formats_summary=_summarize_formats(info),
    )


def download_sync(url: str, quality: str = "best") -> list[Path]:
    """
    quality: 'best' | '720' | '480' | '360' | 'audio'
    returns list of downloaded file paths
    """
    tmpdir = Path(tempfile.mkdtemp(dir=str(DOWNLOAD_DIR)))
    outtmpl = str(tmpdir / "%(title).60s_%(id)s.%(ext)s")

    opts = base_opts()
    opts.update({
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
        if quality != "audio" else
        [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    })

    if quality == "audio":
        opts["format"] = "bestaudio/best"
    elif quality == "best":
        opts["format"] = "bv*+ba/best"
    elif quality.isdigit():
        h = int(quality)
        opts["format"] = f"bv*[height<={h}]+ba/b[height<={h}]/b[height<={h}]/best"
    else:
        opts["format"] = "bv*+ba/best"

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    files = [p for p in tmpdir.iterdir() if p.is_file()]
    if not files:
        raise RuntimeError("دانلود ناموفق بود — فایلی ساخته نشد.")
    return files


async def get_info(url: str) -> MediaInfo:
    return await asyncio.to_thread(get_info_sync, url)


async def download_media(url: str, quality: str = "best") -> list[Path]:
    return await asyncio.to_thread(download_sync, url, quality)


def file_too_big_for_telegram(path: Path) -> bool:
    return path.stat().st_size > MAX_TELEGRAM_MB * 1024 * 1024


URL_RE = re.compile(r"https?://[^\s<>\"'()]+")

def extract_url(text: str) -> Optional[str]:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,!?؛،") if m else None
