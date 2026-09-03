from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/gi_onco.db"
    llm_provider: str = "disabled"
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_provider: str = "local"
    secret_key: str = "change-me-before-production"
    admin_api_key: str = "change-me-before-production"
    allowed_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        placeholders = {
            "change-me-before-production",
            "replace-with-at-least-32-random-bytes",
            "replace-with-a-separate-random-admin-secret",
        }
        if (
            self.secret_key in placeholders
            or self.admin_api_key in placeholders
            or len(self.secret_key) < 32
            or len(self.admin_api_key) < 32
            or self.secret_key == self.admin_api_key
        ):
            raise ValueError(
                "production requires distinct SECRET_KEY and ADMIN_API_KEY values of at least 32 characters"
            )
        origins = self.origins
        if not origins:
            raise ValueError("production requires at least one exact HTTPS ALLOWED_ORIGINS value")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
                or "*" in parsed.netloc
            ):
                raise ValueError(
                    "production ALLOWED_ORIGINS entries must be exact public HTTPS origins without paths, credentials, wildcards, queries, or fragments"
                )
        return self

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.allowed_origins.split(",") if value.strip()]

    @property
    def sqlite_path(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("the community edition currently requires a sqlite:/// database URL")
        return self.database_url.removeprefix(prefix)


@lru_cache
def get_settings() -> Settings:
    return Settings()
