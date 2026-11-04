"""Live transfer to a person.

Flow: the LLM calls transfer_to_human(reason, summary). We mark the call as transferred
(so Pipecat will NOT hang it up when the bot's pipeline stops), then replace the call's
TwiML through Twilio's REST API:

    <Say> one hold line </Say>
    <Dial callerId=our number, action=/transfer-status>
        <Number url=/whisper?...> human's number </Number>   # the human hears the reason first
    </Dial>

Replacing the TwiML ends the Media Stream (<Connect> completes), so the bot leaves and
Twilio keeps the caller on the line while it dials. If nobody answers, /transfer-status
apologizes, saves a callback request and hangs up. Without TRANSFER_DRY_RUN, this is the
only module that changes a live call.
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlencode
from xml.sax.saxutils import escape, quoteattr

from loguru import logger
from pipecat.frames.frames import CancelFrame, EndFrame
from pipecat.serializers.twilio import TwilioFrameSerializer

HOLD_LINE = "Connecting you to our on-call team now. Please stay on the line."
REASONS = ("caller_request", "emergency", "stuck", "safety")
VOICE = "Polly.Joanna-Neural"


class TransferAwareTwilioSerializer(TwilioFrameSerializer):
    """Twilio serializer that skips its automatic hang-up once the call has been transferred.

    Pipecat hangs up the call (Status=completed) when the pipeline ends. After a transfer the
    call belongs to the <Dial>, so that hang-up would drop the caller and the person they
    were transferred to.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transferred = False

    async def serialize(self, frame):
        if self.transferred and isinstance(frame, (EndFrame, CancelFrame)):
            logger.info("Call was transferred: skipping automatic hang-up")
            return None
        return await super().serialize(frame)


def transfer_twiml(*, public_url: str, to_number: str, from_number: str, reason: str, summary: str,
                   caller_id: str | None) -> str:
    base = public_url.rstrip("/")
    q = urlencode({"reason": reason, "summary": summary[:200], "caller": caller_id or ""})
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Response>'
        f"<Say voice={quoteattr(VOICE)}>{escape(HOLD_LINE)}</Say>"
        f"<Dial callerId={quoteattr(from_number)} timeout=\"25\" action={quoteattr(f'{base}/transfer-status?{q}')}>"
        f"<Number url={quoteattr(f'{base}/whisper?{q}')}>{escape(to_number)}</Number>"
        "</Dial></Response>"
    )


def whisper_twiml(reason: str, summary: str) -> str:
    label = {"emergency": "Emergency", "safety": "Safety", "stuck": "Agent could not help",
             "caller_request": "Caller asked for a person"}.get(reason, "Transfer")
    text = f"Blue Ridge phone agent transfer. {label}. {summary}".strip()
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say voice={quoteattr(VOICE)}>{escape(text)}</Say></Response>'


def status_twiml(dial_status: str) -> str:
    """After the <Dial>: hang up cleanly if the person talked, apologize otherwise."""
    if dial_status == "completed":
        return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Say voice={quoteattr(VOICE)}>'
        "Sorry, no one could pick up right now. We have saved your request and the office will call you back "
        "as soon as possible. If anyone is in danger, hang up and call nine one one.</Say><Hangup/></Response>"
    )


async def redirect_call(call_sid: str, twiml: str) -> None:
    """Replace the live call's TwiML. TRANSFER_DRY_RUN=1 logs instead (simulated calls, tests)."""
    if os.getenv("TRANSFER_DRY_RUN") == "1":
        logger.info(f"TRANSFER DRY RUN for {call_sid}: {twiml}")
        return
    from twilio.rest import Client

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    await asyncio.to_thread(lambda: client.calls(call_sid).update(twiml=twiml))
    logger.info(f"Call {call_sid} redirected to transfer TwiML")
