from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 5
    # For checking a product's cross-stock quantity before letting it be
    # (re)published (see routers/products.py's update_product) — same
    # container-to-container bypass-nginx pattern as every other
    # inter-service client in this project.
    inventory_base_url: str
    inventory_timeout_seconds: float = 5.0
    minio_endpoint: str
    minio_public_base_url: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "catalog-product-images"
    # STR-140: OPA sidecar, same pod/network namespace on GKE (see
    # docker-compose.yml's catalog-opa for the local dev equivalent).
    opa_url: str = "http://localhost:8181"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
