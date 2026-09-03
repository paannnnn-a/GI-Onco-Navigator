import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError, match="production requires distinct"):
        Settings(app_env="production")


def test_production_accepts_explicit_secrets() -> None:
    settings = Settings(
        app_env="production",
        secret_key="patient-token-signing-secret-32-characters",
        admin_api_key="independent-admin-access-secret-32-characters",
        allowed_origins="https://navigator.example.org",
    )
    assert settings.app_env == "production"


@pytest.mark.parametrize(
    "allowed_origins",
    [
        "*",
        "http://navigator.example.org",
        "https://localhost",
        "https://*.example.org",
        "https://navigator.example.org/path",
        "https://user:password@navigator.example.org",
    ],
)
def test_production_rejects_unsafe_browser_origins(allowed_origins: str) -> None:
    with pytest.raises(ValidationError, match="exact public HTTPS origins"):
        Settings(
            app_env="production",
            secret_key="patient-token-signing-secret-32-characters",
            admin_api_key="independent-admin-access-secret-32-characters",
            allowed_origins=allowed_origins,
        )


def test_production_rejects_shared_or_short_secrets() -> None:
    shared = "one-shared-secret-that-is-long-enough-123"
    with pytest.raises(ValidationError, match="distinct"):
        Settings(
            app_env="production",
            secret_key=shared,
            admin_api_key=shared,
            allowed_origins="https://navigator.example.org",
        )
