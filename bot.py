import os
from datetime import datetime, date
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
    REMINDER_MESSAGE,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Даты проведения при необходимости корректируйте
EVENT_START = datetime(2024, 12, 11)
EVENT_END = datetime(2024, 12, 15)
TOTAL_DAYS = 5

IMAGE_URL = "NY_3.png"  # Укажите корректный путь к вашему изображению


def get_current_day_number():
    """
    Возвращает номер текущего дня мероприятия, начиная с 1.
    Если сегодня раньше EVENT_START, возвращает 0.
    Если после EVENT_END - возвращает TOTAL_DAYS.
    """
    today = date.today()
    start_date = EVENT_START.date()
    if today < start_date:
        return 0
    delta = (today - start_date).days + 1
    if delta > TOTAL_DAYS:
        delta = TOTAL_DAYS
    return delta


def get_allowed_greetings_count():
    """
    Возвращает максимальное количество пожеланий, которое пользователь может выбрать к текущему дню.
    """
    current_day_number = get_current_day_number()
    return min(current_day_number, TOTAL_DAYS)


def get_available_greetings_for_user(user_id):
    """
    Возвращает список (index, text) доступных пожеланий для пользователя,
    учитывая уже выбранные пожелания.
    """
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
    """
    Показывает пользователю список доступных пожеланий.
    """
    user = get_user(user_id)
    if not user:
        add_user(user_id)
        user = get_user(user_id)

    allowed_count = get_allowed_greetings_count()
    if allowed_count == 0:
        # Событие еще не началось
        await application.bot.send_message(
            chat_id=user_id,
            text="Событие ещё не началось. Подождите начала мероприятия.",
        )
        return

    selected_str = user["selected_greetings"]
    selected_indices = [int(x) for x in selected_str.strip().split(",") if x.isdigit()]
    chosen_count = len(selected_indices)

    # Если пользователь уже достиг максимума доступных пожеланий на этот день или вообще
    if chosen_count >= allowed_count:
        if chosen_count < TOTAL_DAYS:
            # Еще будут дни впереди
            await application.bot.send_message(chat_id=user_id, text=THANK_YOU_MESSAGE)
        else:
            # Пользователь выбрал все пожелания
            await application.bot.send_message(chat_id=user_id, text=FINAL_MESSAGE)
        return

    # Иначе показываем доступные пожелания
    available = get_available_greetings_for_user(user_id)
    if not available:
        # Нет доступных пожеланий вообще
        await application.bot.send_message(chat_id=user_id, text=FINAL_MESSAGE)
        return

    keyboard = [
        [InlineKeyboardButton(text=f"{i + 1} 🎁", callback_data=f"greeting_{idx}")]
        for i, (idx, text) in enumerate(available)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    with open(IMAGE_URL, "rb") as photo:
        await application.bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=START_MESSAGE,
            reply_markup=reply_markup,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Стартовая команда, просто вызывает логику отображения меню пожеланий.
    """
    user_id = update.message.from_user.id
    await show_greetings_menu(user_id, context.application)


async def handle_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка выбора пожелания или нажатия на кнопку "Показать пожелания".
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    callback_data = query.data

    # Если пользователь нажал на специальную кнопку "show_greetings"
    if callback_data == "show_greetings":
        await show_greetings_menu(user_id, context.application)
        return

    # Проверяем, что callback действительно относится к пожеланиям
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
        # Пользователь уже выбрал максимально доступное количество пожеланий на сегодня
        await query.message.reply_text(
            "Вы уже выбрали все доступные на сегодня пожелания."
        )
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    selected_index = int(callback_data.split("_")[1])

    # Проверяем, не было ли это пожелание выбрано ранее
    if selected_index in selected_indices:
        # Это пожелание уже выбиралось ранее
        if query.message.text:
            await query.edit_message_text("Это пожелание уже было выбрано ранее.")
        else:
            await query.message.reply_text("Это пожелание уже было выбрано ранее.")
        return

    # Добавляем выбранное пожелание
    selected_indices.append(selected_index)
    new_selected_str = ",".join(str(i) for i in selected_indices)

    # Обновляем данные пользователя
    today_str = date.today().isoformat()
    update_user(user_id, new_selected_str, today_str)

    # Отправляем выбранное пожелание
    greeting_text = GREETING_MESSAGES[selected_index]

    if query.message.text:
        await query.edit_message_text(greeting_text)
    else:
        await query.message.reply_text(greeting_text)

    # Убираем клавиатуру
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Проверяем, может ли пользователь выбрать ещё
    chosen_count = len(selected_indices)
    if chosen_count < allowed_count:
        # Есть ещё возможность выбрать пожелания
        # Вместо просто текста - сразу показываем меню снова
        await show_greetings_menu(user_id, context.application)
    else:
        # Лимит на сегодня достигнут
        if chosen_count < TOTAL_DAYS:
            # Выводим сообщение без кнопки
            await query.message.reply_text(THANK_YOU_MESSAGE)
            # **Изменение здесь**: Не отправляем кнопку, если пользователь достиг лимита
        else:
            await query.message.reply_text(FINAL_MESSAGE)


async def send_message_to_all_users(application, text):
    """
    Ежедневное напоминание пользователям.
    После напоминания предлагаем кнопку для выбора пожеланий только тем,
    кто может выбрать ещё пожелания.
    """
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
                # Отправляем напоминание
                await application.bot.send_message(chat_id=uid, text=REMINDER_MESSAGE)
                # Добавим кнопку для показа пожеланий
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
        else:
            # Пользователь уже выбрал все доступные пожелания на сегодня или вообще
            # Не отправляем кнопку, но можем отправить другое сообщение, если нужно
            pass


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
