"""Simulated phone caller: speaks to the bot over the same WebSocket protocol
Twilio Media Streams uses, without the phone network.

1. POST /voice with a valid Twilio signature -> get the stream token from TwiML.
2. Open /ws, send Twilio "connected" + "start" events with that token.
3. Stream caller lines (Deepgram TTS, 8 kHz mu-law) in real time, with silence
   between turns, and record everything the bot sends back.
4. Transcribe the bot's audio with Deepgram and print the conversation.

Usage: uv run python scripts/sim_call.py [--port 8790]
"""

import argparse
import asyncio
import base64
import json
import os
import re
import urllib.parse
import urllib.request

import websockets
from dotenv import load_dotenv
from twilio.request_validator import RequestValidator

load_dotenv(".env")
DG = os.environ["DEEPGRAM_API_KEY"]
CALLER_LINES = [
    "Hi, my kitchen sink is leaking under the cabinet. Can someone take a look?",
    "Okay. What area do you cover?",
    "Great, thanks. Bye.",
]
FRAME = 160  # 20 ms of 8 kHz mu-law
SILENCE = b"\xff" * FRAME


def tts(text: str) -> bytes:
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/speak?model=aura-2-orion-en&encoding=mulaw&sample_rate=8000&container=none",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {DG}", "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req).read()


def stt_mulaw(audio: bytes) -> str:
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&encoding=mulaw&sample_rate=8000",
        data=audio,
        headers={"Authorization": f"Token {DG}", "Content-Type": "audio/mulaw"},
    )
    r = json.load(urllib.request.urlopen(req))
    return r["results"]["channels"][0]["alternatives"][0]["transcript"]


def get_token(port: int) -> str:
    public = os.environ["PUBLIC_URL"].rstrip("/") + "/voice"
    form = {"CallSid": "CAsimulated", "From": "+15550000000", "To": os.environ.get("TWILIO_PHONE_NUMBER", "")}
    sig = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"]).compute_signature(public, form)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/voice", data=urllib.parse.urlencode(form).encode(), headers={"X-Twilio-Signature": sig}
    )
    twiml = urllib.request.urlopen(req).read().decode()
    return re.search(r'name="token" value="([^"]+)"', twiml).group(1)


async def main(port: int):
    token = get_token(port)
    caller_audio = [tts(t) for t in CALLER_LINES]
    bot_turns: list[bytearray] = [bytearray()]
    sid = "MZsimulated"

    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        await ws.send(json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"}))
        await ws.send(json.dumps({"event": "start", "sequenceNumber": "1", "streamSid": sid,
                                  "start": {"streamSid": sid, "callSid": "CAsimulated", "accountSid": "AC",
                                            "tracks": ["inbound"], "customParameters": {"token": token},
                                            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}}}))

        async def reader():
            async for msg in ws:
                m = json.loads(msg)
                if m.get("event") == "media":
                    bot_turns[-1].extend(base64.b64decode(m["media"]["payload"]))

        rtask = asyncio.create_task(reader())

        async def send_audio(audio: bytes):
            for i in range(0, len(audio), FRAME):
                chunk = audio[i:i + FRAME].ljust(FRAME, b"\xff")
                await ws.send(json.dumps({"event": "media", "streamSid": sid,
                                          "media": {"payload": base64.b64encode(chunk).decode()}}))
                await asyncio.sleep(0.02)

        await send_audio(SILENCE * 300)  # 6 s: let the greeting play
        for audio in caller_audio:
            bot_turns.append(bytearray())
            await send_audio(audio)
            await send_audio(SILENCE * 400)  # 8 s for the bot to answer
        await ws.send(json.dumps({"event": "stop", "streamSid": sid}))
        await asyncio.sleep(1)
        rtask.cancel()

    print("--- simulated call ---")
    for i, turn in enumerate(bot_turns):
        if i > 0:
            print(f"CALLER: {CALLER_LINES[i - 1]}")
        text = stt_mulaw(bytes(turn)) if len(turn) > 1600 else "(no audio)"
        print(f"BOT:    {text}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "8790")))
    asyncio.run(main(ap.parse_args().port))
