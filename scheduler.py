from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import pytz
import os

REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", 10))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", 0))


def start_scheduler(application, send_message_to_all_users):
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))

    async def send_daily_reminder():
        """
        Асинхронное напоминание пользователям.
        """
        await send_message_to_all_users(
            application, "Новый день - новое пожелание! Скорее забирай🤗"
        )

    def job_wrapper():
        """
        Обертка для вызова асинхронной функции через asyncio.
        """
        asyncio.get_event_loop().create_task(send_daily_reminder())

    # Планировщик задачи, ежедневно в указанное время (по умолчанию в 10:00 по Москве)
    scheduler.add_job(
        job_wrapper,  # Вызываем обертку, чтобы запустить асинхронную задачу
        CronTrigger(hour=REMINDER_HOUR, minute=REMINDER_MINUTE),
    )
    scheduler.start()
