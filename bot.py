import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- Клавиатура с двумя кнопками ---
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_profile = types.KeyboardButton("👤 Профиль")
    btn_directions = types.KeyboardButton("📚 Направления")
    kb.add(btn_profile, btn_directions)
    return kb

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        f"Привет, {message.from_user.first_name}!\nВыбери пункт меню:",
        reply_markup=main_keyboard()
    )

# --- Кнопка "Профиль" ---
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = message.from_user
    text = (
        "👤 <b>Твой профиль</b>\n\n"
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username if user.username else 'нет'}\n"
        f"ID: <code>{user.id}</code>"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# --- Кнопка "Направления" ---
@bot.message_handler(func=lambda m: m.text == "📚 Направления")
def directions(message):
    text = (
        "📚 <b>Наши направления:</b>\n\n"
        "1. Программирование\n"
        "2. Дизайн\n"
        "3. Маркетинг\n"
        "4. Аналитика данных"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# --- Ответ на любой другой текст ---
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(
        message.chat.id,
        "Пожалуйста, выбери пункт из меню 👇",
        reply_markup=main_keyboard()
    )

bot.polling(none_stop=True)