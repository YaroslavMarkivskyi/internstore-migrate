from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
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
    # STR-140: OPA sidecar, same pod/network namespace on GKE (see
    # docker-compose.yml's inventory-opa for the local dev equivalent).
    opa_url: str = "http://localhost:8181"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
