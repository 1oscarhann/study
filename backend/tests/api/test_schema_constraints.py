"""Rules the database itself enforces, so app bugs can't break them."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import (
    Cosmetic,
    Question,
    Subject,
    SubjectTopic,
    Topic,
    User,
    UserCosmetic,
    UserEquipped,
)
from app.models.enums import (
    CosmeticSlot,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
    UnlockType,
)


def _user(username: str = "SwiftOtter42") -> User:
    return User(
        username=username,
        password_hash="x",
        recovery_code_hash="x",
        cohort_year=2023,
    )


async def _topic(db) -> Topic:
    subject = Subject(slug="biology", name="Biology", qualification="GCSE", exam_board="AQA")
    topic = Topic(slug="sci-bio-cells", name="Cell biology")
    db.add_all([subject, topic])
    await db.flush()
    db.add(SubjectTopic(subject_id=subject.id, topic_id=topic.id, display_name="Cell biology"))
    await db.flush()
    return topic


def _question(topic: Topic, **overrides) -> Question:
    values = {
        "topic_id": topic.id,
        "type": QuestionType.MCQ,
        "prompt": "Which organelle is the site of aerobic respiration?",
        "content": {
            "options": [{"id": "a", "text": "Mitochondria"}, {"id": "b", "text": "Ribosome"}]
        },
        "answer": {"option_id": "a"},
        "explanation": "Aerobic respiration happens in the mitochondria.",
        "origin": QuestionOrigin.SEED,
        "status": QuestionStatus.LIVE,
    }
    values.update(overrides)
    return Question(**values)


async def test_ai_question_cannot_go_live_without_approval(db_session):
    topic = await _topic(db_session)
    db_session.add(_question(topic, origin=QuestionOrigin.AI, status=QuestionStatus.LIVE))
    with pytest.raises(IntegrityError, match="ai_live_requires_approval"):
        await db_session.flush()


async def test_ai_question_can_go_live_once_approved(db_session):
    topic = await _topic(db_session)
    q = _question(
        topic, origin=QuestionOrigin.AI, status=QuestionStatus.LIVE, approved_at=datetime.now(UTC)
    )
    db_session.add(q)
    await db_session.flush()
    assert q.id is not None


async def test_ai_draft_is_allowed_unapproved(db_session):
    topic = await _topic(db_session)
    db_session.add(_question(topic, origin=QuestionOrigin.AI, status=QuestionStatus.DRAFT))
    await db_session.flush()


async def test_explanation_must_be_one_short_line(db_session):
    topic = await _topic(db_session)
    db_session.add(_question(topic, explanation="x" * 201))
    with pytest.raises(DBAPIError):  # column length or CHECK, either way it's refused
        await db_session.flush()


async def test_usernames_are_unique_case_insensitively(db_session):
    db_session.add(_user("SwiftOtter42"))
    await db_session.flush()
    db_session.add(_user("swiftotter42"))
    with pytest.raises(IntegrityError, match="uq_users_username_lower"):
        await db_session.flush()


@pytest.mark.parametrize("bad", ["ab", "has space", "emoji😀", "dash-name"])
async def test_username_format_is_enforced(db_session, bad):
    db_session.add(_user(bad))
    with pytest.raises(IntegrityError, match="username_format"):
        await db_session.flush()


async def test_username_max_length_is_enforced(db_session):
    db_session.add(_user("a" * 21))
    with pytest.raises(DBAPIError):
        await db_session.flush()


async def _cosmetic(db, key: str, slot: CosmeticSlot) -> Cosmetic:
    c = Cosmetic(key=key, slot=slot, name=key, unlock_type=UnlockType.DEFAULT)
    db.add(c)
    await db.flush()
    return c


async def test_cannot_equip_a_cosmetic_you_dont_own(db_session):
    user = _user()
    db_session.add(user)
    hat = await _cosmetic(db_session, "party-hat", CosmeticSlot.HAT)
    db_session.add(UserEquipped(user_id=user.id, slot=CosmeticSlot.HAT, cosmetic_id=hat.id))
    with pytest.raises(IntegrityError, match="fk_user_equipped_owned"):
        await db_session.flush()


async def test_cannot_equip_a_cosmetic_in_the_wrong_slot(db_session):
    user = _user()
    db_session.add(user)
    hat = await _cosmetic(db_session, "party-hat", CosmeticSlot.HAT)
    db_session.add(UserCosmetic(user_id=user.id, cosmetic_id=hat.id))
    await db_session.flush()
    db_session.add(UserEquipped(user_id=user.id, slot=CosmeticSlot.FRAME, cosmetic_id=hat.id))
    with pytest.raises(IntegrityError, match="fk_user_equipped_slot_matches"):
        await db_session.flush()


async def test_equipping_an_owned_cosmetic_works(db_session):
    user = _user()
    db_session.add(user)
    hat = await _cosmetic(db_session, "party-hat", CosmeticSlot.HAT)
    db_session.add(UserCosmetic(user_id=user.id, cosmetic_id=hat.id))
    await db_session.flush()
    db_session.add(UserEquipped(user_id=user.id, slot=CosmeticSlot.HAT, cosmetic_id=hat.id))
    await db_session.flush()
