"""Debug helper: place a silent call to the bot number, record it, and
transcribe the recording with Deepgram to see what a caller hears."""

import base64
import json
import os
import time
import urllib.request

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(".env")
sid, tok = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
c = Client(sid, tok)
n = os.environ["TWILIO_PHONE_NUMBER"]
twiml = os.getenv("CALLER_TWIML", '<Response><Pause length="25"/></Response>')
call = c.calls.create(to=n, from_=os.getenv("CALLER_ID", n), record=True, twiml=twiml)
while c.calls(call.sid).fetch().status not in ("completed", "failed", "busy", "no-answer", "canceled"):
    time.sleep(3)
time.sleep(6)
recs = c.recordings.list(call_sid=call.sid)
print("duration", c.calls(call.sid).fetch().duration, "recordings", len(recs))
if recs:
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Recordings/{recs[0].sid}.wav")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode())
    audio = urllib.request.urlopen(req).read()
    dg = urllib.request.Request(
        "https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true",
        data=audio,
        headers={"Authorization": "Token " + os.environ["DEEPGRAM_API_KEY"], "Content-Type": "audio/wav"},
    )
    r = json.load(urllib.request.urlopen(dg))
    print("HEARD:", r["results"]["channels"][0]["alternatives"][0]["transcript"])
