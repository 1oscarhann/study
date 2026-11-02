import json
from pathlib import Path

import pytest

from app.content.catalog import (
    CatalogError,
    ImportFile,
    Subtopic,
    build_catalog,
    parse_subtopic,
)

SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "gcse_topics.json"


@pytest.fixture(scope="module")
def seed() -> ImportFile:
    return ImportFile.model_validate(json.loads(SEED_FILE.read_text()))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Meiosis", Subtopic("Meiosis")),
        ("Moles (higher)", Subtopic("Moles", higher_only=True)),
        (
            "Culturing microorganisms (triple only)",
            Subtopic("Culturing microorganisms", triple_only=True),
        ),
        (
            "Sine rule, cosine rule and 1/2 ab sin C (higher)",
            Subtopic("Sine rule, cosine rule and 1/2 ab sin C", higher_only=True),
        ),
        ("Thing (higher) (triple only)", Subtopic("Thing", higher_only=True, triple_only=True)),
        # Brackets that aren't flags are left alone.
        ("Trigonometry (SOHCAHTOA)", Subtopic("Trigonometry (SOHCAHTOA)")),
    ],
)
def test_parse_subtopic(raw, expected):
    assert parse_subtopic(raw) == expected


def test_seed_file_parses(seed):
    catalog = build_catalog(seed)
    assert len(catalog.subjects) == 24
    assert len(catalog.links) == 142
    slugs = [s.slug for s in catalog.subjects]
    assert len(slugs) == len(set(slugs))
    assert "combined-science-trilogy" in slugs


def test_combined_science_shares_topics_with_separate_sciences(seed):
    catalog = build_catalog(seed)
    cells = catalog.topics["sci-bio-cells"]
    # Canonical name + subtopics come from the triple Biology entry.
    assert cells.name == "Cell biology"
    assert Subtopic("Culturing microorganisms", triple_only=True) in cells.subtopics

    links = {lnk.subject_slug: lnk for lnk in catalog.links if lnk.topic_slug == "sci-bio-cells"}
    assert set(links) == {"combined-science-trilogy", "biology"}
    assert links["combined-science-trilogy"].display_name == "Biology 1: Cell biology"
    assert links["combined-science-trilogy"].excludes_triple_only is True
    assert links["combined-science-trilogy"].spec_ref is None
    assert links["biology"].excludes_triple_only is False
    assert links["biology"].spec_ref == "4.1"


def test_space_physics_is_physics_only(seed):
    catalog = build_catalog(seed)
    subjects = {lnk.subject_slug for lnk in catalog.links if lnk.topic_slug == "sci-phys-space"}
    assert subjects == {"physics"}


def test_higher_tier_flags_survive_import(seed):
    catalog = build_catalog(seed)
    algebra = {s.name: s for s in catalog.topics["maths-algebra"].subtopics}
    assert algebra["Iteration"].higher_only
    assert not algebra["Rearranging formulae"].higher_only


def test_subjects_without_topics_are_kept(seed):
    # French and German are listed with no topics yet (to be cloned from Spanish).
    catalog = build_catalog(seed)
    linked = {lnk.subject_slug for lnk in catalog.links}
    assert {"french", "german"} <= {s.slug for s in catalog.subjects}
    assert not {"french", "german"} & linked


def _file(*subjects):
    return ImportFile.model_validate({"subjects": list(subjects)})


def _subject(name, topics, **extra):
    return {
        "subject": name,
        "qualification": "GCSE",
        "board": "AQA",
        "confidence": "stated",
        "topics": topics,
        **extra,
    }


def test_two_subtopic_definitions_for_one_slug_is_an_error():
    data = _file(
        _subject("A", [{"id": "t-1", "name": "T", "subtopics": ["x"]}]),
        _subject("B", [{"id": "t-1", "name": "T", "subtopics": ["y"]}]),
    )
    with pytest.raises(CatalogError, match="t-1"):
        build_catalog(data)


def test_duplicate_topic_within_a_subject_is_an_error():
    data = _file(_subject("A", [{"id": "t-1", "name": "T"}, {"id": "t-1", "name": "T"}]))
    with pytest.raises(CatalogError, match="twice"):
        build_catalog(data)


def test_same_subject_name_gets_qualification_in_slug():
    data = _file(
        _subject("Biology", [], qualification="GCSE"),
        _subject("Biology", [], qualification="A-level"),
    )
    assert [s.slug for s in build_catalog(data).subjects] == ["biology", "biology-a-level"]


def test_unknown_fields_are_rejected():
    with pytest.raises(ValueError):
        _file(_subject("A", [{"id": "t-1", "name": "T", "subtopix": []}]))
