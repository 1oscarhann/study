"""Spaced repetition through the API, review mode, weak spots, home, catalogue, exams."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import PlaySession, QuestionReview
from tests.api.helpers import play_through, seed_content, start_quiz, subject_id, topic_id
from tests.conftest import open_client, signup

pytestmark = pytest.mark.asyncio
TODAY = date(2026, 11, 2)  # the test clock's default date


@pytest.fixture
async def player(app, client):
    await seed_content(app)
    await signup(client)
    return client


async def _summary(client):
    return (await client.get("/api/reviews/summary")).json()


# --- spaced repetition ----------------------------------------------------------------------


async def test_wrong_answers_come_back_tomorrow_then_3_7_14_days(app, player, clock):
    state = await start_quiz(player, app)
    results = await play_through(player, app, state, pattern=[False])
    for r in results:
        assert r["feedback"]["review"] == {
            "box": 1,
            "due_on": str(TODAY + timedelta(days=1)),
            "days_until_due": 1,
        }
    assert await _summary(player) == {"today": 0, "this_week": 10}
    nothing = await player.post("/api/play", json={"mode": "review"})
    assert nothing.status_code == 409 and nothing.json()["code"] == "nothing_due"

    # Each review answered correctly pushes them further out: 3, then 7, then 14 days.
    for gap in (3, 7, 14):
        clock.advance(days=1 if gap == 3 else {7: 3, 14: 7}[gap])
        assert (await _summary(player))["today"] == 10
        review = (await player.post("/api/play", json={"mode": "review"})).json()
        assert review["mode"] == "review" and review["progress"]["total"] == 10
        done = await play_through(player, app, review)
        assert {r["feedback"]["review"]["days_until_due"] for r in done} == {gap}
        assert (await _summary(player))["today"] == 0


async def test_first_time_correct_gets_a_two_week_check_in(app, player):
    state = await start_quiz(player, app)
    results = await play_through(player, app, state)
    assert {(r["feedback"]["review"]["box"], r["feedback"]["review"]["days_until_due"])
            for r in results} == {(4, 14)}  # fmt: skip


async def test_getting_a_review_wrong_resets_it(app, player, clock):
    state = await start_quiz(player, app)
    await play_through(player, app, state, pattern=[False])
    clock.advance(days=1)
    review = (await player.post("/api/play", json={"mode": "review"})).json()
    done = await play_through(player, app, review, pattern=[False])
    assert {r["feedback"]["review"]["box"] for r in done} == {1}


async def test_quick_quiz_puts_due_questions_first(app, player, clock):
    first = await start_quiz(player, app)
    await play_through(player, app, first, pattern=[False, True])  # 5 wrong → due tomorrow
    async with app.state.db.sessionmaker() as s:
        wrong_ids = set(
            await s.scalars(select(QuestionReview.question_id).where(QuestionReview.box == 1))
        )
    assert len(wrong_ids) == 5
    clock.advance(days=1)
    second = await start_quiz(player, app)
    async with app.state.db.sessionmaker() as s:
        picked = set((await s.get(PlaySession, second["session_id"])).question_ids)
    assert wrong_ids <= picked


async def test_reviews_mix_topics(app, player, clock):
    await play_through(player, app, await start_quiz(player, app), pattern=[False])
    await play_through(
        player, app, await start_quiz(player, app, topic="hist-weimar-nazi", subject="history"),
        pattern=[False],
    )  # fmt: skip
    clock.advance(days=1)
    review = (await player.post("/api/play", json={"mode": "review"})).json()
    assert review["progress"]["total"] == 20  # capped at 20 per review session
    assert review["topic"] is None


# --- weak spots + home ----------------------------------------------------------------------


async def test_weak_spots_worst_first(app, player):
    await play_through(player, app, await start_quiz(player, app), pattern=[False, False, True])
    await play_through(
        player, app, await start_quiz(player, app, topic="sci-chem-atomic", subject="chemistry")
    )
    hist = await start_quiz(player, app, topic="hist-weimar-nazi", subject="history")
    await play_through(player, app, hist, stop_after=3)

    spots = (await player.get("/api/progress/weak-spots")).json()
    assert spots["min_answers"] == 5 and spots["window_days"] == 60
    names = [(t["name"], t["enough_data"]) for t in spots["topics"]]
    assert names == [
        ("Cell biology", True),
        ("Atomic structure and the periodic table", True),
        ("Paper 3: Weimar and Nazi Germany, 1918-39", False),
    ]
    cells = spots["topics"][0]
    assert cells["subject_name"] == "Biology"
    assert cells["subject_id"] == await subject_id(app, "biology")
    assert (cells["answered"], cells["correct"]) == (10, 3)


async def test_weak_spots_remember_combined_science(app, player):
    await play_through(
        player, app, await start_quiz(player, app, subject="combined-science-trilogy"),
        pattern=[False],
    )  # fmt: skip
    spot = (await player.get("/api/progress/weak-spots")).json()["topics"][0]
    assert spot["name"] == "Biology 1: Cell biology"
    assert spot["subject_name"] == "Combined Science: Trilogy"


async def test_home_quick_launch_and_due_reviews(app, player, clock):
    empty = (await player.get("/api/home")).json()
    assert empty["recent_topics"] == [] and empty["weakest_topic"] is None
    assert empty["due_reviews"] == {"today": 0, "this_week": 0}
    assert empty["user"]["username"] == "SwiftOtter42" and empty["user"]["year_group"] == 10

    await play_through(player, app, await start_quiz(player, app), pattern=[False])
    clock.advance(minutes=5)
    await play_through(
        player, app, await start_quiz(player, app, topic="sci-chem-atomic", subject="chemistry")
    )
    home = (await player.get("/api/home")).json()
    assert [t["name"] for t in home["recent_topics"]] == [
        "Atomic structure and the periodic table",
        "Cell biology",
    ]
    assert home["weakest_topic"]["name"] == "Cell biology"
    assert home["due_reviews"] == {"today": 0, "this_week": 10}


# --- catalogue ------------------------------------------------------------------------------


async def test_subject_list_shows_whats_playable(app, player):
    subjects = {s["slug"]: s for s in (await player.get("/api/subjects")).json()["subjects"]}
    assert len(subjects) == 24
    assert subjects["biology"]["playable_topic_count"] == 1
    assert subjects["combined-science-trilogy"]["playable_topic_count"] == 2
    assert subjects["mathematics"]["playable_topic_count"] == 0
    assert subjects["mathematics"]["topic_count"] == 6


async def test_subject_detail_counts_respect_combined_science(app, player):
    bio = (await player.get(f"/api/subjects/{await subject_id(app, 'biology')}")).json()
    combined = (
        await player.get(f"/api/subjects/{await subject_id(app, 'combined-science-trilogy')}")
    ).json()
    bio_cells = next(t for t in bio["topics"] if t["slug"] == "sci-bio-cells")
    comb_cells = next(t for t in combined["topics"] if t["slug"] == "sci-bio-cells")
    assert (bio_cells["question_count"], comb_cells["question_count"]) == (25, 22)
    assert bio_cells["spec_ref"] == "4.1"


async def test_topic_detail(app, player):
    cells = await topic_id(app, "sci-bio-cells")
    combined = await subject_id(app, "combined-science-trilogy")
    detail = (await player.get(f"/api/topics/{cells}?subject_id={combined}")).json()
    assert detail["name"] == "Biology 1: Cell biology"
    assert detail["question_count"] == 22
    assert "Culturing microorganisms" not in [s["name"] for s in detail["subtopics"]]
    assert detail["learn_more_url"].startswith("https://")
    assert detail["stats"] == {"answered": 0, "correct": 0, "accuracy": None}


# --- exams ----------------------------------------------------------------------------------


async def test_exam_countdowns(app, player, clock):
    bio = await subject_id(app, "biology")
    hist = await subject_id(app, "history")
    later = await player.post("/api/exams", json={"subject_id": hist, "exam_date": "2027-06-05"})
    soon = await player.post(
        "/api/exams", json={"subject_id": bio, "exam_date": "2027-05-14", "label": "Paper 1"}
    )
    assert later.status_code == soon.status_code == 201
    assert soon.json()["days_left"] == (date(2027, 5, 14) - TODAY).days

    exams = (await player.get("/api/exams")).json()["exams"]
    assert [e["subject_name"] for e in exams] == ["Biology", "History"]  # soonest first
    assert (await player.get("/api/home")).json()["exams"][0]["label"] == "Paper 1"

    clock.set("2027-05-20T09:00:00+00:00")  # past exams drop off
    await player.post("/api/auth/login", json={"username": "SwiftOtter42",
                                               "password": "correct horse battery"})  # fmt: skip
    assert [e["subject_name"] for e in (await player.get("/api/exams")).json()["exams"]] == [
        "History"
    ]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"exam_date": "2026-10-01"}, "exam_date"),
        ({"exam_date": "2030-01-01"}, "exam_date"),
        ({"label": "<script>alert(1)</script>"}, "label"),
        ({"subject_id": 999999}, "subject_id"),
    ],
)
async def test_exam_validation(app, player, payload, field):
    body = {"subject_id": await subject_id(app, "biology"), "exam_date": "2027-05-14", **payload}
    resp = await player.post("/api/exams", json=body)
    assert resp.status_code == 422 and resp.json()["field"] == field


async def test_exams_are_private(app, player):
    exam = (
        await player.post(
            "/api/exams",
            json={"subject_id": await subject_id(app, "biology"), "exam_date": "2027-05-14"},
        )
    ).json()
    async with open_client(app) as other:
        await signup(other, "CosmicPanda11")
        assert (await other.get("/api/exams")).json()["exams"] == []
        assert (await other.delete(f"/api/exams/{exam['id']}")).status_code == 404
    assert (await player.delete(f"/api/exams/{exam['id']}")).status_code == 204
