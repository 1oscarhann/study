"""Enum-like values. Stored as text + CHECK constraints (easier to evolve than PG enums)."""

from enum import StrEnum


class BoardConfidence(StrEnum):
    STATED = "stated"
    INFERRED = "inferred"


class QuestionType(StrEnum):
    MCQ = "mcq"
    FILL_BLANK = "fill_blank"
    ORDER = "order"
    MATCH = "match"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    LIVE = "live"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class QuestionOrigin(StrEnum):
    SEED = "seed"
    ADMIN = "admin"
    MANUAL = "manual"
    AI = "ai"


class VerificationStatus(StrEnum):
    UNCHECKED = "unchecked"
    PASSED = "passed"
    NEEDS_CHECKING = "needs_checking"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"


class ReportReason(StrEnum):
    WRONG_ANSWER = "wrong_answer"
    AMBIGUOUS = "ambiguous"
    TYPO = "typo"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    UPHELD = "upheld"
    DISMISSED = "dismissed"


class PlayMode(StrEnum):
    QUIZ = "quiz"
    BATTLE = "battle"
    BOSS = "boss"
    REVIEW = "review"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    FINISHED = "finished"
    ABANDONED = "abandoned"


class SessionResult(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class XpSource(StrEnum):
    ANSWER = "answer"
    QUIZ = "quiz"
    BATTLE = "battle"
    BOSS = "boss"
    STREAK = "streak"
    REVIEW = "review"


class CosmeticSlot(StrEnum):
    HAT = "hat"
    BACKGROUND = "background"
    FRAME = "frame"


class UnlockType(StrEnum):
    DEFAULT = "default"
    LEVEL = "level"
    STREAK = "streak"
    BOSS = "boss"


class LeagueOutcome(StrEnum):
    PROMOTED = "promoted"
    STAYED = "stayed"
    RELEGATED = "relegated"
