"""Marking. All-or-nothing correctness, plus a friendly partial-credit note.

Fill-the-blank matching is EXACT after normalising case, spacing, quotes and surrounding
punctuation, against a list of accepted answers. There's deliberately no fuzzy/typo
matching: "meiosis" is two letters from "mitosis", and a wrong answer marked right is
worse than a typo marked wrong.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import QuestionType

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_EDGE_PUNCT = " .,!?;:'\"()"
_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+", re.I)
_NUMBER = re.compile(r"^[+\-]?(\d+(\.\d*)?|\.\d+)$")
# Commas only count as thousands separators ("1,000"), never as decimal commas ("1,2").
_THOUSANDS = re.compile(r"^[+\-]?\d{1,3}(,\d{3})+(\.\d+)?$")


class McqResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str = Field(max_length=8)


class FillBlankResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=200)


class OrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: list[str] = Field(max_length=10)


class MatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pairs: dict[str, str] = Field(max_length=10)


RESPONSE_MODELS: dict[QuestionType, type[BaseModel]] = {
    QuestionType.MCQ: McqResponse,
    QuestionType.FILL_BLANK: FillBlankResponse,
    QuestionType.ORDER: OrderResponse,
    QuestionType.MATCH: MatchResponse,
}


@dataclass(frozen=True)
class Marked:
    correct: bool
    partial: str | None = None  # e.g. "3 of 5 in the right place"


def normalise(text: str, *, case_sensitive: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    text = " ".join(text.split()).strip(_EDGE_PUNCT)
    if not case_sensitive:
        text = _LEADING_ARTICLE.sub("", text.casefold())
    return text


def _as_number(text: str) -> float | None:
    cleaned = unicodedata.normalize("NFKC", text).strip().replace("−", "-").rstrip(".")
    if _THOUSANDS.match(cleaned):
        cleaned = cleaned.replace(",", "")
    if _NUMBER.match(cleaned):
        return float(cleaned)
    return None


def blank_matches(given: str, accepted: list[str], *, case_sensitive: bool) -> bool:
    got = normalise(given, case_sensitive=case_sensitive)
    if not got:
        return False
    got_number = _as_number(given)  # from the raw text: normalising would eat ".5"'s dot
    for option in accepted:
        want = normalise(option, case_sensitive=case_sensitive)
        if got == want:
            return True
        want_number = _as_number(option)
        if got_number is not None and want_number is not None and got_number == want_number:
            return True
    return False


def mark(
    qtype: QuestionType, answer: dict[str, Any], response: BaseModel, *, case_sensitive: bool
) -> Marked:
    match qtype, response:
        case QuestionType.MCQ, McqResponse():
            return Marked(response.option_id == answer["option_id"])
        case QuestionType.FILL_BLANK, FillBlankResponse():
            return Marked(
                blank_matches(response.text, answer["accepted"], case_sensitive=case_sensitive)
            )
        case QuestionType.ORDER, OrderResponse():
            right: list[str] = answer["order"]
            given = response.order
            in_place = sum(1 for a, b in zip(given, right, strict=False) if a == b)
            ok = given == right
            note = None if ok else f"{in_place} of {len(right)} in the right place"
            return Marked(ok, note)
        case QuestionType.MATCH, MatchResponse():
            want: dict[str, str] = answer["pairs"]
            got = response.pairs
            matched = sum(1 for k, v in want.items() if got.get(k) == v)
            ok = matched == len(want) and len(got) == len(want)
            note = None if ok else f"{matched} of {len(want)} pairs right"
            return Marked(ok, note)
    raise ValueError("Response doesn't fit this question type")


def response_fits_question(qtype: QuestionType, shown: dict[str, Any], response: BaseModel) -> bool:
    """Reject responses that reference options the player was never shown."""
    match qtype, response:
        case QuestionType.MCQ, McqResponse():
            return response.option_id in {o["id"] for o in shown["options"]}
        case QuestionType.FILL_BLANK, FillBlankResponse():
            return True
        case QuestionType.ORDER, OrderResponse():
            return sorted(response.order) == sorted(i["id"] for i in shown["items"])
        case QuestionType.MATCH, MatchResponse():
            return set(response.pairs) == {i["id"] for i in shown["left"]} and set(
                response.pairs.values()
            ) <= {i["id"] for i in shown["right"]}
    return False
