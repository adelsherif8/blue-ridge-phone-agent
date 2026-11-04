"""Simulated phone call: an LLM caller talks to the bot over Twilio's Media Streams protocol.

No phone network. The caller's lines are spoken with Deepgram TTS (8 kHz mu-law),
streamed to /ws in real time; the bot's audio is collected, a turn ends after
SILENCE_GAP seconds of no bot audio, and the turn is transcribed with Deepgram
and handed to the caller LLM, which picks the next line.

Usage: uv run python scripts/sim_call.py [--scenario routine_booking] [--port 8790]
"""

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websockets
from dotenv import load_dotenv
from openai import AsyncOpenAI
from twilio.request_validator import RequestValidator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.scenarios import SCENARIOS  # noqa: E402

load_dotenv(".env")
DG = os.environ["DEEPGRAM_API_KEY"]
FRAME = 160  # 20 ms of 8 kHz mu-law
SILENCE = b"\xff" * FRAME
SILENCE_GAP = 2.0  # seconds of bot silence that end its turn
TURN_TIMEOUT = 25.0
MAX_TURNS = 14
CALLER_RULES = (
    "You are a person on the phone with Blue Ridge Plumbing. Speak in one or two short spoken sentences, no "
    "symbols. Answer only what is asked. Stick to your role. Never hang up while waiting for an answer. When the "
    "agent has finished and you have said goodbye, end your line with [HANGUP]."
)
oai = AsyncOpenAI()


def tts(text: str) -> bytes:
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/speak?model=aura-2-orion-en&encoding=mulaw&sample_rate=8000&container=none",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {DG}", "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req).read()


def stt_mulaw(audio: bytes) -> str:
    if len(audio) < 1600:
        return ""
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&encoding=mulaw&sample_rate=8000",
        data=audio, headers={"Authorization": f"Token {DG}", "Content-Type": "audio/mulaw"},
    )
    r = json.load(urllib.request.urlopen(req))
    return r["results"]["channels"][0]["alternatives"][0]["transcript"]


def get_token(port: int, caller: str, call_sid: str = "CAsimulated") -> str:
    public = os.environ["PUBLIC_URL"].rstrip("/") + "/voice"
    form = {"CallSid": call_sid, "From": caller, "To": os.environ.get("TWILIO_PHONE_NUMBER", "")}
    sig = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"]).compute_signature(public, form)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(f"http://127.0.0.1:{port}/voice", data=urllib.parse.urlencode(form).encode(),
                                 headers={"X-Twilio-Signature": sig})
    twiml = opener.open(req).read().decode()
    return re.search(r'name="token" value="([^"]+)"', twiml).group(1)


async def run(scenario: dict, port: int, call_sid: str = "CAsimulated", client_turns: list | None = None
              ) -> list[tuple[str, str]]:
    """client_turns, if given, gets one dict per bot turn: seconds from the end of the caller's audio to the
    first bot audio byte received (what a caller would perceive, minus the phone network)."""
    caller_id = scenario.get("caller_id", "+18285550199") or ""
    token = get_token(port, caller_id, call_sid)
    sid = "MZ" + call_sid[2:]
    caller_done = [None]
    inbox = bytearray()
    last_audio = [0.0]
    lines: list[tuple[str, str]] = []
    caller_msgs = [{"role": "system", "content": f"{CALLER_RULES}\n\nYOUR ROLE: {scenario['caller']}"}]

    async with websockets.connect(f"ws://127.0.0.1:{port}/ws", proxy=None) as ws:
        await ws.send(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))
        await ws.send(json.dumps({"event": "start", "sequenceNumber": "1", "streamSid": sid, "start": {
            "streamSid": sid, "callSid": call_sid, "accountSid": "AC", "tracks": ["inbound"],
            "customParameters": {"token": token, "caller": caller_id, "scenario": scenario["id"]},
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}}}))

        async def reader():
            async for msg in ws:
                m = json.loads(msg)
                if m.get("event") == "media":
                    now = time.monotonic()
                    if caller_done[0] is not None and client_turns is not None:
                        client_turns.append({"secs": round(now - caller_done[0], 3)})
                        caller_done[0] = None
                    inbox.extend(base64.b64decode(m["media"]["payload"]))
                    last_audio[0] = now

        rtask = asyncio.create_task(reader())

        async def send(audio: bytes):
            for i in range(0, len(audio), FRAME):
                await ws.send(json.dumps({"event": "media", "streamSid": sid, "media": {
                    "payload": base64.b64encode(audio[i:i + FRAME].ljust(FRAME, b"\xff")).decode()}}))
                await asyncio.sleep(0.02)

        async def bot_turn() -> str:
            """Keep the line open with silence until the bot has spoken and gone quiet."""
            start = time.monotonic()
            inbox.clear()
            while time.monotonic() - start < TURN_TIMEOUT:
                await send(SILENCE * 10)
                if inbox and time.monotonic() - last_audio[0] > SILENCE_GAP:
                    break
            return stt_mulaw(bytes(inbox))

        async def say(audio: bytes):
            await send(audio)
            caller_done[0] = time.monotonic()  # caller finished speaking; timer runs until bot audio arrives

        try:
            await converse(lines, caller_msgs, bot_turn, say)
        except websockets.ConnectionClosed:
            heard = stt_mulaw(bytes(inbox))
            if heard:
                lines.append(("AGENT", heard))
            lines.append(("SYSTEM", "server closed the media stream (bot left the call: transfer)"))
            rtask.cancel()
            return lines
        await ws.send(json.dumps({"event": "stop", "streamSid": sid}))
        await asyncio.sleep(1)
        rtask.cancel()
    return lines


async def converse(lines, caller_msgs, bot_turn, send):
    if True:
        for _ in range(MAX_TURNS):
            heard = await bot_turn()
            lines.append(("AGENT", heard or "(silence)"))
            caller_msgs.append({"role": "user", "content": heard or "(silence on the line)"})
            c = await oai.chat.completions.create(model="gpt-4.1", messages=caller_msgs, temperature=0.7)
            said = c.choices[0].message.content or ""
            caller_msgs.append({"role": "assistant", "content": said})
            clean = said.replace("[HANGUP]", "").strip()
            lines.append(("CALLER", clean))
            await send(tts(clean))
            if "[HANGUP]" in said:
                lines.append(("AGENT", await bot_turn() or "(silence)"))
                break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="routine_booking")
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "8790")))
    a = ap.parse_args()
    sc = next(s for s in SCENARIOS if s["id"] == a.scenario)
    print(f"--- simulated voice call: {sc['id']} ---")
    for who, text in asyncio.run(run(sc, a.port)):
        print(f"{who:6}: {text}")
