import pytest

from app.redact import CallRedactor


@pytest.mark.parametrize("text,gone", [
    ("call 828 555 0142", "555"),
    ("it's (828) 555-0142", "555"),
    ("+18285550142", "555"),
    ("eight two eight, five five five, oh one four two", "five five five"),
    ("five five five, one two three, four five six seven", "one two three"),
    ("That's forty-one Laurel Drive, right?", "Laurel"),
    ("fifty-two Maple Street", "Maple"),
    ("nine Ridgecrest Road", "Ridgecrest"),
    ("41 Laurel Drive", "Laurel"),
    ("this is Ana", "Ana"),
    ("email me at ana@example.com", "example.com"),
])
def test_pii_is_removed(text, gone):
    assert gone not in CallRedactor(names=["Ana"]).redact(text)


@pytest.mark.parametrize("text", [
    "There's an eighty-nine dollar call-out fee.",
    "We have two to four PM or four to six PM open tomorrow.",
    "Thanks for calling Blue Ridge Plumbing, this is Sam.",
    "Call the gas company or nine one one from outside.",
])
def test_business_text_is_kept(text):
    assert CallRedactor(names=["Ana"]).redact(text) == text


def test_same_value_gets_same_placeholder_in_one_call():
    r = CallRedactor(names=["Ana"])
    a, b = r.redact("41 Laurel Drive"), r.redact("yes, 41 Laurel Drive")
    assert a in b


def test_nested_objects_and_agent_name_kept():
    r = CallRedactor(names=["Ana", "Sam", "Caller"])
    out = r.redact_obj({"args": {"name": "Ana", "address": "41 Laurel Drive"}, "text": ["Sam here"]})
    assert out["args"]["name"] != "Ana" and "Laurel" not in out["args"]["address"] and out["text"] == ["Sam here"]
