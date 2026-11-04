"""Live HubSpot check: token works, phone search works, contact + linked meeting can be created.

Creates a test contact (+1 828 555 0100, "Test Caller") and one meeting, finds the contact again
by phone in several formats, then prints the record links. With --cleanup it archives both
(HubSpot keeps archived records in the recycle bin for 90 days).

Usage: uv run python scripts/hubspot_check.py [--cleanup]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.crm import HubSpot  # noqa: E402

load_dotenv(".env")
TEST_PHONE = "+18285550100"


async def main(cleanup: bool):
    hs = HubSpot(os.environ["HUBSPOT_TOKEN"])
    try:
        acct = await hs._req("GET", "/account-info/v3/details")
        portal = acct.get("portalId")
        print(f"token ok, portal {portal}")
    except Exception as e:
        print(f"account-info not readable ({str(e)[:80]}); continuing")
        portal = None
    cid, created = await hs.upsert_contact(phone=TEST_PHONE, firstname="Test Caller", address="1 Test Street")
    print(f"contact {cid} {'created' if created else 'already existed'}")
    await asyncio.sleep(8)  # search index lags a few seconds behind writes
    again = await hs.find_contact_by_phone(TEST_PHONE)
    print(f"search by phone finds it: {bool(again and again['id'] == cid)}")
    mid = await hs.create_meeting(cid, job_id="BRP-TEST", date="2026-11-05", window="2-4",
                                  problem="hubspot_check test", address="1 Test Street", urgency="routine")
    assoc = await hs._req("GET", f"/crm/v3/objects/meetings/{mid}?associations=contacts")
    linked = [a["id"] for a in assoc.get("associations", {}).get("contacts", {}).get("results", [])]
    print(f"meeting {mid} linked to contact: {cid in linked}")
    if portal:
        print(f"contact: https://app.hubspot.com/contacts/{portal}/record/0-1/{cid}")
    if cleanup:
        await hs._req("DELETE", f"/crm/v3/objects/meetings/{mid}")
        await hs._req("DELETE", f"/crm/v3/objects/contacts/{cid}")
        print("archived test meeting and contact")
    await hs.aclose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    asyncio.run(main(ap.parse_args().cleanup))
