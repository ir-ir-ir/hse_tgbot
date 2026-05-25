from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация бота, загружается из .env."""

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
    channel_id: str = Field(..., alias="CHANNEL_ID")
    database_url: str = Field(
        default="sqlite+aiosqlite:///submissions.db", alias="DATABASE_URL"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return [int(v) for v in value]
        raise TypeError(f"Unsupported ADMIN_IDS type: {type(value)!r}")

    @field_validator("channel_id", mode="before")
    @classmethod
    def _normalize_channel_id(cls, value):
        if value is None:
            return value
        return str(value).strip()


settings = Settings()
