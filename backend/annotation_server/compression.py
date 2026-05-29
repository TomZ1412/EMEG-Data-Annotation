from __future__ import annotations

import gzip
from collections.abc import Callable
from typing import Any

try:
    import brotli
except ImportError:  # pragma: no cover - depends on deployment extras
    brotli = None


class CompressedResponseMiddleware:
    def __init__(self, app: Callable, minimum_size: int = 1024, gzip_level: int = 6) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.gzip_level = gzip_level

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        accept_encoding = request_headers.get("accept-encoding", "")
        encoding = self._select_encoding(accept_encoding)
        if not encoding:
            await self.app(scope, receive, send)
            return

        start_message: dict[str, Any] | None = None
        body_chunks: list[bytes] = []

        async def capture(message: dict[str, Any]) -> None:
            nonlocal start_message
            if message["type"] == "http.response.start":
                start_message = message
                return
            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    await self._send_response(send, start_message, body_chunks, encoding)

        await self.app(scope, receive, capture)

    def _select_encoding(self, accept_encoding: str) -> str | None:
        encodings = {item.strip().split(";", 1)[0].lower() for item in accept_encoding.split(",")}
        if "br" in encodings and brotli is not None:
            return "br"
        if "gzip" in encodings:
            return "gzip"
        return None

    async def _send_response(
        self,
        send: Callable,
        start_message: dict[str, Any] | None,
        body_chunks: list[bytes],
        encoding: str,
    ) -> None:
        if start_message is None:
            return

        body = b"".join(body_chunks)
        headers = list(start_message.get("headers", []))
        status = int(start_message.get("status", 200))

        if not self._should_compress(status, headers, len(body)):
            await send(start_message)
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        compressed = self._compress(body, encoding)
        filtered_headers = [
            (key, value)
            for key, value in headers
            if key.lower() not in {b"content-length", b"content-encoding"}
        ]
        filtered_headers.extend([
            (b"content-encoding", encoding.encode("latin1")),
            (b"content-length", str(len(compressed)).encode("latin1")),
            (b"vary", b"Accept-Encoding"),
        ])

        await send({**start_message, "headers": filtered_headers})
        await send({"type": "http.response.body", "body": compressed, "more_body": False})

    def _should_compress(self, status: int, headers: list[tuple[bytes, bytes]], size: int) -> bool:
        if status < 200 or status in {204, 304} or size < self.minimum_size:
            return False
        header_map = {key.lower(): value.lower() for key, value in headers}
        if b"content-encoding" in header_map:
            return False
        content_type = header_map.get(b"content-type", b"")
        return any(token in content_type for token in (b"application/json", b"text/", b"application/javascript"))

    def _compress(self, body: bytes, encoding: str) -> bytes:
        if encoding == "br" and brotli is not None:
            return brotli.compress(body)
        return gzip.compress(body, compresslevel=self.gzip_level)
