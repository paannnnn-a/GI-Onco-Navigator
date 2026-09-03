from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.app.knowledge import normalize_text

MAX_WEBPAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class WebChunk:
    ordinal: int
    text: str
    section_path: list[str]
    content_hash: str


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.heading = "Web page content"
        self.pending_heading = False
        self.current: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.hidden_depth += 1
        if self.hidden_depth:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self._flush()
            self.pending_heading = True
        elif tag in {"p", "li", "article", "section"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
            return
        if self.hidden_depth:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            heading = normalize_text(" ".join(self.current))
            if heading:
                self.heading = heading[:200]
            self.current = []
            self.pending_heading = False
        elif tag in {"p", "li", "article", "section"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth and data.strip():
            self.current.append(data.strip())

    def _flush(self) -> None:
        if self.pending_heading:
            return
        text = normalize_text(" ".join(self.current))
        if len(text) >= 20:
            self.blocks.append((self.heading, text))
        self.current = []

    def close(self) -> None:
        super().close()
        self._flush()


def validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("web ingestion requires a credential-free HTTPS URL")
    for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("web ingestion refuses private, loopback, or reserved addresses")


def fetch_public_webpage(url: str) -> bytes:
    validate_public_https_url(url)
    request = Request(url, headers={"User-Agent": "GI-Onco-Navigator/0.1 evidence-ingest"})
    with urlopen(request, timeout=20) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"unsupported webpage content type: {content_type}")
        content = response.read(MAX_WEBPAGE_BYTES + 1)
    if len(content) > MAX_WEBPAGE_BYTES:
        raise ValueError("webpage exceeds the 10 MiB ingestion limit")
    return content


def extract_web_chunks(content: bytes, target_chars: int = 1200) -> list[WebChunk]:
    parser = _ReadableHtmlParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    chunks: list[WebChunk] = []
    buffer: list[str] = []
    section = "Web page content"

    def flush() -> None:
        nonlocal buffer
        text = normalize_text("\n".join(buffer))
        if text:
            chunks.append(
                WebChunk(
                    ordinal=len(chunks), text=text,
                    section_path=[section, f"Content block {len(chunks) + 1}"],
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )
            )
        buffer = []

    for heading, text in parser.blocks:
        if buffer and (heading != section or sum(map(len, buffer)) + len(text) > target_chars):
            flush()
        section = heading
        buffer.append(text)
    flush()
    return chunks
