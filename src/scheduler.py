import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import discord

from src import config
from src.jira_client import JiraClient
from src.notifier import send_reminders

logger = logging.getLogger(__name__)


async def run_reminder(bot: discord.Client) -> None:
    logger.info("Đang lấy dữ liệu từ Jira...")
    try:
        jira = JiraClient()
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(None, jira.get_active_sprint_issues)
        logger.info(f"Tìm thấy {len(issues)} issue cần nhắc.")
        await send_reminders(bot, issues)
    except Exception:
        logger.exception("Lỗi khi chạy reminder")


def setup_scheduler(bot: discord.Client) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_reminder,
        trigger=CronTrigger(
            hour=config.REMIND_CRON_HOUR,
            minute=config.REMIND_CRON_MINUTE,
            day_of_week="mon-fri",
        ),
        args=[bot],
        id="jira_reminder",
        name="Jira Daily Reminder",
        replace_existing=True,
    )
    return scheduler
