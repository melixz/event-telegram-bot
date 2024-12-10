import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from dotenv import load_dotenv

from database import get_user, add_user, update_user, get_all_user_ids, init_db
from messages import (
    START_MESSAGE,
    GREETING_OPTIONS,
    GREETING_MESSAGES,
    THANK_YOU_MESSAGE,
    FINAL_MESSAGE,
)

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Даты проведения
EVENT_START = datetime(2024, 12, 16)
EVENT_END = datetime(2024, 12, 20)
TOTAL_DAYS = 5  # Всего 5 поздравлений


def get_current_day_count():
    now = datetime.now()
    if now < EVENT_START:
        return 0
    delta = (now.date() - EVENT_START.date()).days
    day_count = delta + 1
    return min(day_count, TOTAL_DAYS)


def get_available_greetings_for_user(user_id):
    user = get_user(user_id)
    if not user:
        return GREETING_OPTIONS

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]

    current_day_count = get_current_day_count()

    available = []
    for i in range(current_day_count):
        if i not in selected_indices:
            available.append(GREETING_OPTIONS[i])
    return available


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        add_user(user_id)

    message = START_MESSAGE
    available = get_available_greetings_for_user(user_id)

    if len(available) == 0 and get_current_day_count() >= TOTAL_DAYS:
        await update.message.reply_text(FINAL_MESSAGE)
        return

    keyboard = [
        [InlineKeyboardButton(text=f"{i + 1} 🎁", callback_data=f"greeting_{i}")]
        for i, option in enumerate(available)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup)


async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем получение события
    user_id = query.from_user.id
    callback_data = query.data

    if not callback_data.startswith("greeting_"):
        return

    selected_index = int(callback_data.split("_")[1])

    user = get_user(user_id)
    if not user:
        add_user(user_id)
        user = get_user(user_id)

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]

    if selected_index in selected_indices:
        await query.edit_message_text("Это пожелание уже было выбрано ранее.")
        return

    current_day_count = get_current_day_count()
    if selected_index >= current_day_count:
        await query.edit_message_text("Это пожелание еще не доступно. Приходи позже!")
        return

    selected_indices.append(selected_index)
    new_selected_str = ",".join(str(i) for i in selected_indices)
    update_user(user_id, new_selected_str)

    greeting_text = GREETING_MESSAGES[selected_index]
    await query.edit_message_text(greeting_text)

    if len(selected_indices) < TOTAL_DAYS:
        await query.message.reply_text(THANK_YOU_MESSAGE)
    else:
        await query.message.reply_text(FINAL_MESSAGE)


async def send_message_to_all_users(application, text):
    user_ids = get_all_user_ids()
    for uid in user_ids:
        available = get_available_greetings_for_user(uid)
        if available:
            try:
                await application.bot.send_message(chat_id=uid, text=text)
                await application.bot.send_message(chat_id=uid, text="/start")
            except Exception as e:
                print(f"Ошибка отправки сообщения пользователю {uid}: {e}")


def main():
    init_db()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_inline_selection))

    from scheduler import start_scheduler

    start_scheduler(application)

    application.run_polling()


if __name__ == "__main__":
    main()
