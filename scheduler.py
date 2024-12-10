from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from bot import send_message_to_all_users


def start_scheduler(application):
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))

    async def send_daily_reminder():
        """
        Отправляет напоминание всем пользователям.
        """
        await send_message_to_all_users(
            application, "Новый день - новое пожелание! Скорее забирай🤗"
        )

    # Планировщик задачи, ежедневно в 10:00 по Москве
    scheduler.add_job(send_daily_reminder, CronTrigger(hour=10, minute=0))
    scheduler.start()
