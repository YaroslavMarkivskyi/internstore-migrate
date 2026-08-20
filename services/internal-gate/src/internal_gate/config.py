from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8090
    # localhost, not the container name -- this runs sidecar-style,
    # network_mode: "service:<app>" in compose / same pod in k8s, same
    # pattern as every OPA sidecar (see docker-compose.yml's catalog-opa).
    opa_url: str = "http://localhost:8181"
    # Which OPA package's /allow (and /subject, exported alongside it --
    # see policies/common.rego) this instance checks. One internal-gate
    # per domain service, parameterized by this instead of one image per
    # service.
    opa_package: str
    opa_timeout_seconds: float = 2.0


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
