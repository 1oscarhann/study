import re

import pytest

from app.security.passwords import (
    RECOVERY_ALPHABET,
    hash_secret,
    new_recovery_code,
    normalise_recovery_code,
    password_problem,
    verify_secret,
)
from app.security.usernames import username_ideas, username_problem

# --- passwords ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("short", "at least 8"),
        ("x" * 129, "under 128"),
        ("SwiftOtter42", "same as your username"),
        ("swiftotter42", "same as your username"),
        ("password", "too common"),
        ("Football", "too common"),
        ("iloveyou", "too common"),
    ],
)
def test_bad_passwords_are_explained(password, fragment):
    problem = password_problem(password, "SwiftOtter42")
    assert problem is not None and fragment in problem


@pytest.mark.parametrize("password", ["correct horse battery", "Mitochondria!4", "a" * 128])
def test_good_passwords_pass(password):
    assert password_problem(password, "SwiftOtter42") is None


async def test_hash_round_trip():
    stored = await hash_secret("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert await verify_secret(stored, "correct horse battery")
    assert not await verify_secret(stored, "wrong horse battery")


async def test_garbage_hash_just_fails():
    assert not await verify_secret("not-a-hash", "anything")


def test_recovery_codes_are_readable_and_random():
    codes = {new_recovery_code() for _ in range(200)}
    assert len(codes) == 200
    pattern = re.compile(rf"^[{RECOVERY_ALPHABET}]{{4}}(-[{RECOVERY_ALPHABET}]{{4}}){{3}}$")
    assert all(pattern.match(c) for c in codes)
    assert not set("01ILO") & set(RECOVERY_ALPHABET)


def test_recovery_code_typing_is_forgiving():
    assert normalise_recovery_code(" abcd-efgh hjkm-npqr ") == "ABCDEFGHHJKMNPQR"


# --- usernames ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "SwiftOtter42",
        "peacock",
        "Arsenal_fan",
        "Sussex99",
        "badminton_pro",
        "raccoon",
        "Spicy_Noodle",
        "PakistanFan",
        "NigeriaFan",
        "grape_juice",
        "Cocktail",
        "Mississippi",
        "class_clown",
        "Titanic",
        "Year10_Physics",
    ],
)
def test_ordinary_usernames_are_allowed(name):
    assert username_problem(name) is None


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("ab", "3–20"),
        ("has space", "3–20"),
        ("emoji😀", "3–20"),
        ("a" * 21, "3–20"),
        ("phone07123456789", "long numbers"),
        ("admin", "reserved"),
        ("TheAdmin", "reserved"),
        ("Mod_99", "reserved"),
        ("Revision_Battle", "reserved"),
        ("xXsh1tXx", "isn't allowed"),
        ("F_u_U_c_K", "isn't allowed"),
        ("fuuuuuck", "isn't allowed"),
        ("big_ass", "isn't allowed"),
        ("S3xyBeast", "isn't allowed"),
        ("Nazi_Fan", "isn't allowed"),
    ],
)
def test_bad_usernames_are_explained(name, fragment):
    problem = username_problem(name)
    assert problem is not None and fragment in problem


def test_username_ideas_are_all_valid():
    ideas = username_ideas(50)
    assert len(ideas) == 50
    assert len(set(ideas)) == 50
    assert all(username_problem(i) is None and len(i) <= 20 for i in ideas)
