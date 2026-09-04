"""游戏 AI 智能体 —— 启动入口"""

import sys
import asyncio
import argparse
from pathlib import Path

from loguru import logger
from config.settings import get_settings


def setup_logging():
    """配置日志系统 —— 控制台 + 文件滚动"""
    settings = get_settings()
    log_dir = settings.project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 控制台输出（彩色）
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # 全量日志文件（按天滚动，保留 30 天）
    logger.add(
        log_dir / "game_agent_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
    )

    # 错误日志单独记录
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        encoding="utf-8",
    )

    return logger


def run_ui():
    """启动 Streamlit 前端"""
    import os
    import streamlit.web.cli as stcli

    ui_path = Path(__file__).parent / "ui" / "app.py"
    sys.argv = ["streamlit", "run", str(ui_path)]
    # preview 环境通过 PORT 注入动态端口（streamlit 需显式 --server.port）
    if os.environ.get("PORT"):
        sys.argv += ["--server.port", os.environ["PORT"], "--server.headless", "true"]
    logger.info("启动 Streamlit 前端...")
    stcli.main()


def run_scheduler():
    """启动后台调度器"""
    from src.scheduler.engine import create_scheduler, register_jobs

    scheduler = create_scheduler()
    register_jobs(scheduler)
    scheduler.start()

    logger.info("调度器已启动 (价格巡检 + 新闻抓取)")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("调度器已停止")


def init_db():
    """初始化数据库"""
    from src.data.database import create_tables

    asyncio.run(create_tables())
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    setup_logging()

    parser = argparse.ArgumentParser(description="游戏 AI 智能体")
    parser.add_argument("command", choices=["ui", "scheduler", "init-db"],
                        help="ui: 启动前端 | scheduler: 启动调度器 | init-db: 初始化数据库")
    args = parser.parse_args()

    logger.info(f"执行命令: {args.command}")

    if args.command == "ui":
        run_ui()
    elif args.command == "scheduler":
        run_scheduler()
    elif args.command == "init-db":
        init_db()
