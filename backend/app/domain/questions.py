"""Question formats: how questions are written, stored, served and displayed.

Authoring ("draft") format — what seed files, admins and (later) the AI produce:

    mcq         prompt, correct, wrong[2-4]
    fill_blank  prompt with exactly one ___ , accepted[1-6], case_sensitive
    order       prompt, items[3-6] in the correct order
    match       prompt, pairs[3-6] of [term, definition]

Storage splits that into `content` (what a player may see) and `answer` (server-only).
Every option/item gets an opaque id, so shuffling for display never touches the answer.

The validators here are the deterministic "code checks" in the accuracy pipeline: they
run on every question regardless of where it came from.
"""

from __future__ import annotations

import random
import re
import string
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import QuestionType

BLANK = "___"
_BANNED_OPTIONS = re.compile(r"\b(all|none|both|neither) of (the|these) (above|options)\b", re.I)

Text = Annotated[str, Field(min_length=1, max_length=160)]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _ids(n: int, prefix: str = "") -> list[str]:
    return [f"{prefix}{c}" for c in string.ascii_lowercase[:n]]


class _DraftBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prompt: str = Field(min_length=5, max_length=500)
    explanation: str = Field(min_length=1, max_length=200)
    subtopic: str | None = Field(default=None, max_length=200)
    difficulty: int = Field(default=2, ge=1, le=3)
    is_core: bool = False
    higher_only: bool = False
    triple_only: bool = False


class McqDraft(_DraftBase):
    type: Literal["mcq"] = "mcq"
    correct: Text
    wrong: list[Text] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def _check(self) -> McqDraft:
        options = [self.correct, *self.wrong]
        if len({_norm(o) for o in options}) != len(options):
            raise ValueError("Options must all be different (and the right answer can't repeat).")
        if any(_BANNED_OPTIONS.search(o) for o in options):
            raise ValueError("Don't use 'all/none of the above' style options.")
        return self


class FillBlankDraft(_DraftBase):
    type: Literal["fill_blank"] = "fill_blank"
    accepted: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(
        min_length=1, max_length=6
    )
    case_sensitive: bool = False

    @field_validator("prompt")
    @classmethod
    def _one_blank(cls, prompt: str) -> str:
        if prompt.count(BLANK) != 1:
            raise ValueError(f"A fill-the-blank prompt needs exactly one {BLANK}.")
        return prompt

    @model_validator(mode="after")
    def _distinct(self) -> FillBlankDraft:
        if len({_norm(a) for a in self.accepted}) != len(self.accepted):
            raise ValueError("Accepted answers must be different from each other.")
        return self


class OrderDraft(_DraftBase):
    type: Literal["order"] = "order"
    items: list[Text] = Field(min_length=3, max_length=6)  # in the CORRECT order

    @model_validator(mode="after")
    def _distinct(self) -> OrderDraft:
        if len({_norm(i) for i in self.items}) != len(self.items):
            raise ValueError("Items to order must all be different.")
        return self


class MatchDraft(_DraftBase):
    type: Literal["match"] = "match"
    pairs: list[tuple[Text, Text]] = Field(min_length=3, max_length=6)

    @model_validator(mode="after")
    def _distinct(self) -> MatchDraft:
        lefts = [_norm(a) for a, _ in self.pairs]
        rights = [_norm(b) for _, b in self.pairs]
        if len(set(lefts)) != len(lefts) or len(set(rights)) != len(rights):
            raise ValueError("Each term and each definition must be different.")
        return self


QuestionDraft = Annotated[
    McqDraft | FillBlankDraft | OrderDraft | MatchDraft, Field(discriminator="type")
]


class Stored(BaseModel):
    type: QuestionType
    content: dict[str, Any]
    answer: dict[str, Any]


def to_storage(draft: McqDraft | FillBlankDraft | OrderDraft | MatchDraft) -> Stored:
    """Split a draft into player-visible content and the server-only answer."""
    # Stored order is scrambled (deterministically, so re-seeding is stable) on top of the
    # per-attempt shuffle, so nothing ever depends on "the right answer is listed first".
    rng = random.Random(draft.prompt)
    match draft:
        case McqDraft():
            texts = [draft.correct, *draft.wrong]
            rng.shuffle(texts)
            options = [{"id": i, "text": t} for i, t in zip(_ids(len(texts)), texts, strict=True)]
            correct_id = next(o["id"] for o in options if o["text"] == draft.correct)
            return Stored(
                type=QuestionType.MCQ,
                content={"options": options},
                answer={"option_id": correct_id},
            )
        case FillBlankDraft():
            return Stored(
                type=QuestionType.FILL_BLANK, content={}, answer={"accepted": draft.accepted}
            )
        case OrderDraft():
            ids = _ids(len(draft.items))
            items = [{"id": i, "text": t} for i, t in zip(ids, draft.items, strict=True)]
            correct_order = [it["id"] for it in items]
            rng.shuffle(items)
            return Stored(
                type=QuestionType.ORDER, content={"items": items}, answer={"order": correct_order}
            )
        case MatchDraft():
            left = [
                {"id": i, "text": a}
                for i, (a, _) in zip(_ids(len(draft.pairs), "l"), draft.pairs, strict=True)
            ]
            right = [
                {"id": i, "text": b}
                for i, (_, b) in zip(_ids(len(draft.pairs), "r"), draft.pairs, strict=True)
            ]
            pairs = {lft["id"]: rgt["id"] for lft, rgt in zip(left, right, strict=True)}
            rng.shuffle(right)
            return Stored(
                type=QuestionType.MATCH,
                content={"left": left, "right": right},
                answer={"pairs": pairs},
            )
    raise TypeError(f"Unknown draft: {draft!r}")


# --- Serving ----------------------------------------------------------------------------


def shuffle_for_display(
    qtype: QuestionType, content: dict[str, Any], rng: random.Random
) -> dict[str, Any]:
    """A fresh per-attempt order for whatever the player sees. Never includes the answer."""

    def shuffled(items: list[dict[str, str]]) -> list[dict[str, str]]:
        copy = [dict(i) for i in items]
        rng.shuffle(copy)
        return copy

    match qtype:
        case QuestionType.MCQ:
            return {"options": shuffled(content["options"])}
        case QuestionType.ORDER:
            return {"items": shuffled(content["items"])}
        case QuestionType.MATCH:
            return {"left": shuffled(content["left"]), "right": shuffled(content["right"])}
        case QuestionType.FILL_BLANK:
            return {}
    raise ValueError(f"Unknown question type {qtype}")


def correct_answer_display(
    qtype: QuestionType, content: dict[str, Any], answer: dict[str, Any]
) -> dict[str, Any]:
    """What to show after answering: the right answer in a form the UI can render."""
    match qtype:
        case QuestionType.MCQ:
            option = next(o for o in content["options"] if o["id"] == answer["option_id"])
            return {"option_id": option["id"], "text": option["text"]}
        case QuestionType.FILL_BLANK:
            return {"text": answer["accepted"][0], "also_accepted": answer["accepted"][1:]}
        case QuestionType.ORDER:
            by_id = {i["id"]: i["text"] for i in content["items"]}
            return {"order": answer["order"], "texts": [by_id[i] for i in answer["order"]]}
        case QuestionType.MATCH:
            left = {i["id"]: i["text"] for i in content["left"]}
            right = {i["id"]: i["text"] for i in content["right"]}
            return {
                "pairs": answer["pairs"],
                "texts": [[left[lft], right[rgt]] for lft, rgt in answer["pairs"].items()],
            }
    raise ValueError(f"Unknown question type {qtype}")
