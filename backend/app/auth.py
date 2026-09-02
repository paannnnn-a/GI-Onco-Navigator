from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4


class InvalidPatientToken(ValueError):
    pass


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_patient_token(secret: str, ttl_seconds: int = 86400) -> tuple[str, str, int]:
    patient_id = str(uuid4())
    expires_at = int(time.time()) + ttl_seconds
    payload = _encode(json.dumps({"sub": patient_id, "exp": expires_at}).encode("utf-8"))
    signature = _encode(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return patient_id, f"{payload}.{signature}", expires_at


def verify_patient_token(token: str, secret: str, patient_id: str) -> None:
    try:
        payload, supplied_signature = token.split(".", 1)
        expected = _encode(
            hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected):
            raise InvalidPatientToken("invalid signature")
        claims = json.loads(_decode(payload))
        if claims.get("sub") != patient_id:
            raise InvalidPatientToken("token does not grant access to this patient")
        if not isinstance(claims.get("exp"), int) or claims["exp"] < int(time.time()):
            raise InvalidPatientToken("token expired")
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        if isinstance(exc, InvalidPatientToken):
            raise
        raise InvalidPatientToken("malformed token") from exc
