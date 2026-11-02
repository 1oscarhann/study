"""Helpers for API tests that need content and want to play through games."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Question, Subject, Topic, User
from app.services.content import (
    apply_catalog,
    apply_seed_questions,
    load_catalog,
    load_question_files,
)


async def seed_content(app: FastAPI) -> None:
    async with app.state.db.sessionmaker() as s:
        await apply_catalog(s, load_catalog())
        await apply_seed_questions(s, load_question_files())
        await s.commit()


async def subject_id(app: FastAPI, slug: str) -> int:
    async with app.state.db.sessionmaker() as s:
        return await s.scalar(select(Subject.id).where(Subject.slug == slug))  # type: ignore[return-value]


async def topic_id(app: FastAPI, slug: str) -> int:
    async with app.state.db.sessionmaker() as s:
        return await s.scalar(select(Topic.id).where(Topic.slug == slug))  # type: ignore[return-value]


async def question(app: FastAPI, qid: int) -> Question:
    async with app.state.db.sessionmaker() as s:
        q = await s.get(Question, qid)
        assert q is not None
        return q


async def make_admin(app: FastAPI, username: str) -> None:
    async with app.state.db.sessionmaker() as s:
        user = await s.scalar(select(User).where(User.username == username))
        assert user is not None
        user.is_admin = True
        await s.commit()


async def response_for(app: FastAPI, served: dict[str, Any], *, correct: bool) -> dict[str, Any]:
    """Build a right (or deliberately wrong) answer for a served question."""
    q = await question(app, served["question_id"])
    match q.type:
        case "mcq":
            if correct:
                return {"option_id": q.answer["option_id"]}
            wrong = next(o["id"] for o in served["options"] if o["id"] != q.answer["option_id"])
            return {"option_id": wrong}
        case "fill_blank":
            return {"text": q.answer["accepted"][0] if correct else "definitely not this"}
        case "order":
            order = list(q.answer["order"])
            return {"order": order if correct else list(reversed(order))}
        case "match":
            pairs = dict(q.answer["pairs"])
            if not correct:
                keys = list(pairs)
                values = [pairs[k] for k in keys]
                pairs = dict(zip(keys, values[1:] + values[:1], strict=True))
            return {"pairs": pairs}
    raise AssertionError(q.type)


async def start_quiz(
    client: AsyncClient, app: FastAPI, topic: str = "sci-bio-cells", subject: str = "biology",
    **extra: Any,
) -> dict[str, Any]:  # fmt: skip
    resp = await client.post(
        "/api/play",
        json={
            "mode": "quiz",
            "topic_id": await topic_id(app, topic),
            "subject_id": await subject_id(app, subject),
            **extra,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def play_through(
    client: AsyncClient, app: FastAPI, state: dict[str, Any], pattern: list[bool] | None = None,
    stop_after: int | None = None,
) -> list[dict[str, Any]]:  # fmt: skip
    """Answer every question (right/wrong per `pattern`, default all right)."""
    results = []
    served = state["question"]
    i = 0
    while served is not None and (stop_after is None or i < stop_after):
        ok = pattern[i % len(pattern)] if pattern else True
        response = await response_for(app, served, correct=ok)
        resp = await client.post(
            f"/api/play/{state['session_id']}/answer",
            json={"position": served["position"], "response": response},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        results.append(body)
        served = body["next"]
        i += 1
    return results
