from pathlib import Path


def test_web_proxy_matches_api_upload_and_security_boundaries() -> None:
    config = Path("frontend/nginx.conf").read_text(encoding="utf-8")

    assert "client_max_body_size 26m;" in config
    assert "Content-Security-Policy" in config
    assert "frame-ancestors 'none'" in config
    assert 'X-Frame-Options "DENY"' in config
    assert 'Permissions-Policy "camera=(), microphone=(), geolocation=()"' in config
    assert "proxy_set_header X-Request-ID $request_id;" in config
