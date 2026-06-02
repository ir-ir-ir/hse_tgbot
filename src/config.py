from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Конфигурация бота, загружается из .env."""

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    channel_id: str = Field(..., alias="CHANNEL_ID")
    database_url: str = Field(
        default="sqlite+aiosqlite:///submissions.db", alias="DATABASE_URL"
    )

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    fsm_ttl: int = Field(default=86400, alias="FSM_TTL")  # 24 часа

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def redis_url(self) -> str:
        """Формирует URL для подключения к Redis."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        if isinstance(value, int):
            return [value]
        raise TypeError(f"Unsupported ADMIN_IDS type: {type(value)!r}")

    @field_validator("channel_id", mode="before")
    @classmethod
    def _normalize_channel_id(cls, value):
        if value is None:
            return value
        return str(value).strip()

    @field_validator("redis_port", mode="before")
    @classmethod
    def _validate_redis_port(cls, value):
        if value is not None:
            port = int(value)
            if not (1 <= port <= 65535):
                raise ValueError(f"Invalid Redis port: {port}")
            return port
        return value

    @field_validator("redis_db", mode="before")
    @classmethod
    def _validate_redis_db(cls, value):
        if value is not None:
            db = int(value)
            if not (0 <= db <= 15):
                raise ValueError(f"Invalid Redis database index: {db}")
            return db
        return value

    @field_validator("fsm_ttl", mode="before")
    @classmethod
    def _validate_fsm_ttl(cls, value):
        if value is not None:
            ttl = int(value)
            if ttl < 60:
                raise ValueError(f"FSM TTL must be at least 60 seconds, got {ttl}")
            return ttl
        return value


settings = Settings()
