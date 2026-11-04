"""Point the Twilio number's voice webhook at PUBLIC_URL/voice."""

import os

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(override=True)
client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
number = os.environ["TWILIO_PHONE_NUMBER"]
url = os.environ["PUBLIC_URL"].rstrip("/") + "/voice"
matches = client.incoming_phone_numbers.list(phone_number=number)
if not matches:
    raise SystemExit("TWILIO_PHONE_NUMBER not found on this account")
matches[0].update(voice_url=url, voice_method="POST")
print(f"voice webhook -> {url}")
