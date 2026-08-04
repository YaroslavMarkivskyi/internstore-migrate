from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    internal_token_secret: str
    inventory_base_url: str
    inventory_timeout_seconds: float = 5.0
    # Container-to-container address, same pattern as inventory_base_url --
    # needed to look up each order item's *current* authoritative price
    # server-side when building a Stripe PaymentIntent. Orders itself keeps
    # no price snapshot (see OrderItem in models.py), and the amount
    # charged must never be trusted from the client.
    catalog_base_url: str
    catalog_timeout_seconds: float = 5.0
    kafka_bootstrap_servers: str
    outbox_poll_interval_seconds: float = 1.0
    stripe_secret_key: str
    stripe_webhook_secret: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
