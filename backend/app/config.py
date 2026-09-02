from functools import lru_cache

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
