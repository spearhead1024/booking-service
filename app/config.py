"""Application settings, loaded from environment variables (prefix ``BOOKING_``)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOKING_", env_file=".env", extra="ignore")

    app_name: str = "Booking Service"
    database_url: str = "sqlite:///./booking.db"
    sql_echo: bool = False
    # When unset, authentication is disabled (convenient for local development).
    api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
