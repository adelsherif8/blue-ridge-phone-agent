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


def test_calllog_joins_stt_fragments_before_redacting(tmp_path, monkeypatch):
    import json
    from app import calllog
    monkeypatch.setenv("CALL_LOG_DIR", str(tmp_path))
    log = calllog.CallLog("CAtest", "+18285550123")
    msgs = [{"role": "assistant", "content": "What's the address?"},
            {"role": "user", "content": "Sure. The address is one two three"},
            {"role": "user", "content": "Pine Street."}]
    path = log.write(messages=msgs, tool_calls=[], transfer=None, crm=[], ended_by="hangup")
    rec = json.loads(path.read_text())
    assert len(rec["transcript"]) == 2
    assert "Pine" not in rec["transcript"][1]["text"]


def test_self_given_first_name_is_redacted_in_transfer_summary(tmp_path, monkeypatch):
    import json
    from app import calllog
    monkeypatch.setenv("CALL_LOG_DIR", str(tmp_path))
    log = calllog.CallLog("CAtest2", None)
    msgs = [{"role": "user", "content": "Hi Sam, This is Marcus. A pipe burst in my basement."}]
    path = log.write(messages=msgs, tool_calls=[], transfer={"reason": "emergency", "summary": "Marcus has a burst pipe"},
                     crm=[], ended_by="transfer")
    rec = json.loads(path.read_text())
    assert "Marcus" not in json.dumps(rec)
    assert "Sam" in rec["transcript"][0]["text"]
