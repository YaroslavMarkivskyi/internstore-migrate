from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 5


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
