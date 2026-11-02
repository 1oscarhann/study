"""Username rules, the profanity filter, and safe username suggestions.

The filter deliberately leans strict: a kid picking a different username is a much
smaller harm than a slur on a school leaderboard. Word lists live in ./data so they can
be extended without touching code.
"""

from __future__ import annotations

import re
import secrets
from functools import cache
from pathlib import Path

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_LONG_NUMBER_RE = re.compile(r"\d{6,}")
# 0→o 1→i 3→e 4→a 5→s 7→t 8→b 9→g
_LEET = str.maketrans("01345789", "oieastbg")
_TOKEN_SPLIT_RE = re.compile(r"[_\d]+|(?<=[a-z])(?=[A-Z])")

_DATA = Path(__file__).parent / "data"


def _load(name: str) -> frozenset[str]:
    lines = (_DATA / name).read_text().splitlines()
    return frozenset(w.strip().lower() for w in lines if w.strip() and not w.startswith("#"))


@cache
def _substrings() -> frozenset[str]:
    return _load("blocked_substrings.txt")


@cache
def _tokens() -> frozenset[str]:
    return _load("blocked_tokens.txt")


@cache
def _reserved() -> frozenset[str]:
    return _load("reserved_usernames.txt")


def _collapse_repeats(text: str) -> str:
    return re.sub(r"(.)\1+", r"\1", text)


def _squashed_variants(name: str) -> set[str]:
    """`F_u_U_u_c_K` → {"fuuuck", "fuck"}; `sh1t` → {"shit"}."""
    base = name.lower().replace("_", "").translate(_LEET)
    return {base, _collapse_repeats(base)}


def _tokens_of(name: str) -> set[str]:
    """`SwiftOtter_42` → {"swift", "otter"}; leetspeak inside a token is undone too."""
    parts = [p for p in _TOKEN_SPLIT_RE.split(name) if p]
    out: set[str] = set()
    for part in parts:
        low = part.lower()
        out.add(low)
        out.add(_collapse_repeats(low))
    # Leet-decoded whole name, split again (catches "s3x" → "sex").
    decoded = name.translate(_LEET)
    for part in _TOKEN_SPLIT_RE.split(decoded):
        if part:
            out.add(part.lower())
    return out


def is_offensive(name: str) -> bool:
    if any(bad in variant for variant in _squashed_variants(name) for bad in _substrings()):
        return True
    return bool(_tokens_of(name) & _tokens())


def is_reserved(name: str) -> bool:
    if _tokens_of(name) & _reserved():
        return True
    return any(v in _reserved() for v in _squashed_variants(name))


def username_problem(name: str) -> str | None:
    """A friendly reason the username isn't allowed, or None if it's fine."""
    if not USERNAME_RE.fullmatch(name):
        return "Usernames are 3–20 letters, numbers or underscores (no spaces)."
    if _LONG_NUMBER_RE.search(name):
        return "Usernames can't contain long numbers like phone numbers."
    if is_reserved(name):
        return "That username is reserved. Pick another one."
    if is_offensive(name):
        return "That username isn't allowed. Pick another one."
    return None


# --- Suggestions ------------------------------------------------------------------------
_ADJECTIVES = (
    "Swift", "Cosmic", "Brave", "Clever", "Lucky", "Mighty", "Sunny", "Quiet", "Bold",
    "Bright", "Calm", "Daring", "Eager", "Fuzzy", "Gentle", "Happy", "Jolly", "Keen",
    "Lively", "Merry", "Nimble", "Plucky", "Quick", "Rapid", "Snappy", "Stellar", "Tidy",
    "Witty", "Zesty", "Breezy", "Frosty", "Golden", "Hidden", "Misty", "Neon", "Pixel",
    "Silver", "Turbo", "Velvet", "Electric",
)  # fmt: skip
_NOUNS = (
    "Otter", "Falcon", "Panda", "Comet", "Badger", "Fox", "Koala", "Lynx", "Moose",
    "Narwhal", "Owl", "Penguin", "Quokka", "Raven", "Seal", "Tiger", "Walrus", "Yak",
    "Zebra", "Gecko", "Heron", "Ibis", "Jaguar", "Lemur", "Puffin", "Rocket", "Nebula",
    "Meteor", "Planet", "Atom", "Photon", "Quasar", "Pulsar", "Orbit", "Galaxy", "Dragon",
    "Phoenix", "Kraken", "Yeti", "Griffin",
)  # fmt: skip


def username_ideas(count: int = 12) -> list[str]:
    """Random friendly usernames that pass the rules. Availability is checked by the caller."""
    ideas: list[str] = []
    attempts = 0
    while len(ideas) < count and attempts < count * 10:
        attempts += 1
        name = f"{secrets.choice(_ADJECTIVES)}{secrets.choice(_NOUNS)}{secrets.randbelow(90) + 10}"
        if len(name) <= 20 and username_problem(name) is None and name not in ideas:
            ideas.append(name)
    return ideas
