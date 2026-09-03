import json
import tomllib
from pathlib import Path

from backend.app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_public_release_versions_are_synchronized() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        backend_version = tomllib.load(handle)["project"]["version"]
    frontend_version = json.loads(
        (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )["version"]

    assert backend_version == "1.0.0"
    assert frontend_version == backend_version
    assert app.version == backend_version
    assert f"## {backend_version} " in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
