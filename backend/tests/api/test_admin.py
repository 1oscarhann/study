"""Admin: only admins, topic import/edit, official questions."""

import pytest
from sqlalchemy import select

from app.models import PlaySession, Question
from tests.api.helpers import make_admin, play_through, seed_content, start_quiz, topic_id
from tests.conftest import signup

pytestmark = pytest.mark.asyncio

NEW_Q = {
    "type": "fill_blank",
    "prompt": "The ___ is the control centre of the cell.",
    "accepted": ["nucleus"],
    "explanation": "The nucleus contains genetic material and controls the cell.",
    "difficulty": 1,
}


@pytest.fixture
async def admin(app, client):
    await seed_content(app)
    await signup(client)
    await make_admin(app, "SwiftOtter42")
    return client


async def test_non_admins_are_refused(app, client):
    await seed_content(app)
    await signup(client)
    cells = await topic_id(app, "sci-bio-cells")
    for method, url, body in [
        ("GET", f"/api/admin/questions?topic_id={cells}", None),
        ("POST", "/api/admin/questions", {"topic_id": cells, "question": NEW_Q}),
        ("PATCH", f"/api/admin/topics/{cells}", {"is_active": False}),
        ("POST", "/api/admin/topics/import", {"subjects": []}),
    ]:
        resp = await client.request(method, url, json=body)
        assert resp.status_code == 403, url


async def test_admin_adds_an_official_question_that_shows_up_in_quizzes(app, admin):
    cells = await topic_id(app, "sci-bio-cells")
    resp = await admin.post("/api/admin/questions", json={"topic_id": cells, "question": NEW_Q})
    assert resp.status_code == 201
    assert resp.json()["origin"] == "admin" and resp.json()["status"] == "live"

    dupe = await admin.post("/api/admin/questions", json={"topic_id": cells, "question": NEW_Q})
    assert dupe.status_code == 409

    listed = (await admin.get(f"/api/admin/questions?topic_id={cells}")).json()
    assert len(listed) == 26
    assert all("answer" in q for q in listed)  # admins can see answers


async def test_admin_questions_get_the_same_checks(app, admin):
    cells = await topic_id(app, "sci-bio-cells")
    bad = {**NEW_Q, "prompt": "No blank in this one at all"}
    resp = await admin.post("/api/admin/questions", json={"topic_id": cells, "question": bad})
    assert resp.status_code == 422


async def test_deleting_keeps_history_for_answered_questions(app, admin):
    cells = await topic_id(app, "sci-bio-cells")
    state = await start_quiz(admin, app)
    await play_through(admin, app, state, stop_after=1)
    answered_id = state["question"]["question_id"]
    async with app.state.db.sessionmaker() as s:
        # Pick a question that isn't in this game at all (served-but-unanswered ones are
        # also kept, because a game is using them).
        in_game = (await s.get(PlaySession, state["session_id"])).question_ids
        unanswered_id = await s.scalar(
            select(Question.id).where(Question.topic_id == cells, Question.id.not_in(in_game))
        )
    assert (await admin.delete(f"/api/admin/questions/{answered_id}")).status_code == 204
    assert (await admin.delete(f"/api/admin/questions/{unanswered_id}")).status_code == 204
    async with app.state.db.sessionmaker() as s:
        assert (await s.get(Question, answered_id)).status == "archived"
        assert await s.get(Question, unanswered_id) is None


async def test_admin_sets_learn_more_link_https_only(app, admin):
    cells = await topic_id(app, "sci-bio-cells")
    bad = await admin.patch(
        f"/api/admin/topics/{cells}", json={"learn_more_url": "http://x.example"}
    )
    assert bad.status_code == 422
    ok = await admin.patch(
        f"/api/admin/topics/{cells}", json={"learn_more_url": "https://example.org/cells"}
    )
    assert ok.json()["learn_more_url"] == "https://example.org/cells"


async def test_admin_imports_topics(app, admin):
    body = {
        "subjects": [
            {"subject": "Physics", "qualification": "GCSE (triple)", "board": "AQA",
             "confidence": "stated",
             "topics": [{"id": "sci-phys-energy", "name": "Energy", "subtopics": ["Power"]}]}
        ]
    }  # fmt: skip
    stats = (await admin.post("/api/admin/topics/import", json=body)).json()
    assert stats["topics_updated"] == 1  # subtopics changed
