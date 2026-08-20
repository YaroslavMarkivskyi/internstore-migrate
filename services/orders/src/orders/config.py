from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
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
    # STR-139: Temporal-orchestrated checkout, parallel to the Kafka saga
    # above. Best-effort, same reasoning as inventory_base_url/catalog_base_url
    # having no depends_on: Orders should still boot and serve the existing
    # /checkout fine even if Temporal is briefly down; /checkout/v2 just
    # fails fast in that case.
    temporal_host: str = "temporal:7233"
    temporal_task_queue: str = "checkout-workflow"
    # How long POST /checkout/v2 waits inline for the workflow to finish
    # before falling back to 202 Accepted + {workflow_id} for the caller to
    # poll (see routers/checkout_v2.py) — the ticket's confirmed answer to
    # its own "does the Gateway wait synchronously" open question.
    checkout_v2_wait_seconds: float = 10.0
    # STR-140: OPA sidecar, same pod/network namespace on GKE (see
    # docker-compose.yml's orders-opa for the local dev equivalent).
    opa_url: str = "http://localhost:8181"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
