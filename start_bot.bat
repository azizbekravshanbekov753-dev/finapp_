@echo off
chcp 65001 >nul
title FinApp — Telegram Bot

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   FinApp Telegram Bot ishga tushadi  ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: .env fayl bor bo'lsa token ni o'qish
if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="BOT_TOKEN" set BOT_TOKEN=%%b
    )
)

:: Token tekshirish
if "%BOT_TOKEN%"=="" (
    echo  [!] BOT_TOKEN topilmadi!
    echo.
    echo  .env fayl yarating va ichiga yozing:
    echo  BOT_TOKEN=sizning_tokeningiz
    echo.
    echo  Token olish: @BotFather da /newbot
    echo.
    pause
    exit
)

:: python-telegram-bot o'rnatilganmi tekshirish
python -c "import telegram" 2>nul
if errorlevel 1 (
    echo  [!] Kutubxona o'rnatilmoqda...
    pip install python-telegram-bot==20.7
    echo.
)

echo  [✓] Bot ishga tushmoqda...
echo  [i] To'xtatish: Ctrl + C
echo.

python bot.py

echo.
echo  [!] Bot to'xtatildi.
pause
