import os
import sqlite3
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6719518185 # ← вставь СВОЙ Telegram ID
DB_FILE = "bot.db"

bot = telebot.TeleBot(TOKEN)

# uid -> message_id главного меню
menu_messages = {}

# uid -> временные данные (для вывода и т.п.)
temp = {}

# ============================================================
# БАЗА ДАННЫХ
# ============================================================
def db_init():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            status TEXT DEFAULT 'answering',
            experience TEXT,
            source TEXT,
            profit TEXT,
            balance REAL DEFAULT 0,
            step TEXT DEFAULT 'experience',
            wallet TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,
            amount REAL,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def db_get(uid):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""SELECT uid, name, username, status, experience, source, profit,
                   balance, step, wallet FROM users WHERE uid = ?""", (uid,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "uid": row[0], "name": row[1], "username": row[2], "status": row[3],
        "experience": row[4], "source": row[5], "profit": row[6],
        "balance": row[7], "step": row[8], "wallet": row[9]
    }

def db_create(uid, name, username):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (uid, name, username, status, step) VALUES (?, ?, ?, 'answering', 'experience')",
        (uid, name, username)
    )
    conn.commit()
    conn.close()

def db_update(uid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [uid]
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {cols} WHERE uid = ?", vals)
    conn.commit()
    conn.close()

def db_all():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT uid, name, username, status, balance FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows

db_init()

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def delete_msg(chat_id, message_id):
    """Тихо удаляем сообщение, если получится"""
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def clear_previous_menu(uid):
    """Удаляем предыдущее сообщение главного меню (если было)"""
    prev = menu_messages.get(uid)
    if prev:
        delete_msg(uid, prev)
        menu_messages.pop(uid, None)

def delete_user_messages(uid, message_id):
    """Удаляем сообщения пользователя (в личке можно)"""
    delete_msg(uid, message_id)

# ============================================================
# КЛАВИАТУРЫ
# ============================================================
def bottom_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    kb.add(types.KeyboardButton("📋 Главное меню"))
    return kb

def main_menu_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💰 Баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("📚 Материалы", callback_data="menu_materials"),
        types.InlineKeyboardButton("🎓 Направления", callback_data="menu_directions")
    )
    return kb

def yes_no_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("Да"), types.KeyboardButton("Нет"))
    return kb

def admin_kb(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{uid}")
    )
    return kb

# ============================================================
# ОТПРАВКА ГЛАВНОГО МЕНЮ (с очисткой предыдущего)
# ============================================================
def send_main_menu(uid, message_id_to_delete=None):
    # 1. Удаляем предыдущее меню
    clear_previous_menu(uid)

    # 2. Удаляем сообщение пользователя (кнопку "Главное меню")
    if message_id_to_delete:
        delete_user_messages(uid, message_id_to_delete)

    # 3. Отправляем новое меню
    sent = bot.send_message(
        uid,
        "🏠 <b>Главное меню</b>\n\nВыбери раздел:",
        parse_mode="HTML",
        reply_markup=main_menu_inline()
    )
    menu_messages[uid] = sent.message_id

# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    u = message.from_user

    db_create(uid, u.first_name, u.username or "")
    db_update(uid, name=u.first_name, username=u.username or "")

    user = db_get(uid)

    if user["status"] == "approved":
        bot.send_message(uid, "Ты уже одобрен ✅", reply_markup=bottom_kb())
        send_main_menu(uid)
        return
    if user["status"] == "pending":
        bot.send_message(uid, "Твоя заявка на рассмотрении ⏳")
        return
    if user["status"] == "rejected":
        bot.send_message(uid, "Твоя заявка была отклонена ❌")
        return

    db_update(uid, status="answering", step="experience")
    bot.send_message(uid,
        "Привет! Ответь на несколько вопросов.\n\n1️⃣ Есть ли опыт в работе?",
        reply_markup=yes_no_kb())

# ============================================================
# АНКЕТА
# ============================================================
@bot.message_handler(func=lambda m: (db_get(m.chat.id) or {}).get("status") == "answering")
def handle_answer(message):
    uid = message.chat.id
    user = db_get(uid)
    step = user["step"]
    text = message.text or ""

    if step == "experience":
        if text not in ("Да", "Нет"):
            bot.send_message(uid, "Выбери: Да или Нет", reply_markup=yes_no_kb())
            return
        db_update(uid, experience=text, step="source")
        bot.send_message(uid, "2️⃣ Откуда узнал о нас?", reply_markup=types.ReplyKeyboardRemove())
        return

    if step == "source":
        db_update(uid, source=text, step="profit")
        bot.send_message(uid, "3️⃣ Сколько у тебя профитов?")
        return

    if step == "profit":
        db_update(uid, profit=text, status="pending")
        bot.send_message(uid, "Спасибо! Заявка отправлена на рассмотрение ⏳",
                         reply_markup=types.ReplyKeyboardRemove())

        u = db_get(uid)
        report = (
            "📥 <b>Новая заявка</b>\n\n"
            f"👤 Имя: {u['name']}\n"
            f"🔗 Username: @{u['username'] or 'нет'}\n"
            f"🆔 ID: <code>{uid}</code>\n\n"
            f"1. Опыт: {u['experience']}\n"
            f"2. Откуда узнал: {u['source']}\n"
            f"3. Профитов: {u['profit']}"
        )
        bot.send_message(ADMIN_ID, report, parse_mode="HTML", reply_markup=admin_kb(uid))
        return

# ============================================================
# ОДОБРИТЬ / ОТКЛОНИТЬ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    action, uid_str = call.data.split("_", 1)
    uid = int(uid_str)

    if action == "approve":
        db_update(uid, status="approved")

        try:
            bot.send_message(
                uid,
                "🎉 <b>Твоя заявка одобрена!</b>\n\nДобро пожаловать 👇",
                parse_mode="HTML",
                reply_markup=bottom_kb()
            )
        except Exception as e:
            print("Ошибка отправки:", e)

        try:
            send_main_menu(uid)
        except Exception as e:
            print("Ошибка меню:", e)

        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Одобрено ✅")
    else:
        db_update(uid, status="rejected")
        try:
            bot.send_message(uid, "😔 К сожалению, заявка отклонена.")
        except Exception as e:
            print("Ошибка:", e)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Отклонено ❌")

# ============================================================
# КНОПКА "📋 Главное меню" — чистит всё и показывает меню заново
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📋 Главное меню" and (db_get(m.chat.id) or {}).get("status") == "approved")
def bottom_menu_button(message):
    # Удаляем сообщение пользователя ("Главное меню") + предыдущее меню
    send_main_menu(message.chat.id, message_id_to_delete=message.message_id)

# ============================================================
# ИНЛАЙН-КНОПКИ ГЛАВНОГО МЕНЮ
# ============================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def menu_actions(call):
    uid = call.from_user.id
    u = db_get(uid)
    if not u or u["status"] != "approved":
        bot.answer_callback_query(call.id, "Нет доступа")
        return

    action = call.data.replace("menu_", "")

    # Удаляем старое меню, чтобы не копились
    clear_previous_menu(uid)

    if action == "balance":
        sent = bot.send_message(uid,
            f"💰 <b>Твой баланс:</b> <b>{u['balance']}$</b>",
            parse_mode="HTML",
            reply_markup=main_menu_inline())
        menu_messages[uid] = sent.message_id
        bot.answer_callback_query(call.id)

    elif action == "profile":
        sent = bot.send_message(uid,
            f"👤 <b>Твой профиль</b>\n\n"
            f"Имя: {u['name']}\n"
            f"Username: @{u['username'] or 'нет'}\n"
            f"ID: <code>{uid}</code>\n"
            f"💰 Баланс: <b>{u['balance']}$</b>",
            parse_mode="HTML",
            reply_markup=main_menu_inline())
        menu_messages[uid] = sent.message_id
        bot.answer_callback_query(call.id)

    elif action == "materials":
        sent = bot.send_message(uid,
            "📚 <b>Материалы</b>\n\n"
            "1. Гайд для новичков\n"
            "2. Видео-уроки\n"
            "3. Шаблоны и чек-листы\n"
            "4. Полезные ссылки",
            parse_mode="HTML",
            reply_markup=main_menu_inline())
        menu_messages[uid] = sent.message_id
        bot.answer_callback_query(call.id)

    elif action == "directions":
        sent = bot.send_message(uid,
            "🎓 <b>Направления</b>\n\n"
            "1. Программирование\n"
            "2. Дизайн\n"
            "3. Маркетинг\n"
            "4. Аналитика данных",
            parse_mode="HTML",
            reply_markup=main_menu_inline())
        menu_messages[uid] = sent.message_id
        bot.answer_callback_query(call.id)

# ============================================================
# КОМАНДЫ АДМИНА
# ============================================================
@bot.message_handler(commands=['list'])
def admin_list(message):
    if message.chat.id != ADMIN_ID:
        return
    rows = db_all()
    if not rows:
        bot.send_message(ADMIN_ID, "Пока нет пользователей.")
        return

    lines = ["📋 <b>Все пользователи:</b>\n"]
    for uid, name, username, status, bal in rows:
        icon = {"approved": "✅", "pending": "⏳", "rejected": "❌", "answering": "✏️"}.get(status, "•")
        lines.append(f"{icon} <b>{name}</b> (@{username or '—'}) | ID: <code>{uid}</code> | 💰 {bal}$")
    bot.send_message(ADMIN_ID, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.text and m.text.lower().startswith("balance "))
def admin_check_balance(message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(ADMIN_ID, "❌ Формат: <code>balance 123456789</code>", parse_mode="HTML")
        return

    uid = int(parts[1])
    u = db_get(uid)
    if not u:
        bot.send_message(ADMIN_ID, f"❌ Пользователь <code>{uid}</code> не найден.", parse_mode="HTML")
        return

    bot.send_message(ADMIN_ID,
        f"👤 <b>Пользователь</b>\n\n"
        f"Имя: {u['name']}\n"
        f"Username: @{u['username'] or 'нет'}\n"
        f"ID: <code>{uid}</code>\n"
        f"Статус: {u['status']}\n"
        f"💰 Баланс: <b>{u['balance']}$</b>",
        parse_mode="HTML")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.text and len(m.text.split()) == 2)
def admin_topup(message):
    parts = message.text.split()
    amount_str = parts[0].replace("$", "")
    uid_str = parts[1]

    if not uid_str.isdigit():
        return
    try:
        amount = float(amount_str)
    except:
        return

    uid = int(uid_str)
    u = db_get(uid)
    if not u:
        bot.send_message(ADMIN_ID, f"❌ Пользователь <code>{uid}</code> не найден.", parse_mode="HTML")
        return

    new_bal = u["balance"] + amount
    db_update(uid, balance=new_bal)

    bot.send_message(ADMIN_ID,
        f"✅ Баланс изменён\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"💵 {'+' if amount >= 0 else ''}{amount}$\n"
        f"💰 Новый баланс: <b>{new_bal}$</b>",
        parse_mode="HTML")

    try:
        if amount >= 0:
            text = f"💰 Баланс пополнен на <b>{amount}$</b>\nТекущий: <b>{new_bal}$</b>"
        else:
            text = f"💸 Списано <b>{abs(amount)}$</b>\nТекущий: <b>{new_bal}$</b>"
        bot.send_message(uid, text, parse_mode="HTML", reply_markup=bottom_kb())
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ Не смог уведомить: {e}")

# ============================================================
# FALLBACK
# ============================================================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    uid = message.chat.id
    u = db_get(uid)

    if u and u["status"] == "approved":
        # Стираем сообщение пользователя и показываем меню заново
        delete_user_messages(uid, message.message_id)
        send_main_menu(uid)
    elif u and u["status"] == "pending":
        bot.send_message(uid, "Заявка на рассмотрении ⏳")
    elif u and u["status"] == "rejected":
        bot.send_message(uid, "Заявка отклонена ❌")
    elif uid == ADMIN_ID:
        bot.send_message(ADMIN_ID,
            "🔧 <b>Команды админа:</b>\n\n"
            "➕ <code>20 123456789</code> — пополнить\n"
            "➖ <code>-20 123456789</code> — списать\n"
            "🔍 <code>balance 123456789</code> — баланс\n"
            "📋 <code>/list</code> — все пользователи",
            parse_mode="HTML")
    else:
        bot.send_message(uid, "Напиши /start, чтобы начать.")

# ============================================================
# ЗАПУСК
# ============================================================
print("Бот запущен...")
bot.polling(none_stop=True)