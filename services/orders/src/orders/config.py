from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    inventory_base_url: str
    inventory_timeout_seconds: float = 5.0
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 1.0


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
