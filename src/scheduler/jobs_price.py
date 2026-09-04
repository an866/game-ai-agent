"""价格巡检定时任务（代理 —— 逻辑在 services.price_monitor_service）"""

from src.services.price_monitor_service import run_price_check as check_watchlist_prices