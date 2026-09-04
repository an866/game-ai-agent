"""项目配置中心 —— Pydantic Settings 管理所有环境变量和路径"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 项目路径 ----
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    chroma_persist_dir: str = str(data_dir / "chroma")

    # ---- LLM ----
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_model_complex: str = "gpt-4o"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"

    # ---- 外部 API Keys ----
    steam_api_key: str = ""
    rawg_api_key: str = ""
    itad_api_key: str = ""
    tavily_api_key: str = ""

    # ---- MySQL ----
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "game_agent"

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # ---- 调度器 ----
    price_check_interval_hours: int = 6
    news_fetch_interval_hours: int = 2
    timezone: str = "Asia/Shanghai"

    # ---- 日志 ----
    log_level: str = "INFO"

    # ---- Memory ----
    memory_max_messages: int = 20
    memory_compress_threshold: float = 0.85
    memory_recent_keep: int = 8

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def mysql_sync_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
