import random

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.answer_check import (
    FillBlankResponse,
    MatchResponse,
    McqResponse,
    OrderResponse,
    blank_matches,
    mark,
    normalise,
    response_fits_question,
)
from app.domain.questions import (
    FillBlankDraft,
    MatchDraft,
    McqDraft,
    OrderDraft,
    QuestionDraft,
    correct_answer_display,
    shuffle_for_display,
    to_storage,
)
from app.models.enums import QuestionType

DRAFT = TypeAdapter(QuestionDraft)
EXPL = "Because science."


# --- drafts: the deterministic checks ------------------------------------------------------


def test_mcq_draft_happy_path():
    d = DRAFT.validate_python(
        {"type": "mcq", "prompt": "Which organelle?", "correct": "Nucleus",
         "wrong": ["Ribosome", "Cell wall"], "explanation": EXPL}
    )  # fmt: skip
    assert isinstance(d, McqDraft)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"wrong": ["Nucleus", "Ribosome"]}, "different"),  # right answer repeated
        ({"wrong": ["ribosome ", "Ribosome"]}, "different"),  # dupes after normalising
        ({"wrong": ["All of the above", "Ribosome"]}, "above"),
        ({"wrong": ["Ribosome"]}, "at least 2"),
        ({"explanation": "x" * 201}, "at most 200"),
        ({"explanation": ""}, "at least 1"),
        ({"surprise": "field"}, "Extra inputs"),
    ],
)
def test_mcq_draft_rejections(payload, message):
    base = {"type": "mcq", "prompt": "Which organelle?", "correct": "Nucleus",
            "wrong": ["Ribosome", "Cell wall"], "explanation": EXPL}  # fmt: skip
    with pytest.raises(ValidationError, match=message):
        DRAFT.validate_python({**base, **payload})


@pytest.mark.parametrize("prompt", ["No blank here at all", "Two ___ blanks ___ here"])
def test_fill_blank_needs_exactly_one_blank(prompt):
    with pytest.raises(ValidationError, match="exactly one"):
        FillBlankDraft(prompt=prompt, accepted=["x"], explanation=EXPL)


def test_order_and_match_need_distinct_items():
    with pytest.raises(ValidationError):
        OrderDraft(prompt="Put in order", items=["a", "b", "A"], explanation=EXPL)
    with pytest.raises(ValidationError):
        MatchDraft(prompt="Match them", pairs=[("a", "1"), ("b", "1"), ("c", "3")],
                   explanation=EXPL)  # fmt: skip


# --- storage + serving -------------------------------------------------------------------


def _mcq():
    return McqDraft(prompt="Which organelle releases energy?", correct="Mitochondria",
                    wrong=["Ribosome", "Nucleus", "Cell wall"], explanation=EXPL)  # fmt: skip


def test_storage_keeps_the_answer_out_of_content():
    stored = to_storage(_mcq())
    assert stored.type is QuestionType.MCQ
    assert "Mitochondria" in {o["text"] for o in stored.content["options"]}
    assert set(stored.answer) == {"option_id"}
    assert "option_id" not in str(stored.content)


def test_stored_order_doesnt_always_put_the_answer_first():
    firsts = set()
    for i in range(30):
        d = McqDraft(prompt=f"Question number {i}?", correct="Right",
                     wrong=["W1", "W2", "W3"], explanation=EXPL)  # fmt: skip
        s = to_storage(d)
        firsts.add(s.content["options"][0]["text"] == "Right")
    assert firsts == {True, False}


def test_order_storage_and_display():
    d = OrderDraft(prompt="Put in order", items=["first", "second", "third", "fourth"],
                   explanation=EXPL)  # fmt: skip
    s = to_storage(d)
    shown = correct_answer_display(s.type, s.content, s.answer)
    assert shown["texts"] == ["first", "second", "third", "fourth"]


def test_match_storage_and_display():
    d = MatchDraft(prompt="Match them", pairs=[("Proton", "+1"), ("Electron", "-1"),
                   ("Neutron", "0")], explanation=EXPL)  # fmt: skip
    s = to_storage(d)
    shown = correct_answer_display(s.type, s.content, s.answer)
    assert sorted(shown["texts"]) == [["Electron", "-1"], ["Neutron", "0"], ["Proton", "+1"]]


def test_shuffle_for_display_never_adds_answer_and_keeps_items():
    s = to_storage(_mcq())
    for seed in range(10):
        shown = shuffle_for_display(s.type, s.content, random.Random(seed))
        assert sorted(o["id"] for o in shown["options"]) == sorted(
            o["id"] for o in s.content["options"]
        )
        assert set(shown) == {"options"}


# --- marking -----------------------------------------------------------------------------


def test_mcq_marking():
    s = to_storage(_mcq())
    right = s.answer["option_id"]
    wrong = next(o["id"] for o in s.content["options"] if o["id"] != right)
    assert mark(s.type, s.answer, McqResponse(option_id=right), case_sensitive=False).correct
    assert not mark(s.type, s.answer, McqResponse(option_id=wrong), case_sensitive=False).correct


@pytest.mark.parametrize(
    ("given", "ok"),
    [
        ("mitochondria", True),
        ("  Mitochondria. ", True),
        ("The mitochondria", True),
        ("MITOCHONDRION", True),
        ("mitochondra", False),  # typo: no fuzzy matching on purpose
        ("", False),
        ("   ", False),
    ],
)
def test_fill_blank_marking_is_exact_after_normalising(given, ok):
    assert blank_matches(given, ["mitochondria", "mitochondrion"], case_sensitive=False) is ok


def test_meiosis_is_not_mitosis():
    assert not blank_matches("meiosis", ["mitosis"], case_sensitive=False)


def test_case_sensitive_chemistry_symbols():
    assert blank_matches("Co", ["Co"], case_sensitive=True)
    assert not blank_matches("CO", ["Co"], case_sensitive=True)  # carbon monoxide, not cobalt


@pytest.mark.parametrize(
    ("given", "ok"),
    [("12", True), ("12.0", True), (" 12 ", True), ("12.", True), ("13", False),
     ("twelve", False), ("1,2", False)],
)  # fmt: skip
def test_numbers_compare_as_numbers(given, ok):
    # "1,2" might mean 1.2 (decimal comma), so it's never read as 12.
    assert blank_matches(given, ["12"], case_sensitive=False) is ok


def test_thousands_separators():
    assert blank_matches("1,000", ["1000"], case_sensitive=False)
    assert blank_matches("6,600", ["6600"], case_sensitive=False)
    assert not blank_matches("1,2", ["1.2"], case_sensitive=False)


def test_decimals():
    assert blank_matches(".5", ["0.5"], case_sensitive=False)
    assert blank_matches("35.5", ["35.5"], case_sensitive=False)
    assert not blank_matches("35", ["35.5"], case_sensitive=False)


def test_normalise_quotes_and_dashes():
    assert normalise("‘Kirche’") == normalise("'kirche'")


def test_order_marking_gives_partial_note():
    answer = {"order": ["a", "b", "c", "d"]}
    assert mark(QuestionType.ORDER, answer, OrderResponse(order=["a", "b", "c", "d"]),
                case_sensitive=False).correct  # fmt: skip
    m = mark(QuestionType.ORDER, answer, OrderResponse(order=["a", "c", "b", "d"]),
             case_sensitive=False)  # fmt: skip
    assert not m.correct and m.partial == "2 of 4 in the right place"


def test_match_marking_gives_partial_note():
    answer = {"pairs": {"la": "ra", "lb": "rb", "lc": "rc"}}
    ok = mark(QuestionType.MATCH, answer, MatchResponse(pairs={"la": "ra", "lb": "rb", "lc": "rc"}),
              case_sensitive=False)  # fmt: skip
    assert ok.correct
    m = mark(QuestionType.MATCH, answer, MatchResponse(pairs={"la": "rb", "lb": "ra", "lc": "rc"}),
             case_sensitive=False)  # fmt: skip
    assert not m.correct and m.partial == "1 of 3 pairs right"


def test_responses_must_refer_to_what_was_shown():
    shown_mcq = {"options": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]}
    assert response_fits_question(QuestionType.MCQ, shown_mcq, McqResponse(option_id="a"))
    assert not response_fits_question(QuestionType.MCQ, shown_mcq, McqResponse(option_id="z"))
    shown_order = {"items": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}]}
    assert not response_fits_question(QuestionType.ORDER, shown_order, OrderResponse(order=["a"]))
    assert not response_fits_question(
        QuestionType.ORDER, shown_order, OrderResponse(order=["a", "a"])
    )
    assert response_fits_question(QuestionType.FILL_BLANK, {}, FillBlankResponse(text="anything"))
