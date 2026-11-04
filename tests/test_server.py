import os

os.environ["PUBLIC_URL"] = "https://example.ngrok-free.app"
os.environ["TWILIO_AUTH_TOKEN"] = "test-token"

from fastapi.testclient import TestClient  # noqa: E402
from twilio.request_validator import RequestValidator  # noqa: E402

from app import server  # noqa: E402
from app.util import mask_phone  # noqa: E402

client = TestClient(server.app)
FORM = {"CallSid": "CA123", "From": "+15551234567", "To": "+15557654321"}


def signed_headers(form):
    sig = RequestValidator("test-token").compute_signature("https://example.ngrok-free.app/voice", form)
    return {"X-Twilio-Signature": sig}


def test_voice_rejects_unsigned():
    assert client.post("/voice", data=FORM).status_code == 403


def test_voice_returns_stream_twiml_with_token():
    r = client.post("/voice", data=FORM, headers=signed_headers(FORM))
    assert r.status_code == 200
    assert 'url="wss://example.ngrok-free.app/ws"' in r.text
    assert '<Parameter name="token"' in r.text


def test_token_is_single_use():
    token = server._issue_token()
    assert server.consume_token(token)
    assert not server.consume_token(token)
    assert not server.consume_token(None)


def test_mask_phone():
    assert mask_phone("+1 (555) 123-4567") == "***4567"
    assert mask_phone(None) == "unknown"
