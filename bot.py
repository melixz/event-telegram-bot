import os
import asyncio
from datetime import datetime, date
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from dotenv import load_dotenv
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_user, add_user, update_user, get_all_user_ids, init_db
from messages import (
    START_MESSAGE,
    GREETING_OPTIONS,
    GREETING_MESSAGES,
    THANK_YOU_MESSAGE,
    FINAL_MESSAGE,
    REMINDER_MESSAGE,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_API_TOKEN")

REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", 10))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", 0))

# Даты проведения при необходимости корректируйте
EVENT_START = datetime(2024, 12, 16)
EVENT_END = datetime(2024, 12, 20)
TOTAL_DAYS = 5

IMAGE_URL = "NY_3.png"  # Укажите корректный путь к вашему изображению


def get_current_day_number():
    today = date.today()
    start_date = EVENT_START.date()
    if today < start_date:
        return 0
    delta = (today - start_date).days + 1
    if delta > TOTAL_DAYS:
        delta = TOTAL_DAYS
    return delta


def get_allowed_greetings_count():
    current_day_number = get_current_day_number()
    return min(current_day_number, TOTAL_DAYS)


def get_available_greetings_for_user(user_id):
    user = get_user(user_id)
    if not user:
        return list(enumerate(GREETING_OPTIONS))

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]

    available = [
        (i, GREETING_OPTIONS[i])
        for i in range(len(GREETING_OPTIONS))
        if i not in selected_indices
    ]
    return available


async def show_greetings_menu(user_id, application):
    user = get_user(user_id)
    if not user:
        add_user(user_id)
        user = get_user(user_id)

    allowed_count = get_allowed_greetings_count()
    if allowed_count == 0:
        await application.bot.send_message(
            chat_id=user_id,
            text="Событие ещё не началось. Подождите начала мероприятия.",
        )
        return

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]
    chosen_count = len(selected_indices)

    if chosen_count >= allowed_count:
        if chosen_count < TOTAL_DAYS:
            await application.bot.send_message(chat_id=user_id, text=THANK_YOU_MESSAGE)
        else:
            await application.bot.send_message(chat_id=user_id, text=FINAL_MESSAGE)
        return

    available = get_available_greetings_for_user(user_id)
    if not available:
        await application.bot.send_message(chat_id=user_id, text=FINAL_MESSAGE)
        return

    keyboard = [
        [InlineKeyboardButton(text=f"{i + 1} 🎁", callback_data=f"greeting_{idx}")]
        for i, (idx, text) in enumerate(available)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if chosen_count == 0:
        with open(IMAGE_URL, "rb") as photo:
            await application.bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=START_MESSAGE,
                reply_markup=reply_markup,
            )
    else:
        await application.bot.send_message(
            chat_id=user_id,
            text="Выбери пожелание на сегодня:",
            reply_markup=reply_markup,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await show_greetings_menu(user_id, context.application)


async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    callback_data = query.data

    if callback_data == "show_greetings":
        await show_greetings_menu(user_id, context.application)
        return

    if not callback_data.startswith("greeting_"):
        return

    user = get_user(user_id)
    if not user:
        add_user(user_id)
        user = get_user(user_id)

    allowed_count = get_allowed_greetings_count()
    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]
    chosen_count = len(selected_indices)

    if chosen_count >= allowed_count:
        await query.message.reply_text(
            "Вы уже выбрали все доступные на сегодня пожелания."
        )
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    selected_index = int(callback_data.split("_")[1])

    if selected_index in selected_indices:
        if query.message.text:
            await query.edit_message_text("Это пожелание уже было выбрано ранее.")
        else:
            await query.message.reply_text("Это пожелание уже было выбрано ранее.")
        return

    selected_indices.append(selected_index)
    new_selected_str = ",".join(str(i) for i in selected_indices)

    today_str = date.today().isoformat()
    update_user(user_id, new_selected_str, today_str)

    greeting_text = GREETING_MESSAGES[selected_index]

    if query.message.text:
        await query.edit_message_text(greeting_text)
    else:
        await query.message.reply_text(greeting_text)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    chosen_count = len(selected_indices)
    if chosen_count < allowed_count:
        await show_greetings_menu(user_id, context.application)
    else:
        if chosen_count < TOTAL_DAYS:
            await query.message.reply_text(THANK_YOU_MESSAGE)
        else:
            await query.message.reply_text(FINAL_MESSAGE)


async def send_message_to_all_users(application, text):
    user_ids = get_all_user_ids()
    for uid in user_ids:
        allowed_count = get_allowed_greetings_count()
        user = get_user(uid)
        selected_str = user["selected_greetings"] if user else ""
        selected_indices = [
            int(x) for x in selected_str.strip().split(",") if x.isdigit()
        ]
        chosen_count = len(selected_indices)
        available = get_available_greetings_for_user(uid)

        if chosen_count < allowed_count and available:
            try:
                await application.bot.send_message(chat_id=uid, text=REMINDER_MESSAGE)
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "Показать пожелания", callback_data="show_greetings"
                        )
                    ]
                ]
                await application.bot.send_message(
                    chat_id=uid,
                    text="Нажмите на кнопку, чтобы выбрать пожелания:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            except Exception as e:
                print(f"Ошибка отправки сообщения пользователю {uid}: {e}")


def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_inline_selection))

    async def send_daily_reminder():
        await send_message_to_all_users(
            application, "Новый день - новое пожелание! Скорее забирай🤗"
        )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def job_wrapper():
        asyncio.run_coroutine_threadsafe(send_daily_reminder(), loop)

    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(
        job_wrapper,
        CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE),
    )
    scheduler.start()

    application.run_polling()


if __name__ == "__main__":
    main()
