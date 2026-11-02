"""CSRF protection for state-changing API requests.

1. SameSite=Lax cookies (set in sessions.py) already stop most cross-site sends.
2. Every POST/PUT/PATCH/DELETE must carry `X-Requested-With: rb`. A cross-site page
   can't add that header without a CORS preflight, which our CORS policy refuses.
3. If the browser sends an Origin header, it must be our frontend's origin.
"""

from __future__ import annotations

import re

from starlette.types import ASGIApp, Receive, Scope, Send

from app.security.proxy import send_json

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = b"x-requested-with"
CSRF_VALUE = b"rb"
_LOCAL_ORIGIN_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


class CsrfMiddleware:
    def __init__(self, app: ASGIApp, *, frontend_origin: str, allow_localhost: bool) -> None:
        self.app = app
        self._origin = frontend_origin.rstrip("/")
        self._allow_localhost = allow_localhost

    def _origin_ok(self, origin: str) -> bool:
        if origin.rstrip("/") == self._origin:
            return True
        return self._allow_localhost and bool(_LOCAL_ORIGIN_RE.match(origin))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in UNSAFE_METHODS
            or not scope["path"].startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        if headers.get(CSRF_HEADER) != CSRF_VALUE:
            await send_json(send, 403, "Request blocked (missing security header).", "csrf")
            return
        origin = headers.get(b"origin")
        if origin is not None and not self._origin_ok(origin.decode("latin-1")):
            await send_json(send, 403, "Request blocked (unexpected origin).", "csrf")
            return

        await self.app(scope, receive, send)
