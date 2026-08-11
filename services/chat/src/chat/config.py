from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 1.0
    redis_url: str
    minio_endpoint: str
    minio_public_base_url: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "chat-attachments"
    history_replay_limit: int = 50
    # STR-146: called synchronously for registered customers' messages, to
    # forward their internal-token into the shopping agent's ReAct loop
    # (see chat.ws.room and ai_assistant_client.py). Guests never trigger
    # this (see ws/room.py) — no agent access for them.
    ai_assistant_service_url: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
