from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    # Realistic production default; docker-compose.yml overrides both to
    # short values so the DoD's expired-reservation scenario is actually
    # runnable in local dev/tests instead of only declared.
    reservation_ttl_seconds: float = 86400
    reservation_check_interval_seconds: float = 60


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
