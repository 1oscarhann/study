"""Parse the topic seed file (backend/seed/gcse_topics.json) into subjects, topics and links.

Pure functions only. The DB writer that upserts these arrives with the topic admin
tools in Phase 3. Rules:

- Topic `id`s are stable slugs. The same slug can appear under several subjects
  (Combined Science reuses the separate sciences' topics); it becomes ONE topic with
  one link per subject, each link keeping its own display name and spec ref.
- At most one entry per slug may define subtopics; that entry also supplies the
  topic's canonical name. Two entries defining subtopics for one slug is an error.
- Subtopic suffixes "(higher)" and "(triple only)" become flags and are stripped.
- Links under a Combined Science subject exclude triple-only content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

SLUG_RE = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_FLAG_RE = re.compile(r"\s*\((higher|triple only)\)\s*$", re.IGNORECASE)


class ImportTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SLUG_RE, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    spec_ref: str | None = Field(default=None, max_length=40)
    subtopics: list[str] = Field(default_factory=list)


class ImportSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=120)
    qualification: str = Field(min_length=1, max_length=80)
    board: str = Field(min_length=1, max_length=80)
    spec_code: str | None = Field(default=None, max_length=120)
    spec_url: HttpUrl | None = None
    spec_url_alt: HttpUrl | None = None
    confidence: str = Field(pattern="^(stated|inferred)$")
    notes: str | None = None
    excludes_triple_only: bool | None = None  # optional override; else inferred from name
    topics: list[ImportTopic]


class ImportFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: dict[str, object] = Field(default_factory=dict)
    subjects: list[ImportSubject]


@dataclass(frozen=True)
class Subtopic:
    name: str
    higher_only: bool = False
    triple_only: bool = False


@dataclass
class CatalogSubject:
    slug: str
    name: str
    qualification: str
    exam_board: str
    spec_code: str | None
    spec_url: str | None
    spec_url_alt: str | None
    board_confidence: str
    admin_notes: str | None
    sort_order: int


@dataclass
class CatalogTopic:
    slug: str
    name: str
    subtopics: list[Subtopic] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogLink:
    subject_slug: str
    topic_slug: str
    display_name: str
    spec_ref: str | None
    sort_order: int
    excludes_triple_only: bool


@dataclass
class Catalog:
    subjects: list[CatalogSubject]
    topics: dict[str, CatalogTopic]
    links: list[CatalogLink]


class CatalogError(ValueError):
    pass


def merge_files(files: list[ImportFile]) -> ImportFile:
    """Combine several topic files. A subject that appears in more than one file (same
    name, qualification and board) gets its topic lists joined; the first file's details win.
    """
    merged: dict[tuple[str, str, str], ImportSubject] = {}
    for f in files:
        for subject in f.subjects:
            key = (subject.subject, subject.qualification, subject.board)
            if key not in merged:
                merged[key] = subject.model_copy(deep=True)
                continue
            existing = merged[key]
            notes = [n for n in (existing.notes, subject.notes) if n]
            merged[key] = existing.model_copy(
                update={
                    "topics": [*existing.topics, *subject.topics],
                    "notes": " ".join(notes) or None,
                }
            )
    return ImportFile(subjects=list(merged.values()))


def parse_subtopic(raw: str) -> Subtopic:
    name = raw.strip()
    higher = triple = False
    while match := _FLAG_RE.search(name):
        flag = match.group(1).lower()
        higher = higher or flag == "higher"
        triple = triple or flag == "triple only"
        name = name[: match.start()].rstrip()
    if not name:
        raise CatalogError(f"Subtopic has no name: {raw!r}")
    return Subtopic(name=name, higher_only=higher, triple_only=triple)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise CatalogError(f"Can't make a slug from {text!r}")
    return slug


def subject_slug(entry: ImportSubject, taken: set[str]) -> str:
    """Slug from the subject name; add the qualification only when names clash."""
    base = slugify(entry.subject)
    if base not in taken:
        return base
    candidate = slugify(f"{entry.subject} {entry.qualification}")
    if candidate in taken:
        raise CatalogError(f"Duplicate subject: {entry.subject} ({entry.qualification})")
    return candidate


def build_catalog(data: ImportFile) -> Catalog:
    subjects: list[CatalogSubject] = []
    topics: dict[str, CatalogTopic] = {}
    defined_by: dict[str, str] = {}  # topic slug -> subject that defined its subtopics
    links: list[CatalogLink] = []
    taken: set[str] = set()

    for s_index, entry in enumerate(data.subjects):
        slug = subject_slug(entry, taken)
        taken.add(slug)
        subjects.append(
            CatalogSubject(
                slug=slug,
                name=entry.subject,
                qualification=entry.qualification,
                exam_board=entry.board,
                spec_code=entry.spec_code,
                spec_url=str(entry.spec_url) if entry.spec_url else None,
                spec_url_alt=str(entry.spec_url_alt) if entry.spec_url_alt else None,
                board_confidence=entry.confidence,
                admin_notes=entry.notes,
                sort_order=s_index,
            )
        )
        excludes_triple = (
            entry.excludes_triple_only
            if entry.excludes_triple_only is not None
            else "combined science" in entry.subject.lower()
        )

        seen_in_subject: set[str] = set()
        for t_index, t in enumerate(entry.topics):
            if t.id in seen_in_subject:
                raise CatalogError(f"Topic {t.id!r} listed twice under {entry.subject}")
            seen_in_subject.add(t.id)

            topic = topics.setdefault(t.id, CatalogTopic(slug=t.id, name=t.name))
            if t.subtopics:
                if t.id in defined_by:
                    raise CatalogError(
                        f"Topic {t.id!r} has subtopics under both "
                        f"{defined_by[t.id]} and {entry.subject}"
                    )
                defined_by[t.id] = entry.subject
                topic.name = t.name
                topic.subtopics = [parse_subtopic(s) for s in t.subtopics]

            links.append(
                CatalogLink(
                    subject_slug=slug,
                    topic_slug=t.id,
                    display_name=t.name,
                    spec_ref=t.spec_ref,
                    sort_order=t_index,
                    excludes_triple_only=excludes_triple,
                )
            )

    return Catalog(subjects=subjects, topics=topics, links=links)
