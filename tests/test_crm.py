import asyncio
import json
from datetime import datetime

import httpx
import pytest

from app.crm import CRMError, CRMSync, HubSpot, national, window_utc
from app.schedule import TZ, Board
from app.tools import Tools


class FakeHubSpot:
    """In-memory stand-in for the HubSpot endpoints we use. Records every request."""

    def __init__(self, fail_first: int = 0, fail_status: int = 429, contacts=None):
        self.contacts = dict(contacts or {})  # id -> properties
        self.meetings = {}  # id -> {"properties", "associations"}
        self.requests = []
        self.fail_first, self.fail_status = fail_first, fail_status
        self._next = 500

    def _id(self):
        self._next += 1
        return str(self._next)

    def handler(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        self.requests.append((req.method, req.url.path, body, req.headers.get("authorization")))
        if self.fail_first:
            self.fail_first -= 1
            return httpx.Response(self.fail_status, json={"message": "fail"})
        path = req.url.path
        if path == "/crm/v3/objects/contacts/search":
            for cid, props in self.contacts.items():
                for group in body["filterGroups"]:
                    f = group["filters"][0]
                    stored = props.get(f["propertyName"]) or ""
                    if f["propertyName"] == "hs_searchable_calculated_phone_number":
                        stored = national(props.get("phone") or "")
                    if stored and stored == f["value"]:
                        return httpx.Response(200, json={"total": 1, "results": [{"id": cid, "properties": props}]})
            return httpx.Response(200, json={"total": 0, "results": []})
        if path == "/crm/v3/objects/contacts" and req.method == "POST":
            cid = self._id()
            self.contacts[cid] = body["properties"]
            return httpx.Response(201, json={"id": cid, "properties": body["properties"]})
        if path.startswith("/crm/v3/objects/contacts/") and req.method == "PATCH":
            self.contacts[path.rsplit("/", 1)[1]].update(body["properties"])
            return httpx.Response(200, json={})
        if path == "/crm/v3/objects/meetings" and req.method == "POST":
            mid = self._id()
            self.meetings[mid] = body
            return httpx.Response(201, json={"id": mid})
        if path.startswith("/crm/v3/objects/meetings/") and req.method == "PATCH":
            self.meetings[path.rsplit("/", 1)[1]]["properties"].update(body["properties"])
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": f"no route {req.method} {path}"})


def client(fake: FakeHubSpot) -> HubSpot:
    return HubSpot("pat-test", transport=httpx.MockTransport(fake.handler), retries=3)


def board():
    return Board(now_fn=lambda: datetime(2026, 11, 4, 9, 30, tzinfo=TZ))


def booked_tools(fake, caller="+18285550142"):
    sync = CRMSync(client(fake))
    t = Tools(board(), caller_id=caller, on_job=sync.submit)
    t.run("check_slots", {"day": "tomorrow"})
    return t, sync


JOB = {"name": "Ana", "address": "41 Laurel Drive", "problem": "dripping faucet", "day": "tomorrow",
       "window": "2-4", "urgency": "routine"}


def test_window_is_converted_from_eastern_to_utc():
    # Nov 5 2026 is after DST ends (Nov 1): Eastern = UTC-5.
    assert window_utc("2026-11-05", "2-4") == ("2026-11-05T19:00:00.000Z", "2026-11-05T21:00:00.000Z")
    # July: Eastern daylight time = UTC-4.
    assert window_utc("2026-07-01", "8-10") == ("2026-07-01T12:00:00.000Z", "2026-07-01T14:00:00.000Z")


async def test_new_caller_creates_contact_and_linked_meeting():
    fake = FakeHubSpot()
    t, sync = booked_tools(fake)
    assert t.run("book_job", JOB)["status"] == "Booked"
    [res] = await sync.drain()
    assert res["ok"] and res["contact_created"]
    contact = fake.contacts[res["contact_id"]]
    assert contact["phone"] == "+18285550142" and contact["firstname"] == "Ana"
    assert contact["address"] == "41 Laurel Drive"
    meeting = fake.meetings[res["meeting_id"]]
    assert meeting["associations"] == [{"to": {"id": res["contact_id"]}, "types": [
        {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 200}]}]
    p = meeting["properties"]
    assert p["hs_meeting_start_time"] == p["hs_timestamp"] == "2026-11-05T19:00:00.000Z"
    assert p["hs_meeting_end_time"] == "2026-11-05T21:00:00.000Z"
    assert "BRP-1001" in p["hs_meeting_title"] and p["hs_meeting_outcome"] == "SCHEDULED"
    assert all(r[3] == "Bearer pat-test" for r in fake.requests)
    assert t.board.jobs[0].meeting_id == res["meeting_id"]


async def test_returning_caller_is_matched_by_phone_not_duplicated():
    fake = FakeHubSpot(contacts={"77": {"firstname": "Ana Maria", "phone": "+18285550142", "address": "old"}})
    t, sync = booked_tools(fake)
    t.run("book_job", {**JOB, "name": "Anna"})
    [res] = await sync.drain()
    assert res["contact_id"] == "77" and not res["contact_created"]
    assert len(fake.contacts) == 1
    assert fake.contacts["77"]["firstname"] == "Ana Maria"  # stored name kept, STT spelling ignored
    assert fake.contacts["77"]["address"] == "41 Laurel Drive"


async def test_reschedule_moves_the_same_meeting():
    fake = FakeHubSpot()
    t, sync = booked_tools(fake)
    jid = t.run("book_job", {**JOB, "window": "8-10"})["job_id"]
    t.run("change_booking", {"job_id": jid, "day": "tomorrow", "window": "12-2"})  # submitted before sync ran
    results = await sync.drain()
    assert [r["ok"] for r in results] == [True, True]
    assert len(fake.meetings) == 1  # no race, no second meeting
    p = next(iter(fake.meetings.values()))["properties"]
    assert p["hs_meeting_start_time"] == "2026-11-05T17:00:00.000Z" and p["hs_meeting_outcome"] == "RESCHEDULED"


async def test_emergency_is_flagged_in_meeting_title():
    fake = FakeHubSpot()
    t, sync = booked_tools(fake)
    t.run("check_slots", {"day": "today"})
    t.run("book_job", {**JOB, "day": "today", "window": "12-2", "urgency": "emergency", "problem": "burst pipe"})
    [res] = await sync.drain()
    assert fake.meetings[res["meeting_id"]]["properties"]["hs_meeting_title"].startswith("EMERGENCY")


async def test_rate_limit_is_retried():
    fake = FakeHubSpot(fail_first=2, fail_status=429)
    t, sync = booked_tools(fake)
    t.run("book_job", JOB)
    [res] = await sync.drain()
    assert res["ok"] and len(fake.meetings) == 1


async def test_hubspot_error_is_recorded_not_raised_and_booking_stands():
    fake = FakeHubSpot(fail_first=10, fail_status=401)
    t, sync = booked_tools(fake)
    assert t.run("book_job", JOB)["status"] == "Booked"
    [res] = await sync.drain()
    assert not res["ok"] and "401" in res["error"]
    assert len(t.board.jobs) == 1


async def test_client_raises_crm_error_on_4xx():
    fake = FakeHubSpot(fail_first=1, fail_status=400)
    with pytest.raises(CRMError):
        await client(fake).find_contact_by_phone("+18285550142")


async def test_no_crm_configured_is_a_no_op():
    sync = CRMSync(None)
    t = Tools(board(), caller_id="+18285550142", on_job=sync.submit)
    t.run("check_slots", {"day": "tomorrow"})
    assert t.run("book_job", JOB)["status"] == "Booked"
    assert await sync.drain() == []


async def test_callbacks_and_failed_bookings_do_not_touch_crm():
    fake = FakeHubSpot()
    t, sync = booked_tools(fake)
    t.run("request_callback", {"name": "Joyce", "reason": "quote"})
    t.run("book_job", {**JOB, "address": ""})
    assert await sync.drain() == [] and fake.requests == []
