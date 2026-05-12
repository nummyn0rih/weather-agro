from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://weather:weather@db:5432/weather"
    POSTGRES_USER: str = "weather"
    POSTGRES_PASSWORD: str = "weather"
    POSTGRES_DB: str = "weather"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # ── Security / JWT ────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173"

    # ── Frontend ──────────────────────────────────────────
    # Used to build invite URLs (POST /api/admin/invites returns
    # `${FRONTEND_URL}/accept-invite/{token}` — see ADR-005).
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Environment ───────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── Admin user ────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    # ── External APIs ─────────────────────────────────────
    OPENWEATHERMAP_API_KEY: str = ""

    # ── Telegram ──────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BIND_CODE_TTL: int = 300

    # ── Alerts ────────────────────────────────────────────
    ALERTS_DEDUP_HOURS: int = 6

    # ── Encryption (Fernet) ───────────────────────────────
    ENCRYPTION_KEY: str = ""

    # ── Yandex.Disk WebDAV ────────────────────────────────
    YANDEX_DISK_LOGIN: str = ""
    YANDEX_DISK_APP_PASSWORD: str = ""
    YANDEX_DISK_BACKUP_PATH: str = "/weather-app-backups/"

    # ── Backup retention ──────────────────────────────────
    BACKUP_RETENTION_DAILY: int = 30
    BACKUP_RETENTION_MONTHLY: int = 12

    # ── Uploads ───────────────────────────────────────────
    UPLOAD_DIR: str = "/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_PHOTOS_PER_EVENT: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
