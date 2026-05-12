"""APScheduler 调度引擎 —— 定时任务管理"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config.settings import get_settings

settings = get_settings()


def create_scheduler() -> AsyncIOScheduler:
    """创建并配置调度器"""
    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
        timezone=settings.timezone,
    )
    return scheduler


def register_jobs(scheduler: AsyncIOScheduler):
    """注册所有定时任务"""
    from src.scheduler.jobs_price import check_watchlist_prices
    from src.scheduler.jobs_news import fetch_and_index_news

    scheduler.add_job(
        check_watchlist_prices,
        trigger=IntervalTrigger(hours=settings.price_check_interval_hours),
        id="price_check",
        replace_existing=True,
        name="价格巡检",
    )
    logger.info(
        f"注册任务: price_check (每 {settings.price_check_interval_hours} 小时)"
    )

    scheduler.add_job(
        fetch_and_index_news,
        trigger=IntervalTrigger(hours=settings.news_fetch_interval_hours),
        id="news_fetch",
        replace_existing=True,
        name="新闻抓取",
    )
    logger.info(
        f"注册任务: news_fetch (每 {settings.news_fetch_interval_hours} 小时)"
    )

    scheduler.add_job(
        run_cleanup,
        trigger=CronTrigger(hour=3, minute=7, timezone=settings.timezone),
        id="cleanup",
        replace_existing=True,
        name="数据清理",
    )
    logger.info("注册任务: cleanup (每天 3:07)")


async def run_cleanup():
    """数据清理任务"""
    from src.rag.retriever import delete_old_documents

    count = delete_old_documents(days=90)
    if count:
        logger.info(f"清理完成: 删除 {count} 条旧新闻向量")
    else:
        logger.info("清理完成: 无需删除")
