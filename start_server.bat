@echo off
chcp 65001 >nul
title FinApp — Veb Server (localhost:8080)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   FinApp veb server ishga tushadi            ║
echo  ║   Manzil: http://localhost:8080              ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: server ning papkasiga o'tish
cd /d "%~dp0"

:: Brauzer 1 soniyadan keyin avtomatik ochilsin
start "" timeout /t 1 >nul
start "" "http://localhost:8080/finance_dashboard.html"

echo  [✓] Server ishga tushmoqda...
echo  [i] Sayt avtomatik brauzerda ochiladi
echo  [i] To'xtatish uchun: Ctrl + C
echo.
echo  Sayt manzili: http://localhost:8080/finance_dashboard.html
echo  Telegram bot  saytida: http://localhost:8080/finance_telegram.html
echo.

python -m http.server 8080

echo.
echo  [!] Server to'xtatildi.
pause
