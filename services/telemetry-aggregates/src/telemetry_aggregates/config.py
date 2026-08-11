from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    # This service's own instance — a real second Postgres, not a
    # schema-in-telemetry-db shortcut. See README's "Physical instance
    # separation" section.
    database_url: str
    # Must match auth-backend's INTERNAL_TOKEN_SECRET, same as every other
    # domain service — GET /aggregates is admin-only (see auth.py).
    internal_token_secret: str
    # Read-only connection to telemetry-db's raw temperature_readings /
    # store_product_thresholds tables. Used only by backfill.py — the one
    # deliberate exception to this service's "no cross-database dependency"
    # preference for the incremental path. See README.
    telemetry_db_url: str
    kafka_bootstrap_servers: str
    # How often backfill.py recomputes the current + previous hour from
    # telemetry-db and overwrites hourly_aggregates. This is the
    # correctness backstop for the incremental Kafka path — see README's
    # "Idempotency guarantee" section.
    backfill_interval_minutes: float = 15


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
