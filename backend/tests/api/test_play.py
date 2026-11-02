"""Quick quiz: serving, marking, explanations, filtering, retries, ownership."""

import json

import pytest
from sqlalchemy import select, update

from app.models import PlaySession, Question
from tests.api.helpers import (
    play_through,
    question,
    response_for,
    seed_content,
    start_quiz,
    subject_id,
    topic_id,
)
from tests.conftest import open_client, signup

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def player(app, client):
    await seed_content(app)
    await signup(client)
    return client


async def test_quiz_serves_ten_questions_and_never_leaks_answers(app, player):
    state = await start_quiz(player, app)
    assert state["mode"] == "quiz" and state["status"] == "active"
    assert state["progress"] == {"answered": 0, "correct": 0, "total": 10}
    assert state["topic"]["name"] == "Cell biology"

    served = state["question"]
    while served is not None:
        q = await question(app, served["question_id"])
        text = json.dumps(served)
        # The served question must not contain the answer or the explanation.
        assert q.explanation not in text
        assert "answer" not in served and "accepted" not in text and "explanation" not in served
        if q.type == "fill_blank":
            assert all(a not in text for a in q.answer["accepted"] if len(a) > 3)
        response = await response_for(app, served, correct=True)
        resp = await player.post(
            f"/api/play/{state['session_id']}/answer",
            json={"position": served["position"], "response": response},
        )
        served = resp.json()["next"]


async def test_marking_explanations_and_summary(app, player):
    state = await start_quiz(player, app)
    results = await play_through(player, app, state, pattern=[True, False])
    assert len(results) == 10
    for i, r in enumerate(results):
        fb = r["feedback"]
        assert fb["correct"] is (i % 2 == 0)
        assert fb["explanation"]
        assert fb["correct_answer"]
        # The "learn more" link only shows after a wrong answer.
        if fb["correct"]:
            assert fb["learn_more_url"] is None
        else:
            assert fb["learn_more_url"] == "https://en.wikipedia.org/wiki/Cell_(biology)"
    final = results[-1]
    assert final["next"] is None
    summary = final["summary"]
    assert summary["status"] == "finished"
    assert (summary["answered"], summary["correct"], summary["accuracy"]) == (10, 5, 0.5)
    assert len(summary["results"]) == 10

    again = (await player.get(f"/api/play/{state['session_id']}")).json()
    assert again["question"] is None and again["summary"]["correct"] == 5


async def test_partial_credit_note_for_order_and_match(app, player):
    # Leave only the order/match questions live, so the quiz is guaranteed to include them.
    hist = await topic_id(app, "hist-weimar-nazi")
    async with app.state.db.sessionmaker() as s:
        await s.execute(
            update(Question)
            .where(Question.topic_id == hist, Question.type.in_(["mcq", "fill_blank"]))
            .values(status="archived")
        )
        await s.commit()
    state = await start_quiz(player, app, topic="hist-weimar-nazi", subject="history")
    assert state["progress"]["total"] == 5
    results = await play_through(player, app, state, pattern=[False])
    notes = [r["feedback"]["partial"] for r in results]
    assert all(n and " of " in n for n in notes), notes


async def test_combined_science_never_gets_triple_only_questions(app, player):
    combined = await subject_id(app, "combined-science-trilogy")
    for _ in range(3):
        state = await start_quiz(player, app, subject="combined-science-trilogy")
        assert state["subject_id"] == combined
        assert state["topic"]["name"] == "Biology 1: Cell biology"
        async with app.state.db.sessionmaker() as s:
            ids = (await s.get(PlaySession, state["session_id"])).question_ids
            triple = await s.scalars(
                select(Question.id).where(Question.id.in_(ids), Question.triple_only)
            )
            assert list(triple) == []


async def test_foundation_toggle_hides_higher_only_questions(app, player):
    cells = await topic_id(app, "sci-bio-cells")
    async with app.state.db.sessionmaker() as s:
        keep = list(await s.scalars(select(Question.id).where(Question.topic_id == cells).limit(3)))
        await s.execute(
            update(Question).where(Question.topic_id == cells, Question.id.not_in(keep))
            .values(higher_only=True)
        )  # fmt: skip
        await s.commit()
    state = await start_quiz(player, app, include_higher=False)
    assert state["progress"]["total"] == 3


async def test_bad_answers_are_rejected(app, player):
    state = await start_quiz(player, app)
    url = f"/api/play/{state['session_id']}/answer"
    resp = await player.post(url, json={"position": 0, "response": {"nonsense": True}})
    assert resp.status_code == 422 and resp.json()["code"] == "bad_response"
    served = state["question"]
    if served["type"] == "mcq":
        resp = await player.post(url, json={"position": 0, "response": {"option_id": "zz"}})
        assert resp.status_code == 422


async def test_double_submit_returns_the_same_result(app, player):
    state = await start_quiz(player, app)
    served = state["question"]
    body = {"position": 0, "response": await response_for(app, served, correct=False)}
    url = f"/api/play/{state['session_id']}/answer"
    first = (await player.post(url, json=body)).json()
    # Retry with a *different* answer: still the original marking, nothing double-counted.
    retry_body = {"position": 0, "response": await response_for(app, served, correct=True)}
    second = (await player.post(url, json=retry_body)).json()
    assert first["feedback"] == second["feedback"]
    assert second["progress"] == {"answered": 1, "correct": 0, "total": 10}


async def test_cannot_answer_ahead(app, player):
    state = await start_quiz(player, app)
    resp = await player.post(
        f"/api/play/{state['session_id']}/answer",
        json={"position": 5, "response": {"text": "x"}},
    )
    assert resp.status_code == 409


async def test_games_are_private(app, player):
    state = await start_quiz(player, app)
    async with open_client(app) as other:
        await signup(other, "CosmicPanda11")
        assert (await other.get(f"/api/play/{state['session_id']}")).status_code == 404


async def test_ending_early_gives_a_partial_summary(app, player):
    state = await start_quiz(player, app)
    await play_through(player, app, state, stop_after=3)
    summary = (await player.post(f"/api/play/{state['session_id']}/end")).json()
    assert summary["status"] == "abandoned" and summary["answered"] == 3


async def test_topic_without_questions(app, player):
    resp = await player.post(
        "/api/play",
        json={"mode": "quiz", "topic_id": await topic_id(app, "maths-algebra"),
              "subject_id": await subject_id(app, "mathematics")},
    )  # fmt: skip
    assert resp.status_code == 409 and resp.json()["code"] == "no_questions"


async def test_topic_must_belong_to_subject(app, player):
    resp = await player.post(
        "/api/play",
        json={"mode": "quiz", "topic_id": await topic_id(app, "sci-bio-cells"),
              "subject_id": await subject_id(app, "history")},
    )  # fmt: skip
    assert resp.status_code == 404


async def test_quiz_needs_a_topic(player):
    resp = await player.post("/api/play", json={"mode": "quiz"})
    assert resp.status_code == 422


async def test_playing_needs_login(app, client):
    await seed_content(app)
    resp = await client.post("/api/play", json={"mode": "review"})
    assert resp.status_code == 401
