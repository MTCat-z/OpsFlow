"""
应用全局配置 — 从 .env 文件读取
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "内网运维集成工具平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./data/ops_platform.db"
    # PostgreSQL 示例: postgresql://user:pass@localhost:5432/opsflow
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    FERNET_KEY: str = ""
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    CORS_ORIGINS: List[str] = [
        "http://localhost:8080",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
    ]
    ALLOWED_SCAN_NETWORKS: List[str] = [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]
    NMAP_PATH: str = "nmap"
    IPERF3_PATH: str = "iperf3"

    # DingTalk
    DINGTALK_WEBHOOK_URL: str = ""
    DINGTALK_SECRET: str = ""

    # Zabbix
    ZABBIX_URL: str = ""
    ZABBIX_API_TOKEN: str = ""
    ZABBIX_USER: str = ""
    ZABBIX_PASSWORD: str = ""
    ZABBIX_VERIFY_SSL: bool = False
    ZABBIX_CACHE_TTL: int = 60
    ZABBIX_TIMEOUT: int = 10


settings = Settings()