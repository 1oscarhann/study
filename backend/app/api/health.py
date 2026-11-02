from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.db import DbSession

router = APIRouter(tags=["system"])
log = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    db: str


@router.get("/health", response_model=HealthResponse)
async def health(session: DbSession) -> HealthResponse | JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        log.exception("Health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "error"})
    return HealthResponse(status="ok", db="ok")
