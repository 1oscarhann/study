"""The shipped topic list and demo questions load cleanly and meet the quality bar."""

from collections import Counter

import pytest
from sqlalchemy import func, select

from app.models import Question, Subject, SubjectTopic, Topic
from app.services.content import (
    SeedError,
    SeedQuestionFile,
    apply_catalog,
    apply_seed_questions,
    load_catalog,
    load_question_files,
)

FILES = load_question_files()


async def _seed(db):
    await apply_catalog(db, load_catalog())
    return await apply_seed_questions(db, FILES)


async def test_seed_loads_and_is_idempotent(db_session):
    first = await _seed(db_session)
    assert first.created == 75 and first.skipped == 0
    second = await _seed(db_session)
    assert second.created == 0 and second.skipped == 75
    assert await db_session.scalar(select(func.count()).select_from(Subject)) == 24
    assert await db_session.scalar(select(func.count()).select_from(Question)) == 75


async def test_french_and_german_get_the_cloned_tree(db_session):
    await _seed(db_session)
    for slug in ("french", "german"):
        subject = await db_session.scalar(select(Subject).where(Subject.slug == slug))
        count = await db_session.scalar(
            select(func.count())
            .select_from(SubjectTopic)
            .where(SubjectTopic.subject_id == subject.id)
        )
        assert count == 5


async def test_demo_topics_get_learn_more_links(db_session):
    await _seed(db_session)
    for f in FILES:
        topic = await db_session.scalar(select(Topic).where(Topic.slug == f.topic))
        assert topic.learn_more_url and topic.learn_more_url.startswith("https://")


@pytest.mark.parametrize("f", FILES, ids=lambda f: f.topic)
def test_each_demo_topic_is_quiz_and_boss_ready(f: SeedQuestionFile):
    types = Counter(q.type for q in f.questions)
    assert set(types) == {"mcq", "fill_blank", "order", "match"}, "all four question types"
    assert sum(q.is_core for q in f.questions) >= 8, "enough core questions to gate a boss"
    assert sum(q.difficulty >= 2 for q in f.questions) >= 12, "enough harder ones for a boss"
    assert sum(not q.triple_only for q in f.questions) >= 10, "a full quiz for Combined Science"
    assert all(q.subtopic for q in f.questions), "every question tagged with a subtopic"


async def test_duplicate_prompts_in_a_file_are_refused(db_session):
    await apply_catalog(db_session, load_catalog())
    q = {"type": "fill_blank", "prompt": "The ___ is a test.", "accepted": ["x"],
         "explanation": "Test."}  # fmt: skip
    bad = SeedQuestionFile.model_validate({"topic": "sci-bio-cells", "questions": [q, q]})
    with pytest.raises(SeedError, match="duplicate"):
        await apply_seed_questions(db_session, [bad])


async def test_unknown_subtopics_are_refused(db_session):
    await apply_catalog(db_session, load_catalog())
    q = {"type": "fill_blank", "prompt": "The ___ is a test.", "accepted": ["x"],
         "explanation": "Test.", "subtopic": "Not a real subtopic"}  # fmt: skip
    bad = SeedQuestionFile.model_validate({"topic": "sci-bio-cells", "questions": [q]})
    with pytest.raises(SeedError, match="unknown subtopic"):
        await apply_seed_questions(db_session, [bad])
