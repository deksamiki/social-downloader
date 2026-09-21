"""
Social Downloader Bot — Telegram (aiogram 3.x)
Run: python bot.py
Env: BOT_TOKEN (required)
"""
import os
import asyncio
import logging
import shutil
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand,
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from downloader import (
    detect_platform, is_supported, extract_url,
    get_info, download_media, file_too_big_for_telegram,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip("\"'")
BOT_USERNAME = os.getenv("BOT_USERNAME", "branddownloader_bot").strip().lstrip("@")
if not BOT_TOKEN or "PUT-YOUR" in BOT_TOKEN:
    raise SystemExit("BOT_TOKEN در .env تنظیم نشده. از BotFather بگیر و بذار.")

logging.basicConfig(level=logging.INFO)
router = Router()

# ── Webhook support (for cloud deploys alongside the web app) ──────────
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")  # e.g. https://dl.example.com
WEBHOOK_PATH = "/bot/webhook"  # Telegram posts updates here (secret in BOT_TOKEN path below)
USE_WEBHOOK = bool(WEBHOOK_URL)

PLATFORM_FA = {
    "instagram": "📸 اینستاگرام",
    "youtube": "▶️ یوتیوب",
    "tiktok": "🎵 تیک‌تاک",
    "twitter": "✖️ ایکس (توییتر)",
    "pinterest": "📌 پینترست",
    "unknown": "❓ ناشناس",
}

# ── پیام‌ها ──────────────────────────────────────────────

WELCOME = (
    "👋 سلام رفیق! من <b>دانلودر سوشال</b> هستم 📥\n\n"
    "🔗 فقط <b>لینک پست یا ویدیو</b> رو برام بفرست، خودم دانلودش می‌کنم و همینجا تحویلت میدم.\n\n"
    "✅ چی پشتیبانی می‌کنم؟\n"
    "📸 اینستاگرام — پست، ریلز، IGTV\n"
    "▶️ یوتیوب — ویدیو، Shorts (با انتخاب کیفیت)\n"
    "🎵 تیک‌تاک — بدون واترمارک\n"
    "✖️ ایکس (توییتر) — ویدیو و گیف\n"
    "📌 پینترست — ویدیو و عکس\n\n"
    "👇 همین الان یه لینک بفرست تا شروع کنیم!\n"
    "❓ اگه بلد نیستی لینک کپی کنی، بزن روی دکمه «📎 آموزش کپی لینک»."
)

HELP_TEXT = (
    "🆘 <b>راهنمای استفاده</b>\n\n"
    "1️⃣ برو توی اینستا / یوتیوب / تیک‌تاک / ایکس / پینترست\n"
    "2️⃣ روی دکمه <b>Share → Copy Link</b> بزن\n"
    "3️⃣ لینک رو همینجا <b>Paste</b> کن و بفرست\n"
    "4️⃣ چند ثانیه صبر کن، فایل رو می‌فرستم 📥\n\n"
    "🎞 برای <b>یوتیوب</b> بعد از فرستادن لینک، کیفیت رو انتخاب می‌کنی:\n"
    "🎬 بهترین • 📺 720p • 📱 480p • 🎵 فقط صدا\n\n"
    "⚠️ چند نکته:\n"
    "• پیج‌های <b>پرایوت</b> دانلود نمیشن\n"
    "• استوری اینستا فقط اگه پیج <b>پابلیک</b> باشه\n"
    "• فایل‌های بالای ~۵۰ مگ رو تلگرام نمی‌ذاره بفرستم، لینک وب میدم\n\n"
    "دستورات:\n"
    "/start — شروع\n"
    "/help — همین راهنما\n"
    "/link — آموزش کپی لینک\n"
    "/about — درباره ربات"
)

LINK_GUIDE = (
    "📎 <b>آموزش کپی لینک از هر برنامه</b>\n\n"
    "📸 <b>اینستاگرام:</b>\n"
    "روی پست/ریلز → دکمه <b>✈️ Send → Copy Link</b>\n"
    "مثال:\n<code>https://www.instagram.com/reel/ABC123/</code>\n\n"
    "▶️ <b>یوتیوب:</b>\n"
    "زیر ویدیو → <b>Share → Copy link</b>\n"
    "مثال:\n<code>https://youtu.be/dQw4w9WgXcQ</code>\n\n"
    "🎵 <b>تیک‌تاک:</b>\n"
    "روی ویدیو → <b>Share → Copy link</b>\n"
    "مثال:\n<code>https://www.tiktok.com/@user/video/123...</code>\n\n"
    "✖️ <b>ایکس:</b>\n"
    "روی پست → <b>Share → Copy link</b>\n\n"
    "📌 <b>پینترست:</b>\n"
    "روی پین → <b>Share → Copy link</b>\n\n"
    "👇 حالا لینکت رو بفرست!"
)

ABOUT_TEXT = (
    "ℹ️ <b>درباره دانلودر سوشال</b>\n\n"
    "🤖 نسخه 1.0 — ساخته شده با Python + yt-dlp\n"
    "🌐 نسخه وب هم داریم (با همون موتور دانلود)\n"
    "⚡️ سرعت بالا، بدون واترمارک تیک‌تاک\n\n"
    f"📩 پشتیبانی: @{BOT_USERNAME}"
)

MSG_NO_LINK = (
    "🔗 لینکی توی پیامت پیدا نکردم!\n\n"
    "لطفاً یه <b>لینک مستقیم پست</b> بفرست، مثلاً:\n"
    "<code>https://www.instagram.com/reel/...</code>\n\n"
    "اگه بلد نیستی لینک بگیری، بزن /link"
)

MSG_UNSUPPORTED = (
    "❌ این لینک رو پشتیبانی نمی‌کنم.\n\n"
    "فعلاً فقط اینا:\n"
    "📸 اینستاگرام • ▶️ یوتیوب • 🎵 تیک‌تاک • ✖️ ایکس • 📌 پینترست\n\n"
    "لینکت از کدوم برنامه بود؟ اگه اشتباهی فرستادی، لینک درست رو بفرست."
)

MSG_YT_ASK_QUALITY = (
    "▶️ <b>لینک یوتیوب</b> شناسایی شد ✅\n\n"
    "🎞 کیفیت موردنظرت رو انتخاب کن:"
)

MSG_CHECKING = "🔍 <b>قدم ۱ از ۳:</b> در حال بررسی لینک...\n⏳ چند ثانیه صبر کن."
MSG_DOWNLOADING = "📥 <b>قدم ۲ از ۳:</b> لینک سالمه! دارم دانلود می‌کنم...\n🎬 <b>{title}</b>"
MSG_UPLOADING = "📤 <b>قدم ۳ از ۳:</b> دانلود تموم شد، دارم می‌فرستمش... 🚀"


def friendly_error(e: Exception) -> str:
    msg = str(e).lower()
    if "private" in msg or "login" in msg or "cookies" in msg or "403" in msg:
        return (
            "🔒 این پست <b>خصوصی (پرایوت)</b> هست یا نیاز به لاگین داره.\n\n"
            "• اگه پیج پرایوته، متأسفانه نمی‌تونم دانلود کنم\n"
            "• اگه پابلیکه ولی باز خطا میده، یه بار دیگه لینک رو بفرست"
        )
    if "not found" in msg or "404" in msg or "unavailable" in msg or "deleted" in msg:
        return (
            "🗑 این پست پیدا نشد — شاید <b>پاک شده</b> یا لینک ناقصه.\n\n"
            "لینک کامل رو دوباره Copy کن و بفرست."
        )
    if "timed out" in msg or "timeout" in msg:
        return "⏱ اتصال به سرور طول کشید. لطفاً ۱ دقیقه دیگه دوباره لینک رو بفرست."
    return f"❌ دانلود ناموفق شد.\n<code>{e}</code>\n\n💡 یه بار دیگه لینک رو بفرست، اگه باز نشد /link رو ببین."


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 آموزش کپی لینک", callback_data="menu:link")],
        [
            InlineKeyboardButton(text="🆘 راهنما", callback_data="menu:help"),
            InlineKeyboardButton(text="ℹ️ درباره", callback_data="menu:about"),
        ],
    ])


def quality_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 بهترین کیفیت", callback_data="q:best"),
            InlineKeyboardButton(text="📺 720p", callback_data="q:720"),
        ],
        [
            InlineKeyboardButton(text="📱 480p", callback_data="q:480"),
            InlineKeyboardButton(text="🎵 فقط صدا (MP3)", callback_data="q:audio"),
        ],
        [InlineKeyboardButton(text="🔙 انصراف", callback_data="q:cancel")],
    ])


def fmt_duration(sec) -> str:
    if not sec:
        return ""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# user_id -> last url
LAST_URL: dict[int, str] = {}


@router.message(CommandStart())
async def start(m: Message):
    await m.answer(WELCOME, parse_mode="HTML", reply_markup=main_menu())


@router.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("link"))
async def link_cmd(m: Message):
    await m.answer(LINK_GUIDE, parse_mode="HTML")


@router.message(Command("about"))
async def about_cmd(m: Message):
    await m.answer(ABOUT_TEXT, parse_mode="HTML")


@router.callback_query(F.data.startswith("menu:"))
async def on_menu(c: CallbackQuery):
    key = c.data.split(":", 1)[1]
    if key == "link":
        await c.message.answer(LINK_GUIDE, parse_mode="HTML")
    elif key == "help":
        await c.message.answer(HELP_TEXT, parse_mode="HTML")
    elif key == "about":
        await c.message.answer(ABOUT_TEXT, parse_mode="HTML")
    await c.answer()


@router.message(F.text)
async def handle_link(m: Message, bot: Bot):
    url = extract_url(m.text or "")
    if not url:
        return await m.answer(MSG_NO_LINK, parse_mode="HTML")
    if not is_supported(url):
        return await m.answer(MSG_UNSUPPORTED)

    plat = detect_platform(url)
    LAST_URL[m.from_user.id] = url

    if plat == "youtube":
        return await m.answer(
            MSG_YT_ASK_QUALITY,
            parse_mode="HTML",
            reply_markup=quality_keyboard(),
        )

    await process_download(m, bot, url, "best")


@router.message()
async def handle_non_text(m: Message):
    # photo / video / sticker / voice ... → guide back to sending a link
    await m.answer(
        "📎 من فقط با <b>لینک</b> کار می‌کنم!\n\n"
        "لطفاً لینک پست رو از برنامه کپی کن و اینجا بفرست.\n"
        "آموزش: /link",
        parse_mode="HTML",
    )


async def process_download(m: Message, bot: Bot, url: str, quality: str):
    plat = detect_platform(url)
    plat_fa = PLATFORM_FA.get(plat, plat)
    status = await m.answer(f"{plat_fa}\n{MSG_CHECKING}", parse_mode="HTML")
    await bot.send_chat_action(m.chat.id, ChatAction.TYPING)
    try:
        info = await get_info(url)
    except Exception as e:
        return await status.edit_text(friendly_error(e), parse_mode="HTML")

    dur = fmt_duration(info.duration)
    meta_line = f"👤 {info.uploader}\n⏱ {dur}\n" if (info.uploader or dur) else ""

    try:
        await status.edit_text(
            MSG_DOWNLOADING.format(title=(info.title[:80] or "بدون عنوان")),
            parse_mode="HTML",
        )
        await bot.send_chat_action(m.chat.id, ChatAction.UPLOAD_VIDEO)
        files = await download_media(url, quality)
    except Exception as e:
        return await status.edit_text(friendly_error(e), parse_mode="HTML")

    caption = (
        f"✅ <b>{info.title[:100] or 'دانلود شد'}</b>\n"
        f"{meta_line}"
        f"🏷 {plat_fa}\n"
        f"🤖 @{BOT_USERNAME}"
    )
    sent = False
    try:
        await status.edit_text(MSG_UPLOADING, parse_mode="HTML")
        for f in files[:4]:  # anti-spam: max 4 files
            if file_too_big_for_telegram(f):
                mb = f.stat().st_size / 1024 / 1024
                await m.answer(
                    f"⚠️ فایل <b>{f.name}</b> ({mb:.0f} مگ) از سقف تلگرام (~۵۰ مگ) بزرگ‌تره و نمی‌تونم بفرستمش.\n\n"
                    f"💡 راه‌حل:\n"
                    f"• کیفیت پایین‌تر رو امتحان کن (480p)\n"
                    f"• یا از نسخه وب دانلود کن",
                    parse_mode="HTML",
                )
                continue
            doc = FSInputFile(str(f))
            suffix = f.suffix.lower()
            if suffix in (".mp4", ".mov", ".mkv", ".webm"):
                await bot.send_chat_action(m.chat.id, ChatAction.UPLOAD_VIDEO)
                await m.answer_video(doc, caption=caption, parse_mode="HTML")
            elif suffix in (".mp3", ".m4a", ".ogg"):
                await m.answer_audio(doc, caption=caption, parse_mode="HTML")
            elif suffix in (".jpg", ".jpeg", ".png", ".webp"):
                await m.answer_photo(doc, caption=caption, parse_mode="HTML")
            else:
                await m.answer_document(doc, caption=caption, parse_mode="HTML")
            sent = True
        if not sent:
            await status.edit_text(
                "⚠️ فایل آماده شد ولی برای تلگرام خیلی حجیمه.\nکیفیت پایین‌تر رو امتحان کن (480p).",
            )
        else:
            try:
                await status.delete()
            except Exception:
                pass
            await m.answer(
                "🎉 تموم شد! یه لینک دیگه بفرست؟ 👇",
                reply_markup=main_menu(),
            )
    finally:
        if files:
            tmpdir = files[0].parent
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


@router.callback_query(F.data.startswith("q:"))
async def on_quality(c: CallbackQuery, bot: Bot):
    quality = c.data.split(":", 1)[1]
    if quality == "cancel":
        await c.message.edit_text("🔙 باشه، کنسل شد. یه لینک دیگه بفرست 👇")
        return await c.answer()
    url = LAST_URL.get(c.from_user.id)
    if not url:
        return await c.answer("لینک پیدا نشد، دوباره بفرست.", show_alert=True)
    q_fa = {"best": "بهترین کیفیت 🎬", "720": "720p 📺", "480": "480p 📱", "audio": "فقط صدا 🎵"}.get(quality, quality)
    await c.answer(f"⏳ دانلود با {q_fa} شروع شد...")
    try:
        await c.message.edit_text(f"⏳ کیفیت انتخاب شد: <b>{q_fa}</b>\nدارم دانلود می‌کنم...", parse_mode="HTML")
    except Exception:
        pass
    fake_msg = c.message
    fake_msg.from_user = c.from_user
    await process_download(fake_msg, bot, url, quality)


COMMANDS = [
    BotCommand(command="start", description="🚀 شروع ربات"),
    BotCommand(command="help", description="🆘 راهنمای استفاده"),
    BotCommand(command="link", description="📎 آموزش کپی لینک"),
    BotCommand(command="about", description="ℹ️ درباره ربات"),
]


async def main():
    bot = Bot(token=BOT_TOKEN)
    await bot.set_my_commands(COMMANDS)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    print(f"Bot is running (polling)... @{BOT_USERNAME}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
