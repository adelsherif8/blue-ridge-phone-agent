import os
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

os.environ["PUBLIC_URL"] = "https://example.ngrok-free.app"
os.environ["TWILIO_AUTH_TOKEN"] = "test-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pipecat.frames.frames import CancelFrame, EndFrame  # noqa: E402
from twilio.request_validator import RequestValidator  # noqa: E402

from app import server  # noqa: E402
from app.state import BOARD  # noqa: E402
from app.tools import Tools  # noqa: E402
from app.transfer import (  # noqa: E402
    HOLD_LINE,
    TransferAwareTwilioSerializer,
    status_twiml,
    transfer_twiml,
    whisper_twiml,
)

client = TestClient(server.app)


def twiml(**kw):
    args = dict(public_url="https://example.ngrok-free.app/", to_number="+201005550199", from_number="+15555550100",
                reason="emergency", summary='Marcus, burst pipe at 9 Ridgecrest Rd & "flooding"', caller_id="+18285550199")
    args.update(kw)
    return ET.fromstring(transfer_twiml(**args))


# --- TwiML ---------------------------------------------------------------

def test_transfer_says_one_line_then_dials_the_verified_number():
    root = twiml()
    say, dial = list(root)
    assert say.tag == "Say" and say.text == HOLD_LINE
    assert dial.tag == "Dial" and dial.get("callerId") == "+15555550100" and dial.get("timeout") == "25"
    number = dial.find("Number")
    assert number.text == "+201005550199"


def test_transfer_urls_carry_reason_and_are_absolute():
    dial = twiml().find("Dial")
    action = urlparse(dial.get("action"))
    whisper = urlparse(dial.find("Number").get("url"))
    assert action.netloc == whisper.netloc == "example.ngrok-free.app"
    assert action.path == "/transfer-status" and whisper.path == "/whisper"
    q = parse_qs(action.query)
    assert q["reason"] == ["emergency"] and q["caller"] == ["+18285550199"]
    assert '& "flooding"' in q["summary"][0]  # special characters survive XML + URL encoding


def test_summary_is_capped():
    q = parse_qs(urlparse(twiml(summary="x" * 500).find("Dial").get("action")).query)
    assert len(q["summary"][0]) == 200


def test_whisper_tells_the_human_why():
    say = ET.fromstring(whisper_twiml("emergency", "Marcus, burst pipe")).find("Say").text
    assert "Emergency" in say and "Marcus, burst pipe" in say


@pytest.mark.parametrize("status,hangs_up_quietly", [("completed", True), ("no-answer", False),
                                                     ("busy", False), ("failed", False)])
def test_status_twiml(status, hangs_up_quietly):
    root = ET.fromstring(status_twiml(status))
    assert root[-1].tag == "Hangup"
    assert (root.find("Say") is None) == hangs_up_quietly


# --- serializer: the Pipecat hang-up gotcha ------------------------------

@pytest.fixture
def serializer(monkeypatch):
    s = TransferAwareTwilioSerializer(stream_sid="MZ1", call_sid="CA1", account_sid="AC1", auth_token="t")
    s.hangups = 0

    async def fake_hangup():
        s.hangups += 1

    monkeypatch.setattr(s, "_hang_up_call", fake_hangup)
    return s


@pytest.mark.parametrize("frame", [EndFrame(), CancelFrame()])
async def test_normal_call_end_still_hangs_up(serializer, frame):
    await serializer.serialize(frame)
    assert serializer.hangups == 1


@pytest.mark.parametrize("frame", [EndFrame(), CancelFrame()])
async def test_transferred_call_is_not_hung_up(serializer, frame):
    serializer.transferred = True
    assert await serializer.serialize(frame) is None
    assert serializer.hangups == 0


# --- endpoints -----------------------------------------------------------

def signed_post(path_with_query: str, form: dict):
    url = "https://example.ngrok-free.app" + path_with_query
    sig = RequestValidator("test-token").compute_signature(url, form)
    return client.post(path_with_query, data=form, headers={"X-Twilio-Signature": sig})


def test_endpoints_reject_unsigned_requests():
    assert client.post("/whisper?reason=x").status_code == 403
    assert client.post("/transfer-status?reason=x", data={"DialCallStatus": "no-answer"}).status_code == 403


def test_whisper_endpoint():
    r = signed_post("/whisper?reason=caller_request&summary=Joyce%20wants%20the%20owner", {"CallSid": "CA1"})
    assert r.status_code == 200 and "Joyce wants the owner" in r.text


def test_unanswered_transfer_saves_a_callback():
    before = len(BOARD.callbacks)
    r = signed_post("/transfer-status?reason=emergency&summary=burst%20pipe&caller=%2B18285550199",
                    {"CallSid": "CA1", "DialCallStatus": "no-answer"})
    assert r.status_code == 200 and "call you back" in r.text
    assert len(BOARD.callbacks) == before + 1
    cb = BOARD.callbacks[-1]
    assert cb["phone"] == "+18285550199" and "emergency" in cb["reason"]


def test_answered_transfer_just_hangs_up():
    before = len(BOARD.callbacks)
    r = signed_post("/transfer-status?reason=emergency&summary=x&caller=%2B18285550199",
                    {"CallSid": "CA1", "DialCallStatus": "completed"})
    assert "<Hangup/>" in r.text and "<Say" not in r.text and len(BOARD.callbacks) == before


# --- tool ----------------------------------------------------------------

def test_transfer_tool_calls_handler_once_and_logs_reason():
    from app.schedule import Board
    seen = []
    t = Tools(Board(), caller_id="+18285550199", on_transfer=lambda r, s: seen.append((r, s)))
    r = t.run("transfer_to_human", {"reason": "emergency", "summary": "burst pipe"})
    assert r["status"] == "Transferring" and seen == [("emergency", "burst pipe")]
    assert t.run("transfer_to_human", {"reason": "emergency", "summary": "again"})["status"] == "Already transferring"
    assert len(seen) == 1 and t.transfer == {"reason": "emergency", "summary": "burst pipe"}


@pytest.mark.parametrize("args", [{"reason": "bored", "summary": "x"}, {"reason": "emergency", "summary": " "}])
def test_transfer_tool_validates_args(args):
    from app.schedule import Board
    t = Tools(Board(), on_transfer=lambda r, s: None)
    assert t.run("transfer_to_human", args)["status"] == "Not transferred"


def test_transfer_unavailable_without_a_number():
    from app.schedule import Board
    r = Tools(Board()).run("transfer_to_human", {"reason": "caller_request", "summary": "wants owner"})
    assert r["status"] == "Unavailable" and "callback" in r["reason"]
