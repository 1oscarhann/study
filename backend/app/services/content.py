"""Loading official content: the subject/topic catalogue and seed questions.

Both are idempotent, so they're safe to run on every deploy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.catalog import SLUG_RE, Catalog, ImportFile, build_catalog, merge_files
from app.domain.questions import QuestionDraft, to_storage
from app.models import Question, Subject, SubjectTopic, Topic
from app.models.enums import QuestionOrigin, QuestionStatus, VerificationStatus

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
TOPIC_FILES = (SEED_DIR / "gcse_topics.json", SEED_DIR / "mfl_topics.json")
QUESTION_DIR = SEED_DIR / "questions"


@dataclass
class CatalogStats:
    subjects_created: int = 0
    subjects_updated: int = 0
    topics_created: int = 0
    topics_updated: int = 0
    links_created: int = 0
    links_updated: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def load_catalog(paths: tuple[Path, ...] | list[Path] = TOPIC_FILES) -> Catalog:
    files = [ImportFile.model_validate(json.loads(p.read_text())) for p in paths]
    return build_catalog(merge_files(files))


async def apply_catalog(db: AsyncSession, catalog: Catalog) -> CatalogStats:
    """Upsert subjects, topics and subject↔topic links. Never deletes anything."""
    stats = CatalogStats()

    subjects = {s.slug: s for s in await db.scalars(select(Subject))}
    for cs in catalog.subjects:
        values = {
            "name": cs.name,
            "qualification": cs.qualification,
            "exam_board": cs.exam_board,
            "spec_code": cs.spec_code,
            "spec_url": cs.spec_url,
            "spec_url_alt": cs.spec_url_alt,
            "board_confidence": cs.board_confidence,
            "admin_notes": cs.admin_notes,
            "sort_order": cs.sort_order,
        }
        if (row := subjects.get(cs.slug)) is None:
            row = Subject(slug=cs.slug, **values)
            db.add(row)
            subjects[cs.slug] = row
            stats.subjects_created += 1
        elif any(getattr(row, k) != v for k, v in values.items()):
            for k, v in values.items():
                setattr(row, k, v)
            stats.subjects_updated += 1

    topics = {t.slug: t for t in await db.scalars(select(Topic))}
    for ct in catalog.topics.values():
        subtopics = [asdict(s) for s in ct.subtopics]
        if (row := topics.get(ct.slug)) is None:
            row = Topic(slug=ct.slug, name=ct.name, subtopics=subtopics)
            db.add(row)
            topics[ct.slug] = row
            stats.topics_created += 1
        elif row.name != ct.name or row.subtopics != subtopics:
            row.name, row.subtopics = ct.name, subtopics
            stats.topics_updated += 1
    await db.flush()

    links = {(lnk.subject_id, lnk.topic_id): lnk for lnk in await db.scalars(select(SubjectTopic))}
    for cl in catalog.links:
        key = (subjects[cl.subject_slug].id, topics[cl.topic_slug].id)
        values = {
            "display_name": cl.display_name,
            "spec_ref": cl.spec_ref,
            "sort_order": cl.sort_order,
            "excludes_triple_only": cl.excludes_triple_only,
        }
        if (link := links.get(key)) is None:
            db.add(SubjectTopic(subject_id=key[0], topic_id=key[1], **values))
            stats.links_created += 1
        elif any(getattr(link, k) != v for k, v in values.items()):
            for k, v in values.items():
                setattr(link, k, v)
            stats.links_updated += 1
    await db.flush()
    return stats


class SeedQuestionFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(pattern=SLUG_RE)
    learn_more_url: HttpUrl | None = None
    questions: list[QuestionDraft]


@dataclass
class QuestionSeedStats:
    created: int = 0
    skipped: int = 0
    topics: list[str] = field(default_factory=list)


class SeedError(ValueError):
    pass


def load_question_files(directory: Path = QUESTION_DIR) -> list[SeedQuestionFile]:
    return [
        SeedQuestionFile.model_validate(json.loads(p.read_text()))
        for p in sorted(directory.glob("*.json"))
    ]


async def apply_seed_questions(
    db: AsyncSession, files: list[SeedQuestionFile]
) -> QuestionSeedStats:
    """Add official, hand-checked questions. Existing prompts are left alone."""
    stats = QuestionSeedStats()
    for f in files:
        topic = await db.scalar(select(Topic).where(Topic.slug == f.topic))
        if topic is None:
            raise SeedError(f"Unknown topic {f.topic!r}; import topics first.")
        if f.learn_more_url and not topic.learn_more_url:
            topic.learn_more_url = str(f.learn_more_url)  # never overwrite an admin's choice

        prompts = [d.prompt for d in f.questions]
        if dupes := {x for x in prompts if prompts.count(x) > 1}:
            raise SeedError(f"{f.topic}: duplicate prompts {sorted(dupes)}")
        known_subtopics = {s["name"] for s in topic.subtopics}
        existing = set(
            await db.scalars(
                select(Question.prompt).where(
                    Question.topic_id == topic.id, Question.set_id.is_(None)
                )
            )
        )
        for draft in f.questions:
            if draft.subtopic and known_subtopics and draft.subtopic not in known_subtopics:
                raise SeedError(f"{f.topic}: unknown subtopic {draft.subtopic!r}")
            if draft.prompt in existing:
                stats.skipped += 1
                continue
            stored = to_storage(draft)
            db.add(
                Question(
                    topic_id=topic.id,
                    type=stored.type,
                    prompt=draft.prompt,
                    content=stored.content,
                    answer=stored.answer,
                    explanation=draft.explanation,
                    subtopic=draft.subtopic,
                    difficulty=draft.difficulty,
                    is_core=draft.is_core,
                    higher_only=draft.higher_only,
                    triple_only=draft.triple_only,
                    case_sensitive=getattr(draft, "case_sensitive", False),
                    status=QuestionStatus.LIVE,
                    origin=QuestionOrigin.SEED,
                    verification=VerificationStatus.PASSED,
                )
            )
            existing.add(draft.prompt)
            stats.created += 1
        stats.topics.append(f.topic)
    await db.flush()
    return stats
