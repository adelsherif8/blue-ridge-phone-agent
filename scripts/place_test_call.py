"""Place a scripted test call to the bot so nobody has to dial in.

Twilio dials TWILIO_PHONE_NUMBER (the bot). The "caller" leg runs the TwiML
below: it waits, speaks a line, waits for Riley to answer, and so on.
The bot's side of the conversation shows up in the server log.

Usage: uv run python scripts/place_test_call.py [--from +1...]
"""

import argparse
import os
import time

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(override=True)

CALLER_SCRIPT = """<Response>
  <Pause length="9"/>
  <Say voice="Polly.Matthew">Hi, my kitchen sink is leaking under the cabinet. Can someone take a look?</Say>
  <Pause length="9"/>
  <Say voice="Polly.Matthew">Okay. What area do you cover?</Say>
  <Pause length="9"/>
  <Say voice="Polly.Matthew">Great, thanks. Bye.</Say>
  <Pause length="4"/>
  <Hangup/>
</Response>"""

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="from_", default=None, help="caller ID; defaults to the bot number")
args = ap.parse_args()

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
bot_number = os.environ["TWILIO_PHONE_NUMBER"]
call = client.calls.create(to=bot_number, from_=args.from_ or bot_number, twiml=CALLER_SCRIPT)
print(f"placed {call.sid}")
while True:
    time.sleep(3)
    c = client.calls(call.sid).fetch()
    if c.status in ("completed", "failed", "busy", "no-answer", "canceled"):
        print(f"status={c.status} duration={c.duration}s")
        break
