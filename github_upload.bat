@echo off
chcp 65001 >nul
title FinApp — GitHub ga yuklash

echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║   FinApp — GitHub ga yuklash             ║
echo  ╚═══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Git o'rnatilganmi tekshirish
git --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Git topilmadi!
    echo.
    echo  Git o'rnatish: https://git-scm.com/download/win
    echo  O'rnatib qayta ishga tushiring.
    echo.
    pause
    exit
)

echo  GitHub repository URL ni kiriting:
echo  (Masalan: https://github.com/username/finapp.git)
echo.
set /p REPO_URL="URL: "

if "%REPO_URL%"=="" (
    echo  [!] URL kiritilmadi!
    pause
    exit
)

echo.
echo  [1/5] Git boshlash...
git init

echo  [2/5] Fayllar qo'shilmoqda (.env va fin_db.json yuklanmaydi)...
git add .

echo  [3/5] Commit...
git commit -m "FinApp - Shaxsiy moliya va qarz boshqaruv ilovasi"

echo  [4/5] Main branch...
git branch -M main

echo  [5/5] GitHub ga yuklash...
git remote add origin %REPO_URL% 2>nul
git remote set-url origin %REPO_URL%
git push -u origin main

echo.
echo  ════════════════════════════════════════════
echo  ✅ GitHub ga yuklandi!
echo.
echo  Endi Railway da 24/7 ishlatish uchun:
echo  1. https://railway.app ga kiring
echo  2. "New Project" - "Deploy from GitHub repo"
echo  3. Reponi tanlang
echo  4. Variables: BOT_TOKEN = tokeningiz
echo  5. Deploy bosing
echo  ════════════════════════════════════════════
echo.
pause
