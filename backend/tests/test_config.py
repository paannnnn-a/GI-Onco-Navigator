import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError, match="production requires unique"):
        Settings(app_env="production")


def test_production_accepts_explicit_secrets() -> None:
    settings = Settings(app_env="production", secret_key="unique-patient-secret", admin_api_key="unique-admin-secret")
    assert settings.app_env == "production"
