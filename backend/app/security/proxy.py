"""In prod, only accept traffic that came through the Cloudflare Worker.

The Worker adds `X-Proxy-Secret` (a shared secret) and `X-Client-IP` (from
`CF-Connecting-IP`). Requests without the right secret get a 403, so nobody can hit the
Render URL directly, skip the proxy, or spoof their IP to dodge rate limits.
"""

from __future__ import annotations

import hmac

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

PROXY_SECRET_HEADER = b"x-proxy-secret"
CLIENT_IP_HEADER = "x-client-ip"
# Render's health checker calls the service directly, not via the Worker.
EXEMPT_PATHS = frozenset({"/api/health"})


class ProxyGuardMiddleware:
    def __init__(self, app: ASGIApp, *, shared_secret: str) -> None:
        self.app = app
        self._secret = shared_secret.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        supplied = b""
        for name, value in scope["headers"]:
            if name == PROXY_SECRET_HEADER:
                supplied = value
                break

        if not hmac.compare_digest(supplied, self._secret):
            await _send_json(send, 403, b'{"detail":"Forbidden"}')
            return

        await self.app(scope, receive, send)


async def _send_json(send: Send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def client_ip(request: Request) -> str:
    """Best-effort client IP. Only trust X-Client-IP in prod, where the guard has run."""
    settings = request.app.state.settings
    if settings.is_prod:
        forwarded = request.headers.get(CLIENT_IP_HEADER)
        if forwarded:
            return forwarded.strip()
    return request.client.host if request.client else "unknown"
