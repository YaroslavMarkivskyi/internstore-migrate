from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8000
    database_url: str
    # Dev-only failure simulation (STR-139): no real payment gateway exists
    # here, so /charge needs a deterministic way to fail on demand for saga
    # testing. An amount whose string form ends in this suffix fails instead
    # of charging — e.g. "9.99" with suffix "99" simulates a declined card.
    # Real Stripe/gateway integration is explicitly out of scope.
    payment_fail_on_amount_suffix: str = "99"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
