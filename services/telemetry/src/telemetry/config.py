from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 5
    # Matches the simulator's 5-min transmission cadence — see docs/EVENT_BROKER.md.
    violation_check_interval_seconds: float = 300
    # Realistic default (1h, matching EP-02/EP-09's "sustained for an
    # hour"). docker-compose.yml shrinks this to a dev-only value so
    # scripts/test-telemetry-saga.sh doesn't have to wait a real hour —
    # same pattern as Inventory's RESERVATION_TTL_SECONDS.
    violation_window_seconds: float = 3600


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
