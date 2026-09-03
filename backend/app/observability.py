from __future__ import annotations

import re
import threading
from collections import Counter
from uuid import uuid4

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def safe_request_id(value: str | None) -> str:
    """Accept a compact opaque identifier or replace it before logging and reflecting it."""
    return value if value and REQUEST_ID_PATTERN.fullmatch(value) else str(uuid4())


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()

    def record(self, method: str, route: str, status: int) -> None:
        with self._lock:
            self._requests[(method, route, status)] += 1

    def prometheus(self) -> str:
        lines = [
            "# HELP gi_onco_http_requests_total HTTP requests handled by the API.",
            "# TYPE gi_onco_http_requests_total counter",
        ]
        with self._lock:
            items = sorted(self._requests.items())
        for (method, route, status), count in items:
            safe_route = route.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(
                f'gi_onco_http_requests_total{{method="{method}",route="{safe_route}",status="{status}"}} {count}'
            )
        return "\n".join(lines) + "\n"
