# 🚀 FinApp Botni 24/7 Ishlatish

## Kerakli narsalar
- GitHub akkount (bepul) — github.com
- Railway akkount (bepul) — railway.app
- Git dasturi — git-scm.com

---

## 1-QADAM: Git o'rnatish

1. https://git-scm.com/download/win ga boring
2. "64-bit Git for Windows Setup" yuklab oling
3. O'rnating (hammasi default — Next, Next, Finish)
4. Kompyuterni qayta yuring

---

## 2-QADAM: GitHub ga yuklash

1. https://github.com → akkount oching yoki kiring
2. "+" → "New repository"
3. Repository name: `finapp`
4. "Public" tanlang
5. "Create repository" bosing
6. Ko'rsatilgan URL ni nusxa oling (masalan: `https://github.com/ali/finapp.git`)

Keyin:
7. `github_upload.bat` ga **ikki marta bosing**
8. Ko'rsatilgan URL ni kiriting
9. GitHub username va parolni so'rasa kiriting

✅ Fayllar yuklandi!

---

## 3-QADAM: Railway da Deploy

1. https://railway.app ga boring
2. "Login with GitHub" bosing
3. "New Project" bosing
4. "Deploy from GitHub repo" bosing
5. `finapp` ni tanlang
6. **"Variables"** tabiga o'ting:
   - "New Variable" bosing
   - Name: `BOT_TOKEN`
   - Value: `8833504850:AAGzyB3hSvBV3GzEDRfTc3wlLR_IrY7FDpw`
   - Add bosing

7. **"New Volume"** bosing (ma'lumotlar saqlanishi uchun):
   - Mount Path: `/data`
   - Add bosing

8. Deploy avtomatik boshlanadi

✅ Bot 24/7 ishlaydi!

---

## 4-QADAM: Tekshirish

Telegram da botingizga `/start` yozing — javob bersa tayyor!

---

## Muammo bo'lsa

Railway → Deployments → Logs ni oching — xato xabarini ko'ring.

Ko'p uchraydigan xatolar:
- `BOT_TOKEN not found` → Variables ga token qo'shing
- `ModuleNotFoundError` → requirements.txt to'g'ri yuklangani tekshiring
