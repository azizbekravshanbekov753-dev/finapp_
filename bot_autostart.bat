@echo off
chcp 65001 >nul
title FinApp Bot — Task Scheduler sozlash

cd /d "%~dp0"

echo.
echo  ╔═══════════════════════════════════════════════╗
echo  ║   FinApp Bot — Kompyuter yoqilganda           ║
echo  ║   avtomatik ishga tushirish sozlanmoqda       ║
echo  ╚═══════════════════════════════════════════════╝
echo.

:: Bot fayl yo'li
set BOT_PATH=%~dp0bot.py
set WORK_DIR=%~dp0

:: Python yo'lini topish
for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
if "%PYTHON_PATH%"=="" (
    echo [!] Python topilmadi! Avval Python o'rnating.
    pause
    exit
)

echo [✓] Python: %PYTHON_PATH%
echo [✓] Bot: %BOT_PATH%
echo.

:: python-telegram-bot o'rnatish
echo [1/3] Kutubxona tekshirilmoqda...
%PYTHON_PATH% -c "import telegram" 2>nul
if errorlevel 1 (
    echo [!] O'rnatilmoqda...
    pip install python-telegram-bot==20.7
)
echo [✓] Kutubxona tayyor

:: Task Scheduler ga qo'shish
echo [2/3] Task Scheduler ga qo'shilmoqda...

schtasks /delete /tn "FinAppBot" /f >nul 2>&1

schtasks /create /tn "FinAppBot" ^
  /tr "\"%PYTHON_PATH%\" \"%BOT_PATH%\"" ^
  /sc onlogon ^
  /rl highest ^
  /f >nul 2>&1

if errorlevel 1 (
    echo [!] Administrator huquqi kerak!
    echo     Ushbu faylni o'ng bosib "Administrator sifatida ishga tushiring"
    pause
    exit
)

echo [✓] Task Scheduler ga qo'shildi

:: Hozir ham ishga tushirish
echo [3/3] Bot hozir ishga tushirilmoqda...
schtasks /run /tn "FinAppBot" >nul 2>&1

echo.
echo  ════════════════════════════════════════════════
echo  ✅ TAYYOR! Bot endi:
echo     - Hozir ishlayapti (fonda)
echo     - Kompyuter yoqilganda avtomatik ishga tushadi
echo     - Kompyuter o'chganda to'xtaydi
echo  ════════════════════════════════════════════════
echo.
echo  Tekshirish: Task Manager ^> Details ^> python.exe
echo  To'xtatish: bot_stop.bat
echo.
pause
