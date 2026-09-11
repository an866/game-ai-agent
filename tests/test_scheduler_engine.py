"""调度器引擎 —— 任务注册数量 / id / 触发器类型，不真跑任务"""

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.scheduler.engine import create_scheduler, register_jobs


class TestCreateScheduler:
    def test_creates_asyncio_scheduler(self):
        sched = create_scheduler()
        assert sched is not None
        assert sched._job_defaults["coalesce"] is True
        assert sched._job_defaults["max_instances"] == 1
        assert sched._job_defaults["misfire_grace_time"] == 300


class TestRegisterJobs:
    def test_registers_three_jobs(self):
        sched = create_scheduler()
        register_jobs(sched)
        jobs = {j.id: j for j in sched.get_jobs()}
        assert set(jobs) == {"price_check", "news_fetch", "cleanup"}

    def test_price_and_news_use_interval_trigger(self):
        sched = create_scheduler()
        register_jobs(sched)
        jobs = {j.id: j for j in sched.get_jobs()}
        assert isinstance(jobs["price_check"].trigger, IntervalTrigger)
        assert isinstance(jobs["news_fetch"].trigger, IntervalTrigger)

    def test_cleanup_uses_cron_at_307(self):
        sched = create_scheduler()
        register_jobs(sched)
        jobs = {j.id: j for j in sched.get_jobs()}
        trigger = jobs["cleanup"].trigger
        assert isinstance(trigger, CronTrigger)
        hour_field = next(f for f in trigger.fields if f.name == "hour")
        minute_field = next(f for f in trigger.fields if f.name == "minute")
        assert hour_field.expressions[0].first == 3
        assert minute_field.expressions[0].first == 7

    def test_interval_hours_from_settings(self):
        from config.settings import get_settings

        s = get_settings()
        sched = create_scheduler()
        register_jobs(sched)
        jobs = {j.id: j for j in sched.get_jobs()}
        assert jobs["price_check"].trigger.interval.total_seconds() == (
            s.price_check_interval_hours * 3600
        )
        assert jobs["news_fetch"].trigger.interval.total_seconds() == (
            s.news_fetch_interval_hours * 3600
        )
