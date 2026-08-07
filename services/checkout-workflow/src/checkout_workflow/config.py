from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    temporal_host: str = "temporal:7233"
    task_queue: str = "checkout-workflow"
    internal_token_secret: str

    inventory_base_url: str
    inventory_timeout_seconds: float = 5.0
    orders_base_url: str
    orders_timeout_seconds: float = 5.0
    payments_base_url: str
    payments_timeout_seconds: float = 5.0

    kafka_bootstrap_servers: str

    # Escalation (STR-139): once release_stock's activity attempt count
    # crosses this, publish EscalationRequired to ops-events so Notifications
    # can alert an admin. Kept low here relative to a real deployment's
    # value so the escalation path is actually exercisable in dev/CI without
    # waiting through a long real backoff — see
    # scripts/test-temporal-saga.sh's compensation-failure scenario.
    escalation_attempt_threshold: int = 10


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
