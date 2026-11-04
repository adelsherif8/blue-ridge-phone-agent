"""FastAPI entry point.

Twilio calls POST /voice when the number rings. We check the request
signature, then answer with TwiML that opens a Media Stream to /ws.
Each stream carries a one-time token so only calls we answered can open
a bot session.
"""

import os
import secrets
import time
from xml.sax.saxutils import quoteattr

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket
from loguru import logger
from twilio.request_validator import RequestValidator

from app.util import mask_phone

load_dotenv()  # real env vars win over .env

app = FastAPI()

TOKEN_TTL_SECS = 60
# token -> issue time. In-memory is fine for one process; Render runs one instance.
_stream_tokens: dict[str, float] = {}


def _public_url() -> str:
    return os.environ["PUBLIC_URL"].rstrip("/")


def _issue_token() -> str:
    now = time.time()
    for t, issued in list(_stream_tokens.items()):
        if now - issued > TOKEN_TTL_SECS:
            _stream_tokens.pop(t, None)
    token = secrets.token_urlsafe(24)
    _stream_tokens[token] = now
    return token


def consume_token(token: str | None) -> bool:
    if not token:
        return False
    issued = _stream_tokens.pop(token, None)
    return issued is not None and time.time() - issued <= TOKEN_TTL_SECS


async def _valid_twilio_request(request: Request) -> bool:
    if os.getenv("SKIP_TWILIO_SIGNATURE") == "1":  # local tests only
        return True
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    form = dict(await request.form())
    # Validate against the public URL Twilio called, not the local one behind ngrok.
    url = _public_url() + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    return validator.validate(url, form, request.headers.get("X-Twilio-Signature", ""))


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/voice")
async def voice(request: Request):
    if not await _valid_twilio_request(request):
        logger.warning("Rejected /voice: bad Twilio signature")
        return Response(status_code=403)
    form = await request.form()
    logger.info(f"Incoming call {form.get('CallSid')} from {mask_phone(form.get('From'))}")
    ws_url = _public_url().replace("https://", "wss://", 1) + "/ws"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f"<Stream url={quoteattr(ws_url)}>"
        f'<Parameter name="token" value={quoteattr(_issue_token())}/>'
        f'<Parameter name="caller" value={quoteattr(form.get("From") or "")}/>'
        "</Stream></Connect></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    from pipecat.runner.types import WebSocketRunnerArguments
    from pipecat.runner.utils import parse_telephony_websocket

    from app.bot import bot

    await websocket.accept()
    transport_type, call_data = await parse_telephony_websocket(websocket)
    params = (call_data.get("body") or {}) if call_data else {}
    if transport_type != "twilio" or not consume_token(params.get("token")):
        logger.warning("Rejected /ws: missing or bad stream token")
        await websocket.close(code=1008)
        return
    try:
        await bot(WebSocketRunnerArguments(websocket=websocket))
    except Exception:
        logger.exception("Bot session failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8790")))
