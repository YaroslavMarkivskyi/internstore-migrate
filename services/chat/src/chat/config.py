from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 1.0
    redis_url: str
    object_storage_endpoint: str
    object_storage_public_base_url: str
    object_storage_access_key: str
    object_storage_secret_key: str
    object_storage_bucket: str = "chat-attachments"
    # Empty locally (chat has its own real MinIO bucket there) -- set on
    # GCP where catalog/chat share one physical GCS bucket, see
    # ObjectStorageClient's docstring.
    object_storage_key_prefix: str = ""
    # How long a presigned GET URL (see ObjectStorageClient.generate_presigned_url)
    # stays valid -- generated fresh on every history read (REST or WS), never
    # stored, so this only bounds how long a client can sit on a response
    # before the attachment link in it goes stale.
    object_storage_presigned_url_ttl_seconds: int = 900
    history_replay_limit: int = 50
    # STR-146: called synchronously for registered customers' messages, to
    # forward their internal-token into the shopping agent's ReAct loop
    # (see chat.ws.room and ai_assistant_client.py). Guests never trigger
    # this (see ws/room.py) — no agent access for them.
    ai_assistant_service_url: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
