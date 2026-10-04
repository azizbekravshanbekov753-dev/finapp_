@echo off
chcp 65001 >nul
title FinApp Bot — To'xtatish

echo.
echo  Bot to'xtatilmoqda...

:: Task Scheduler dan o'chirish
schtasks /delete /tn "FinAppBot" /f >nul 2>&1

:: Ishlayotgan python jarayonini topib o'ldirish
taskkill /f /fi "WINDOWTITLE eq FinApp*" >nul 2>&1

:: bot.py ishlatayotgan python ni to'xtatish
for /f "tokens=2" %%a in ('tasklist /fi "IMAGENAME eq python.exe" /fo csv /nh 2^>nul') do (
    wmic process %%~a get CommandLine 2>nul | find "bot.py" >nul 2>&1
    if not errorlevel 1 taskkill /pid %%~a /f >nul 2>&1
)

echo  [✓] Bot to'xtatildi
echo  [✓] Avtomatik ishga tushirish o'chirildi
echo.
pause
