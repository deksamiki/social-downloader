@echo off
chcp 65001 >nul
title Social Downloader Bot
cd /d "%~dp0"
echo ================================
echo   ربات دانلودر سوشال - تلگرام
echo ================================
echo.
echo برای خاموش کردن، این پنجره رو ببند.
echo.
python bot.py
pause
