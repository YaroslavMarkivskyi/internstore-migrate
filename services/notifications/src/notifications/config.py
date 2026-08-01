from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    kafka_bootstrap_servers: str
    smtp_host: str
    smtp_port: int = 1025
    smtp_from_address: str = "notifications@internstore.local"
    # Dedup cache sizing — see notifications/dedup.py for why an in-memory
    # TTL cache is the whole idempotency story here (no DB, no
    # processed_events table).
    dedup_ttl_seconds: float = 3600
    dedup_max_size: int = 10_000


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
