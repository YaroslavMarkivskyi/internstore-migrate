from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 5
    inventory_base_url: str
    inventory_timeout_seconds: float = 5.0
    object_storage_endpoint: str
    object_storage_public_base_url: str
    object_storage_access_key: str
    object_storage_secret_key: str
    object_storage_bucket: str = "catalog-product-images"
    # Empty locally (catalog has its own real MinIO bucket there) -- set on
    # GCP where catalog/chat share one physical GCS bucket, see
    # ObjectStorageClient's docstring.
    object_storage_key_prefix: str = ""
    # How long a presigned GET URL (see ObjectStorageClient.generate_presigned_url)
    # stays valid -- generated fresh on every GET /products/{id}/images call,
    # never stored, so this only bounds how long a client can sit on a
    # response before the image link in it goes stale.
    object_storage_presigned_url_ttl_seconds: int = 900


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
