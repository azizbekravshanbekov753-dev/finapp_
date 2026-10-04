# -*- coding: utf-8 -*-
"""
FinApp Telegram Bot — Sayt bilan to'liq mos
Ishga tushirish: pip install python-telegram-bot && python bot.py
"""

import json, os, re, time, logging
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

# ── Token va DB fayl ──────────────────────────────
TOKEN   = os.environ.get("BOT_TOKEN", "")
# Railway da /data papkasi persistent volume bo'ladi
# Lokal ishlatganda bot.py yonida fin_db.json
_data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
DB_FILE   = os.path.join(_data_dir, "fin_db.json")

if not TOKEN:
    # .env fayldan o'qishga urinish
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN="):
                    TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

if not TOKEN:
    print("=" * 52)
    print("❌ BOT_TOKEN topilmadi!")
    print()
    print("Quyidagilardan birini bajaring:")
    print()
    print("1) .env fayl yarating va ichiga yozing:")
    print("   BOT_TOKEN=sizning_tokeningiz")
    print()
    print("2) Yoki terminal da:")
    print("   set BOT_TOKEN=sizning_tokeningiz  (Windows)")
    print("   export BOT_TOKEN=sizning_tokeningiz  (Mac/Linux)")
    print()
    print("Token olish: @BotFather → /newbot")
    print("=" * 52)
    exit(1)

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────
(
    ST_START,
    # Auth
    ST_AUTH_CHOOSE,
    ST_REG_USER, ST_REG_PASS, ST_REG_PASS2,
    ST_LOG_USER, ST_LOG_PASS,
    # Bosh menyu
    ST_MAIN,
    # Xarajat
    ST_EXP_NAME, ST_EXP_AMT, ST_EXP_CAT, ST_EXP_NOTE,
    # Qarz
    ST_DEBT_TYPE, ST_DEBT_WHY, ST_DEBT_AMT, ST_DEBT_PERSON, ST_DEBT_DAYS, ST_DEBT_NOTE,
    # Dashboard va ro'yxatlar
    ST_DASHBOARD, ST_LIST,
) = range(20)

# ── Kategoriyalar ─────────────────────────────────
CATS = [
    ("food",          "🍔", "Ovqat"),
    ("transport",     "🚌", "Transport"),
    ("entertainment", "🎮", "Dam olish"),
    ("health",        "💊", "Sog'liq"),
    ("shopping",      "🛍️", "Xarid"),
    ("education",     "📚", "Ta'lim"),
    ("utilities",     "💡", "Kommunal"),
    ("other",         "📌", "Boshqa"),
]
CAT_DICT = {k: (e, n) for k, e, n in CATS}

# ═══════════════════════════════════════════════════
# DB QATLAMI
# ═══════════════════════════════════════════════════
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"DB o'qish xatosi: {e}")
    return {"users": []}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def _hash(pw: str) -> str:
    """Saytdagi Auth._hash() bilan aynan bir xil."""
    h = 0
    for ch in pw:
        h = ((31 * h) + ord(ch)) & 0xFFFFFFFF
        if h > 0x7FFFFFFF:
            h -= 0x100000000
    return "h" + format(abs(h), "x")

def make_uid():
    return format(int(time.time()*1000), "x") + format(int(time.time()*1000) % 9999, "x")

def today():
    return date.today().isoformat()

def fmt(n):
    try: return f"{int(n):,}".replace(",", " ") + " so'm"
    except: return str(n) + " so'm"

# ── Foydalanuvchi CRUD ────────────────────────────
def find_user(db, username: str):
    return next((u for u in db.get("users", []) if u["username"] == username.lower()), None)

def register(db, username, password):
    username = username.strip().lower()
    if len(username) < 3:
        return None, "Username kamida 3 ta belgi bo'lishi kerak"
    if len(password) < 4:
        return None, "Parol kamida 4 ta belgi bo'lishi kerak"
    if find_user(db, username):
        return None, "Bu username allaqachon band. Boshqasini tanlang."
    user = {
        "id":           "u_" + username,
        "username":     username,
        "displayName":  username[0].upper() + username[1:],
        "password":     password,
        "passwordHash": _hash(password),
        "createdAt":    datetime.utcnow().isoformat() + "Z",
    }
    db.setdefault("users", []).append(user)
    save_db(db)
    return user, None

def login(db, username, password):
    u = find_user(db, username)
    if not u: return None, "Foydalanuvchi topilmadi"
    if u.get("password") == password or u.get("passwordHash") == _hash(password):
        return u, None
    return None, "Parol noto'g'ri"

# ── Xarajat / Qarz CRUD ───────────────────────────
def add_expense(db, uid, desc, amount, cat, note=""):
    key  = uid + "_expenses"
    lst  = db.get(key, [])
    item = {
        "id": make_uid(), "userId": uid,
        "description": desc, "amount": amount,
        "category": cat, "note": note,
        "date": today(), "createdAt": datetime.utcnow().isoformat()+"Z",
        "source": "telegram",
    }
    lst.insert(0, item)
    db[key] = lst
    save_db(db)
    return item

def add_debt(db, uid, dtype, desc, amount, person="", days=0, note=""):
    key      = uid + "_debts"
    lst      = db.get(key, [])
    deadline = (date.today() + timedelta(days=days)).isoformat() if days > 0 else ""
    item = {
        "id": make_uid(), "userId": uid,
        "type": dtype, "description": desc,
        "amount": amount, "person": person,
        "deadline": deadline, "daysCount": days,
        "note": note, "date": today(),
        "createdAt": datetime.utcnow().isoformat()+"Z",
        "paid": False, "source": "telegram",
    }
    lst.insert(0, item)
    db[key] = lst
    save_db(db)
    return item

def get_expenses(db, uid): return db.get(uid+"_expenses", [])
def get_debts(db, uid):    return db.get(uid+"_debts", [])

# ═══════════════════════════════════════════════════
# KLAVIATURALAR
# ═══════════════════════════════════════════════════
def kb_auth():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Kirish (akkount bor)",        callback_data="do_login")],
        [InlineKeyboardButton("📝 Ro'yxatdan o'tish (yangi)", callback_data="do_reg")],
    ])

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 Xarajat qo'shish",  callback_data="m_exp"),
         InlineKeyboardButton("🤝 Qarz qo'shish",     callback_data="m_debt")],
        [InlineKeyboardButton("📊 Dashboard",          callback_data="m_dash"),
         InlineKeyboardButton("🔔 Bildirishnomalar",   callback_data="m_notif")],
        [InlineKeyboardButton("📋 Xarajatlar tarixi",  callback_data="m_explist"),
         InlineKeyboardButton("📋 Qarzlar ro'yxati",   callback_data="m_debtlist")],
        [InlineKeyboardButton("🎯 Maqsadlar",          callback_data="m_goals"),
         InlineKeyboardButton("💳 Hamyonlar",          callback_data="m_wallets")],
        [InlineKeyboardButton("📈 Analitika",          callback_data="m_analytics"),
         InlineKeyboardButton("👥 Guruh bo'lish",      callback_data="m_split")],
        [InlineKeyboardButton("⚙️ Sozlamalar",          callback_data="m_settings"),
         InlineKeyboardButton("🚪 Chiqish",            callback_data="m_logout")],
    ])

def kb_cats():
    rows, row = [], []
    for k, e, n in CATS:
        row.append(InlineKeyboardButton(f"{e} {n}", callback_data=f"cat_{k}"))
        if len(row) == 2: rows.append(row); row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

def kb_debt_type():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Men BERDIM  (u menga qaytaradi)",  callback_data="dt_out")],
        [InlineKeyboardButton("💰 Men OLDIM   (men qaytaraman)",     callback_data="dt_in")],
    ])

def kb_skip(label="⏩ O'tkazib yuborish"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="skip")]])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back")]])

def kb_yn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Ha", callback_data="yes"),
         InlineKeyboardButton("❌ Yo'q", callback_data="no")]
    ])

# ═══════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    name = update.effective_user.first_name or "Salom"
    await update.message.reply_text(
        f"👋 Xush kelibsiz, <b>{name}</b>!\n\n"
        f"💰 <b>FinApp</b> — Shaxsiy moliya boshqaruvi\n\n"
        f"🌐 Agar saytda akkountingiz bo'lsa — <b>Kirish</b> ni bosing\n"
        f"   va saytdagi barcha ma'lumotlaringiz botda ham ko'rinadi!\n\n"
        f"🆕 Yangi foydalanuvchimisiz? — <b>Ro'yxatdan o'ting</b>",
        parse_mode="HTML",
        reply_markup=kb_auth(),
    )
    return ST_AUTH_CHOOSE

# ═══════════════════════════════════════════════════
# AUTH — Kirish tugmasi
# ═══════════════════════════════════════════════════
async def on_auth_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "do_login":
        await q.message.edit_text(
            "🔐 <b>Kirish</b>\n\n"
            "Saytda ro'yxatdan o'tganda tanlagan\n"
            "<b>username</b> ingizni kiriting:",
            parse_mode="HTML"
        )
        return ST_LOG_USER
    else:
        await q.message.edit_text(
            "📝 <b>Ro'yxatdan o'tish</b>\n\n"
            "Yangi <b>username</b> tanlang:\n"
            "• Kamida 3 ta belgi\n"
            "• Faqat harf va raqam\n"
            "• Kichik harfda (masalan: ali99)",
            parse_mode="HTML"
        )
        return ST_REG_USER

# ── Register ──────────────────────────────────────
async def reg_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.message.text.strip().lower()
    if len(u) < 3:
        await update.message.reply_text("❗ Kamida 3 ta belgi. Qayta kiriting:")
        return ST_REG_USER
    db = load_db()
    if find_user(db, u):
        await update.message.reply_text(
            f"❌ <b>{u}</b> — bu username band.\n\nBoshqa nom kiriting:",
            parse_mode="HTML"
        )
        return ST_REG_USER
    ctx.user_data["ru"] = u
    await update.message.reply_text(
        f"✅ <b>{u}</b> — bo'sh!\n\n🔐 Parol o'ylab toping:\n• Kamida 4 ta belgi",
        parse_mode="HTML"
    )
    return ST_REG_PASS

async def reg_pass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pw = update.message.text.strip()
    if len(pw) < 4:
        await update.message.reply_text("❗ Kamida 4 ta belgi. Qayta kiriting:")
        return ST_REG_PASS
    ctx.user_data["rp"] = pw
    await update.message.reply_text("🔐 Parolni <b>tasdiqlang</b> (qayta yozing):", parse_mode="HTML")
    return ST_REG_PASS2

async def reg_pass2(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pw2 = update.message.text.strip()
    if pw2 != ctx.user_data.get("rp"):
        await update.message.reply_text("❌ Parollar mos kelmadi. Qaytadan kiriting:")
        return ST_REG_PASS
    db = load_db()
    user, err = register(db, ctx.user_data["ru"], ctx.user_data["rp"])
    if err:
        await update.message.reply_text(f"❌ {err}")
        return ST_REG_USER
    ctx.user_data["user"] = user
    await update.message.reply_text(
        f"🎉 <b>Ro'yxatdan o'tdingiz!</b>\n\n"
        f"👤 Username: <code>{user['username']}</code>\n"
        f"🔐 Parolingizni eslab qoling!\n\n"
        f"🌐 Shu username + parol bilan saytga ham kirishingiz mumkin.\n\n"
        f"Asosiy menyuga xush kelibsiz! 👇",
        parse_mode="HTML",
        reply_markup=kb_main()
    )
    return ST_MAIN

# ── Login ─────────────────────────────────────────
async def log_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.message.text.strip().lower()
    db = load_db()
    if not find_user(db, u):
        await update.message.reply_text(
            f"❌ <b>{u}</b> — topilmadi.\n\n"
            f"Username to'g'ri yozdingizmi? Qayta kiriting:",
            parse_mode="HTML"
        )
        return ST_LOG_USER
    ctx.user_data["lu"] = u
    await update.message.reply_text("🔐 Parolni kiriting:")
    return ST_LOG_PASS

async def log_pass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pw = update.message.text.strip()
    db = load_db()
    user, err = login(db, ctx.user_data["lu"], pw)
    if err:
        await update.message.reply_text(
            f"❌ {err}\n\nQayta urinib ko'ring:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Qayta urinish", callback_data="retry_login")],
                [InlineKeyboardButton("🏠 Boshiga qaytish", callback_data="restart")],
            ])
        )
        return ST_LOG_PASS
    ctx.user_data["user"] = user
    db2 = load_db()
    exp_c  = len(get_expenses(db2, user["id"]))
    debt_c = len(get_debts(db2, user["id"]))
    await update.message.reply_text(
        f"✅ Xush kelibsiz, <b>{user['displayName']}</b>!\n\n"
        f"📊 Sizning ma'lumotlaringiz:\n"
        f"   💸 Xarajatlar: <b>{exp_c} ta</b>\n"
        f"   🤝 Qarzlar: <b>{debt_c} ta</b>\n\n"
        f"Asosiy menyu 👇",
        parse_mode="HTML",
        reply_markup=kb_main()
    )
    return ST_MAIN

# ═══════════════════════════════════════════════════
# ASOSIY MENYU TUGMALARI
# ═══════════════════════════════════════════════════
async def on_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = ctx.user_data.get("user")

    # Qayta urinish va restart
    if q.data == "retry_login":
        await q.message.edit_text("🔐 Parolni qayta kiriting:")
        return ST_LOG_PASS
    if q.data == "restart":
        ctx.user_data.clear()
        await q.message.edit_text(
            "🏠 Bosh sahifaga qaytdingiz.",
            reply_markup=kb_auth()
        )
        return ST_AUTH_CHOOSE
    if q.data == "back":
        await q.message.edit_text(
            f"🏠 <b>{user['displayName']}</b> — Asosiy menyu",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return ST_MAIN

    if not user:
        await q.message.edit_text("❌ Iltimos avval kiring!", reply_markup=kb_auth())
        return ST_AUTH_CHOOSE

    # ── Menyu bo'limlari ──────────────────────────
    if q.data == "m_exp":
        await q.message.edit_text(
            "💸 <b>XARAJAT QO'SHISH</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣  <b>Nima uchun xarajat qildingiz?</b>\n\n"
            "Misol: <i>Tushlik, Taksi, Kino, Dori...</i>",
            parse_mode="HTML"
        )
        return ST_EXP_NAME

    if q.data == "m_debt":
        await q.message.edit_text(
            "🤝 <b>QARZ QO'SHISH</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "<b>Qarz turini tanlang:</b>",
            parse_mode="HTML",
            reply_markup=kb_debt_type()
        )
        return ST_DEBT_TYPE

    if q.data == "m_dash":
        await show_dashboard(q.message, ctx)
        return ST_MAIN

    if q.data == "m_notif":
        await show_notifs(q.message, ctx)
        return ST_MAIN

    if q.data == "m_explist":
        await show_exp_list(q.message, ctx)
        return ST_MAIN

    if q.data == "m_debtlist":
        await show_debt_list(q.message, ctx)
        return ST_MAIN

    if q.data == "m_goals":
        await show_goals(q.message, ctx)
        return ST_MAIN

    if q.data == "m_wallets":
        await show_wallets(q.message, ctx)
        return ST_MAIN

    if q.data == "m_analytics":
        await show_analytics(q.message, ctx)
        return ST_MAIN

    if q.data == "m_split":
        await show_split(q.message, ctx)
        return ST_MAIN

    if q.data == "m_settings":
        await show_settings(q.message, ctx)
        return ST_MAIN

    if q.data == "m_logout":
        name = user["displayName"]
        ctx.user_data.clear()
        await q.message.edit_text(
            f"👋 Xayr, <b>{name}</b>!\n\n/start — qayta kirish",
            parse_mode="HTML"
        )
        return ST_AUTH_CHOOSE

    return ST_MAIN

# ═══════════════════════════════════════════════════
# XARAJAT QO'SHISH — step by step
# ═══════════════════════════════════════════════════
async def exp_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """1. Nima uchun?"""
    ctx.user_data["en"] = update.message.text.strip()
    await update.message.reply_text(
        f"💸 <b>XARAJAT</b>: {ctx.user_data['en']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"2️⃣  <b>Qancha pul sarfladingiz?</b>\n\n"
        f"Misol: <i>15000</i>  yoki  <i>35 ming</i>",
        parse_mode="HTML"
    )
    return ST_EXP_AMT

async def exp_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """2. Summa"""
    txt = re.sub(r"[\s,]", "", update.message.text.strip())
    # ming, mln qo'shimchalar
    mul = 1
    if re.search(r"ming|min|k", txt, re.I): mul = 1000; txt = re.sub(r"[^\d.]","",txt)
    elif re.search(r"mln|million", txt, re.I): mul = 1000000; txt = re.sub(r"[^\d.]","",txt)
    else: txt = re.sub(r"[^\d.]","",txt)
    try:
        amt = float(txt) * mul
        if amt <= 0: raise ValueError
    except:
        await update.message.reply_text("❗ To'g'ri summa kiriting. Masalan: <b>15000</b>", parse_mode="HTML")
        return ST_EXP_AMT
    ctx.user_data["ea"] = amt
    await update.message.reply_text(
        f"💸 <b>XARAJAT</b>: {ctx.user_data['en']} — {fmt(amt)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"3️⃣  <b>Kategoriyani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb_cats()
    )
    return ST_EXP_CAT

async def exp_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """3. Kategoriya"""
    q = update.callback_query; await q.answer()
    ctx.user_data["ec"] = q.data.replace("cat_", "")
    cat = CAT_DICT.get(ctx.user_data["ec"], ("📌","Boshqa"))
    await q.message.edit_text(
        f"💸 <b>XARAJAT</b>: {ctx.user_data['en']} — {fmt(ctx.user_data['ea'])}\n"
        f"   Kategoriya: {cat[0]} {cat[1]}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"4️⃣  <b>Izoh qo'shasizmi?</b> (ixtiyoriy)\n"
        f"Yozmasangiz o'tkazib yuboring 👇",
        parse_mode="HTML",
        reply_markup=kb_skip("⏩ Izohsiz saqlash")
    )
    return ST_EXP_NOTE

async def exp_note_txt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_expense(update.message, ctx, update.message.text.strip(), edit=False)

async def exp_note_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    return await _save_expense(q.message, ctx, "", edit=True)

async def _save_expense(msg, ctx, note, edit=False):
    user = ctx.user_data["user"]
    db   = load_db()
    e    = add_expense(db, user["id"], ctx.user_data["en"],
                       ctx.user_data["ea"], ctx.user_data["ec"], note)
    cat  = CAT_DICT.get(e["category"], ("📌","Boshqa"))
    text = (
        f"✅ <b>XARAJAT SAQLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Nima uchun:  <b>{e['description']}</b>\n"
        f"💵 Summa:       <b>{fmt(e['amount'])}</b>\n"
        f"{cat[0]} Kategoriya: <b>{cat[1]}</b>\n"
        f"📅 Sana:        <b>{e['date']}</b>\n"
        + (f"📎 Izoh:        <i>{note}</i>\n" if note else "") +
        f"\n🌐 Saytda ham ko'rinadi!"
    )
    fn = msg.edit_text if edit else msg.reply_text
    await fn(text, parse_mode="HTML", reply_markup=kb_main())
    log.info(f"Xarajat: {user['username']} | {e['description']} | {e['amount']}")
    return ST_MAIN

# ═══════════════════════════════════════════════════
# QARZ QO'SHISH — step by step
# ═══════════════════════════════════════════════════
async def debt_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """1. Tur tanlash"""
    q = update.callback_query; await q.answer()
    ctx.user_data["dt"] = "debt_out" if q.data == "dt_out" else "debt_in"
    lbl = "🤝 MEN BERDIM" if ctx.user_data["dt"] == "debt_out" else "💰 MEN OLDIM"
    q2  = "kimga berdingiz?" if ctx.user_data["dt"] == "debt_out" else "kimdan oldingiz?"
    await q.message.edit_text(
        f"🤝 <b>QARZ — {lbl}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"2️⃣  <b>Nima uchun qarz {q2[:q2.index('?')]}?</b>\n\n"
        f"Misol: <i>Uy uchun, Oziq-ovqat, Shoshilinch holat...</i>",
        parse_mode="HTML"
    )
    return ST_DEBT_WHY

async def debt_why(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """2. Nima uchun"""
    ctx.user_data["dw"] = update.message.text.strip()
    q = "berayotgan" if ctx.user_data["dt"] == "debt_out" else "olayotgan"
    await update.message.reply_text(
        f"🤝 <b>QARZ</b>: {ctx.user_data['dw']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"3️⃣  <b>Qancha pul {q}siz?</b>\n\n"
        f"Misol: <i>50000</i>  yoki  <i>100 ming</i>",
        parse_mode="HTML"
    )
    return ST_DEBT_AMT

async def debt_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """3. Summa"""
    txt = re.sub(r"[\s,]", "", update.message.text.strip())
    mul = 1
    if re.search(r"ming|min|k", txt, re.I): mul = 1000; txt = re.sub(r"[^\d.]","",txt)
    elif re.search(r"mln|million", txt, re.I): mul = 1000000; txt = re.sub(r"[^\d.]","",txt)
    else: txt = re.sub(r"[^\d.]","",txt)
    try:
        amt = float(txt) * mul
        if amt <= 0: raise ValueError
    except:
        await update.message.reply_text("❗ To'g'ri summa kiriting. Masalan: <b>50000</b>", parse_mode="HTML")
        return ST_DEBT_AMT
    ctx.user_data["da"] = amt
    q = "kimga berdingiz?" if ctx.user_data["dt"] == "debt_out" else "kimdan oldingiz?"
    await update.message.reply_text(
        f"🤝 <b>QARZ</b>: {ctx.user_data['dw']} — {fmt(amt)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"4️⃣  <b>{q[0].upper()+q[1:]}</b>\n\n"
        f"Misol: <i>Karim, Do'stim, Aka...</i>",
        parse_mode="HTML",
        reply_markup=kb_skip("⏩ Ismni yozmaslik")
    )
    return ST_DEBT_PERSON

async def debt_person_txt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["dp"] = update.message.text.strip()
    return await _ask_debt_days(update.message, ctx, edit=False)

async def debt_person_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["dp"] = ""
    return await _ask_debt_days(q.message, ctx, edit=True)

async def _ask_debt_days(msg, ctx, edit=False):
    q = "qaytarishi" if ctx.user_data["dt"] == "debt_out" else "qaytarishingiz"
    text = (
        f"🤝 <b>QARZ</b>: {ctx.user_data['dw']} — {fmt(ctx.user_data['da'])}\n"
        + (f"   Kim: <b>{ctx.user_data['dp']}</b>\n" if ctx.user_data.get('dp') else "") +
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"5️⃣  <b>Necha kunda {q} kerak?</b>\n\n"
        f"Misol: <i>5</i>  yoki  <i>14</i>  (kun soni kiriting)"
    )
    fn = msg.edit_text if edit else msg.reply_text
    await fn(text, parse_mode="HTML", reply_markup=kb_skip("⏩ Muddat belgilashmaslik"))
    return ST_DEBT_DAYS

async def debt_days_txt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = re.sub(r"[^\d]", "", update.message.text.strip())
    try: ctx.user_data["dd"] = int(txt)
    except: ctx.user_data["dd"] = 0
    return await _ask_debt_note(update.message, ctx, edit=False)

async def debt_days_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["dd"] = 0
    return await _ask_debt_note(q.message, ctx, edit=True)

async def _ask_debt_note(msg, ctx, edit=False):
    days = ctx.user_data.get("dd", 0)
    deadline_txt = f"\n   Muddat: <b>{(date.today()+timedelta(days=days)).isoformat()}</b>" if days > 0 else ""
    text = (
        f"🤝 <b>QARZ</b>: {ctx.user_data['dw']} — {fmt(ctx.user_data['da'])}\n"
        + (f"   Kim: <b>{ctx.user_data['dp']}</b>\n" if ctx.user_data.get('dp') else "") +
        deadline_txt + "\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"6️⃣  <b>Qo'shimcha izoh?</b> (ixtiyoriy)"
    )
    fn = msg.edit_text if edit else msg.reply_text
    await fn(text, parse_mode="HTML", reply_markup=kb_skip("⏩ Izoqsiz saqlash"))
    return ST_DEBT_NOTE

async def debt_note_txt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_debt(update.message, ctx, update.message.text.strip(), edit=False)

async def debt_note_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    return await _save_debt(q.message, ctx, "", edit=True)

async def _save_debt(msg, ctx, note, edit=False):
    user = ctx.user_data["user"]
    db   = load_db()
    d    = add_debt(db, user["id"], ctx.user_data["dt"],
                    ctx.user_data["dw"], ctx.user_data["da"],
                    ctx.user_data.get("dp",""), ctx.user_data.get("dd",0), note)
    lbl  = "🤝 Men BERDIM" if d["type"]=="debt_out" else "💰 Men OLDIM"
    dl   = f"\n📅 Muddat: <b>{d['deadline']}</b>" if d.get("deadline") else ""
    per  = f"\n👤 Kim: <b>{d['person']}</b>" if d.get("person") else ""
    text = (
        f"✅ <b>QARZ SAQLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 Tur:         <b>{lbl}</b>\n"
        f"📝 Nima uchun:  <b>{d['description']}</b>\n"
        f"💵 Summa:       <b>{fmt(d['amount'])}</b>"
        f"{per}{dl}\n"
        f"📅 Sana:        <b>{d['date']}</b>\n"
        + (f"📎 Izoh:        <i>{note}</i>\n" if note else "") +
        f"\n🌐 Saytda ham ko'rinadi!"
    )
    fn = msg.edit_text if edit else msg.reply_text
    await fn(text, parse_mode="HTML", reply_markup=kb_main())
    log.info(f"Qarz: {user['username']} | {d['type']} | {d['amount']}")
    return ST_MAIN

# ═══════════════════════════════════════════════════
# KO'RSATISH FUNKSIYALARI
# ═══════════════════════════════════════════════════
async def show_dashboard(msg, ctx):
    user = ctx.user_data["user"]
    db   = load_db()
    exps  = get_expenses(db, user["id"])
    debts = get_debts(db, user["id"])
    td = today(); mo = td[:7]

    t_today = sum(e["amount"] for e in exps if e.get("date") == td)
    t_month = sum(e["amount"] for e in exps if e.get("date","").startswith(mo))
    t_all   = sum(e["amount"] for e in exps)
    d_out   = [(d["description"], d["amount"]) for d in debts if not d.get("paid") and d.get("type")=="debt_out"]
    d_in    = [(d["description"], d["amount"]) for d in debts if not d.get("paid") and d.get("type")=="debt_in"]
    overdue = [d for d in debts if not d.get("paid") and d.get("deadline") and
               date.fromisoformat(d["deadline"]) < date.today()]

    cats = {}
    for e in exps: cats[e.get("category","other")] = cats.get(e.get("category","other"),0)+e["amount"]
    top = sorted(cats.items(), key=lambda x:-x[1])[:3]
    top_txt = "\n".join(f"   {CAT_DICT.get(c,('📌','Boshqa'))[0]} {CAT_DICT.get(c,('📌','Boshqa'))[1]}: {fmt(v)}" for c,v in top) or "   Hali ma'lumot yo'q"

    await msg.edit_text(
        f"📊 <b>DASHBOARD — {user['displayName']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💸 <b>Xarajatlar:</b>\n"
        f"   📆 Bugun:  <b>{fmt(t_today)}</b>\n"
        f"   🗓 Bu oy:  <b>{fmt(t_month)}</b>\n"
        f"   📋 Jami:   <b>{fmt(t_all)}</b>  ({len(exps)} ta)\n\n"
        f"🤝 <b>Qarzlar (ochiq):</b>\n"
        f"   📤 Berganlarim:  <b>{fmt(sum(x[1] for x in d_out))}</b>  ({len(d_out)} ta)\n"
        f"   📥 Olganlarim:   <b>{fmt(sum(x[1] for x in d_in))}</b>  ({len(d_in)} ta)\n"
        + (f"\n⚠️ <b>Muddati o'tgan:</b> {len(overdue)} ta qarz!\n" if overdue else "") +
        f"\n🏆 <b>Top kategoriyalar:</b>\n{top_txt}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_exp_list(msg, ctx):
    user = ctx.user_data["user"]
    db   = load_db()
    exps = get_expenses(db, user["id"])[:15]
    if not exps:
        await msg.edit_text("📋 <b>Xarajatlar</b>\n\nHali xarajat yo'q.", parse_mode="HTML", reply_markup=kb_main())
        return
    lines = ""
    for e in exps:
        cat = CAT_DICT.get(e.get("category","other"),("📌","Boshqa"))
        lines += f"  {cat[0]} <b>{e['description']}</b> — {fmt(e['amount'])}  <i>({e.get('date','')})</i>\n"
    await msg.edit_text(
        f"📋 <b>Xarajatlar ({len(exps)} ta oxirgisi)</b>\n━━━━━━━━━━━━━━━━━━━\n{lines}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_debt_list(msg, ctx):
    user  = ctx.user_data["user"]
    db    = load_db()
    debts = get_debts(db, user["id"])[:15]
    if not debts:
        await msg.edit_text("📋 <b>Qarzlar</b>\n\nHali qarz yo'q.", parse_mode="HTML", reply_markup=kb_main())
        return
    lines = ""
    for d in debts:
        ico = "📤" if d.get("type")=="debt_out" else "📥"
        st  = "✅" if d.get("paid") else "⏳"
        per = f" · {d['person']}" if d.get("person") else ""
        dl  = f" · Muddat: {d['deadline']}" if d.get("deadline") and not d.get("paid") else ""
        lines += f"  {ico}{st} <b>{d['description']}</b>{per} — {fmt(d['amount'])}{dl}\n"
    await msg.edit_text(
        f"📋 <b>Qarzlar ({len(debts)} ta oxirgisi)</b>\n━━━━━━━━━━━━━━━━━━━\n{lines}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_notifs(msg, ctx):
    user  = ctx.user_data["user"]
    db    = load_db()
    debts = get_debts(db, user["id"])
    alerts = []
    for d in debts:
        if d.get("paid") or not d.get("deadline"): continue
        try: diff = (date.fromisoformat(d["deadline"]) - date.today()).days
        except: continue
        if diff < 0:   alerts.append(f"🚨 <b>{d['description']}</b> — {fmt(d['amount'])} — {abs(diff)} kun <b>kechikdi!</b>")
        elif diff == 0: alerts.append(f"⚠️ <b>{d['description']}</b> — {fmt(d['amount'])} — <b>Bugun muddat!</b>")
        elif diff <= 3: alerts.append(f"📅 <b>{d['description']}</b> — {fmt(d['amount'])} — {diff} kun qoldi")
    txt = "🔔 <b>BILDIRISHNOMALAR</b>\n━━━━━━━━━━━━━━━━━━━\n"
    txt += ("\n".join(alerts) if alerts else "✅ Hozircha hamma narsa tartibda!")
    await msg.edit_text(txt, parse_mode="HTML", reply_markup=kb_main())

async def show_goals(msg, ctx):
    user = ctx.user_data["user"]
    db   = load_db()
    goals = db.get(user["id"]+"_goals", [])
    if not goals:
        await msg.edit_text(
            "🎯 <b>MAQSADLAR (Kopilka)</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
            "Hali maqsad yo'q.\n🌐 Saytda maqsad qo'shing — bu yerda ko'rinadi.",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return
    lines = ""
    for g in goals:
        saved  = g.get("saved", 0)
        target = g.get("target", 1)
        pct    = min(int(saved/target*100), 100)
        bar    = "█"*int(pct/10) + "░"*(10-int(pct/10))
        lines += f"\n🎯 <b>{g['name']}</b>\n   {bar} {pct}%\n   {fmt(saved)} / {fmt(target)}\n"
    await msg.edit_text(
        f"🎯 <b>MAQSADLAR</b>\n━━━━━━━━━━━━━━━━━━━{lines}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_wallets(msg, ctx):
    user    = ctx.user_data["user"]
    db      = load_db()
    wallets = db.get(user["id"]+"_wallets", [])
    if not wallets:
        await msg.edit_text(
            "💳 <b>HAMYONLAR</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
            "Hali hamyon yo'q.\n🌐 Saytda hamyon qo'shing — bu yerda ko'rinadi.",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return
    total = sum(w.get("balance",0) for w in wallets)
    lines = ""
    for w in wallets:
        lines += f"\n  💳 <b>{w.get('name','Hamyon')}</b>: {fmt(w.get('balance',0))}\n"
    await msg.edit_text(
        f"💳 <b>HAMYONLAR</b>\n━━━━━━━━━━━━━━━━━━━{lines}\n"
        f"━━━━━━━━━━━━━━━━━━━\n💰 Jami balans: <b>{fmt(total)}</b>",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_analytics(msg, ctx):
    user = ctx.user_data["user"]
    db   = load_db()
    exps = get_expenses(db, user["id"])
    if not exps:
        await msg.edit_text(
            "📈 <b>ANALITIKA</b>\n━━━━━━━━━━━━━━━━━━━\n\nHali ma'lumot yo'q.",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return
    cats = {}
    for e in exps: cats[e.get("category","other")] = cats.get(e.get("category","other"),0)+e["amount"]
    total = sum(cats.values()) or 1
    lines = ""
    for c,v in sorted(cats.items(), key=lambda x:-x[1]):
        pct = int(v/total*100)
        bar = "█"*int(pct/5) + "░"*(20-int(pct/5))
        cat = CAT_DICT.get(c,("📌","Boshqa"))
        lines += f"\n  {cat[0]} <b>{cat[1]}</b>: {pct}%\n  {bar}\n  {fmt(v)}\n"
    # Oylik
    monthly = {}
    for e in exps:
        mo = e.get("date","")[:7]
        if mo: monthly[mo] = monthly.get(mo,0)+e["amount"]
    mo_lines = "\n".join(f"  📅 {m}: {fmt(v)}" for m,v in sorted(monthly.items())[-3:])
    await msg.edit_text(
        f"📈 <b>ANALITIKA</b>\n━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Jami xarajat: <b>{fmt(total)}</b>  ({len(exps)} ta)\n\n"
        f"🏷 <b>Kategoriyalar:</b>{lines}\n"
        f"📅 <b>Oxirgi oylar:</b>\n{mo_lines}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_split(msg, ctx):
    user   = ctx.user_data["user"]
    db     = load_db()
    splits = db.get(user["id"]+"_splits", [])
    if not splits:
        await msg.edit_text(
            "👥 <b>GURUH BO'LISH</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
            "Hali guruh bo'lish yo'q.\n🌐 Saytda yarating — bu yerda ko'rinadi.",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return
    lines = ""
    for s in splits[:5]:
        paid = sum(1 for p in s.get("persons",[]) if p.get("paid"))
        tot  = len(s.get("persons",[]))
        lines += f"\n  👥 <b>{s.get('title','')}</b> — {fmt(s.get('total',0))}\n  {paid}/{tot} to'ladi\n"
    await msg.edit_text(
        f"👥 <b>GURUH BO'LISH</b>\n━━━━━━━━━━━━━━━━━━━{lines}",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def show_settings(msg, ctx):
    user = ctx.user_data["user"]
    db   = load_db()
    exp_c  = len(get_expenses(db, user["id"]))
    debt_c = len(get_debts(db, user["id"]))
    await msg.edit_text(
        f"⚙️ <b>SOZLAMALAR</b>\n━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Foydalanuvchi: <b>{user['displayName']}</b>\n"
        f"🔑 Username: <code>{user['username']}</code>\n\n"
        f"📊 Ma'lumotlar:\n"
        f"   💸 Xarajatlar: <b>{exp_c} ta</b>\n"
        f"   🤝 Qarzlar: <b>{debt_c} ta</b>\n\n"
        f"🌐 <b>Sayt bilan sinxron:</b> Ha ✅\n"
        f"   saytda ham shu akkount bilan kiring",
        parse_mode="HTML", reply_markup=kb_main()
    )

# ═══════════════════════════════════════════════════
# CANCEL
# ═══════════════════════════════════════════════════
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Bekor qilindi.\n/start — qayta boshlash"
    )
    ctx.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
def main():
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ST_AUTH_CHOOSE: [
                CallbackQueryHandler(on_auth_btn, pattern="^(do_login|do_reg)$"),
            ],
            ST_REG_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_user)],
            ST_REG_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_pass)],
            ST_REG_PASS2:[MessageHandler(filters.TEXT & ~filters.COMMAND, reg_pass2)],
            ST_LOG_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_user)],
            ST_LOG_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, log_pass),
                CallbackQueryHandler(on_main, pattern="^(retry_login|restart)$"),
            ],
            ST_MAIN: [CallbackQueryHandler(on_main)],

            # Xarajat
            ST_EXP_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, exp_name)],
            ST_EXP_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_amt)],
            ST_EXP_CAT: [CallbackQueryHandler(exp_cat, pattern="^cat_")],
            ST_EXP_NOTE:[
                CallbackQueryHandler(exp_note_skip, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, exp_note_txt),
            ],

            # Qarz
            ST_DEBT_TYPE:  [CallbackQueryHandler(debt_type, pattern="^dt_")],
            ST_DEBT_WHY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_why)],
            ST_DEBT_AMT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amt)],
            ST_DEBT_PERSON:[
                CallbackQueryHandler(debt_person_skip, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_person_txt),
            ],
            ST_DEBT_DAYS:  [
                CallbackQueryHandler(debt_days_skip, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_days_txt),
            ],
            ST_DEBT_NOTE:  [
                CallbackQueryHandler(debt_note_skip, pattern="^skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_note_txt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start",  cmd_start),
            CallbackQueryHandler(on_main, pattern="^back$"),
        ],
        allow_reentry=True,
        per_chat=True,
    )

    app.add_handler(conv)

    log.info("=" * 52)
    log.info("🚀  FinApp Telegram Bot ishga tushdi!")
    log.info(f"📁  DB fayl: {DB_FILE}")
    log.info("=" * 52)

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
