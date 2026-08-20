from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    # Only used to mint this service's own outbound token when calling
    # Catalog (see catalog_client.py) -- verifying *inbound* tokens is now
    # inventory-gate/inventory-verify/inventory-opa's job, ahead of this
    # app entirely. See inventory/README.md's Auth section.
    internal_token_secret: str
    kafka_bootstrap_servers: str
    # For unpublishing a product in Catalog once it hits zero quantity
    # across every stock (see stock_sync.py) -- same
    # container-to-container bypass-nginx pattern as Orders -> Catalog.
    catalog_base_url: str
    catalog_timeout_seconds: float = 5.0
    # Realistic production default; docker-compose.yml overrides both to
    # short values so the DoD's expired-reservation scenario is actually
    # runnable in local dev/tests instead of only declared.
    reservation_ttl_seconds: float = 86400
    reservation_check_interval_seconds: float = 60
    # STR-149: how often the snapshot worker polls for aggregates that have
    # crossed snapshots.SNAPSHOT_EVENT_THRESHOLD / SNAPSHOT_MAX_AGE. Not on
    # the reservation hot path -- see snapshots.py.
    snapshot_check_interval_seconds: float = 60


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
