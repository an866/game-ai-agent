"""MySQL 数据库初始化脚本 —— 创建所有表"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.database import create_tables, drop_tables
from config.settings import get_settings


async def init():
    settings = get_settings()
    print(f"连接 MySQL: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")
    print("创建表结构...")
    await create_tables()
    print("表创建完成!")


async def reset():
    """危险操作：删除并重建所有表"""
    confirm = input("确认要删除所有表并重建吗？(yes/no): ")
    if confirm.lower() == "yes":
        print("删除表...")
        await drop_tables()
        print("重建表...")
        await create_tables()
        print("重置完成!")
    else:
        print("操作已取消。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="删除并重建所有表")
    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset())
    else:
        asyncio.run(init())
