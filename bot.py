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

# URL или путь к изображению
IMAGE_URL = "/home/vlad/PycharmProjects/event-telegram-bot/NY_3.png"


def get_available_greetings_for_user(user_id):
    """
    Возвращает список доступных пожеланий для пользователя.
    """
    user = get_user(user_id)
    if not user:
        return GREETING_OPTIONS

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]

    available = [
        GREETING_OPTIONS[i]
        for i in range(len(GREETING_OPTIONS))
        if i not in selected_indices
    ]
    return available


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Стартовая команда, отображает доступные пожелания.
    """
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if not user:
        add_user(user_id)

    available = get_available_greetings_for_user(user_id)

    if not available:
        await update.message.reply_text(FINAL_MESSAGE)
        return

    # Создаем инлайн-кнопки
    keyboard = [
        [InlineKeyboardButton(text=f"{i + 1} 🎁", callback_data=f"greeting_{i}")]
        for i, option in enumerate(available)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем изображение и стартовое сообщение
    with open(IMAGE_URL, "rb") as photo:
        await context.bot.send_photo(
            chat_id=update.message.chat_id,
            photo=photo,
            caption=START_MESSAGE,
            reply_markup=reply_markup,
        )


async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора пожелания.
    """
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

    selected_indices.append(selected_index)
    new_selected_str = ",".join(str(i) for i in selected_indices)
    update_user(user_id, new_selected_str)

    greeting_text = GREETING_MESSAGES[selected_index]
    await query.edit_message_text(greeting_text)

    available = get_available_greetings_for_user(user_id)
    if available:
        keyboard = [
            [InlineKeyboardButton(text=f"{i + 1} 🎁", callback_data=f"greeting_{i}")]
            for i, option in enumerate(available)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            THANK_YOU_MESSAGE,
            reply_markup=reply_markup,
        )
    else:
        await query.message.reply_text(FINAL_MESSAGE)


async def send_message_to_all_users(application, text):
    """
    Ежедневное напоминание пользователям.
    """
    user_ids = get_all_user_ids()
    for uid in user_ids:
        available = get_available_greetings_for_user(uid)
        if available:
            try:
                # Отправляем напоминание
                await application.bot.send_message(chat_id=uid, text=text)
                # Автоматически вызываем старт для отображения меню
                await application.bot.send_message(chat_id=uid, text="/start")
            except Exception as e:
                print(f"Ошибка отправки сообщения пользователю {uid}: {e}")


def main():
    """
    Главная функция для запуска бота.
    """
    init_db()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_inline_selection))

    from scheduler import start_scheduler

    start_scheduler(application)

    application.run_polling()


if __name__ == "__main__":
    main()
