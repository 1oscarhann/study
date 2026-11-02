"""One error shape for the whole API: {"detail": str, "code": str, "field": str | null}.

`detail` is always a plain sentence the frontend can show as-is.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status: int,
        detail: str,
        *,
        code: str,
        field: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.code = code
        self.field = field
        self.headers = headers


def _body(detail: str, code: str, field: str | None) -> dict[str, str | None]:
    return {"detail": detail, "code": code, "field": field}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=_body(exc.detail, exc.code, exc.field),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = [part for part in first.get("loc", ()) if isinstance(part, str) and part != "body"]
        field = loc[-1] if loc else None
        message = str(first.get("msg", "Invalid input.")).removeprefix("Value error, ")
        if field:
            message = f"{field.replace('_', ' ').capitalize()}: {message}"
        return JSONResponse(status_code=422, content=_body(message, "invalid_input", field))
