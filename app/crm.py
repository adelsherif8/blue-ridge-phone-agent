"""HubSpot CRM sync: upsert the caller as a contact (matched by phone) and add a meeting
linked to that contact for each booked visit.

Auth: a HubSpot Service Key (Bearer token) with contacts read/write; meetings use the
CRM objects API. Runs after the call has the booking, so HubSpot latency never reaches
the caller. All methods are async and safe to call from the Pipecat event loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from loguru import logger

from app.util import mask_phone

BASE = "https://api.hubapi.com"
MEETING_TO_CONTACT = 200  # HUBSPOT_DEFINED association type id (meeting -> contact)
TZ = ZoneInfo("America/New_York")
WINDOW_START = {"8-10": 8, "10-12": 10, "12-2": 12, "2-4": 14, "4-6": 16}


class CRMError(Exception):
    pass


def window_utc(date_iso: str, window: str) -> tuple[str, str]:
    """Visit window in Eastern time -> (start, end) as UTC ISO 8601 strings HubSpot accepts."""
    start = datetime.fromisoformat(date_iso).replace(hour=WINDOW_START[window], tzinfo=TZ)
    end = start + timedelta(hours=2)
    fmt = lambda d: d.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z")  # noqa: E731
    return fmt(start), fmt(end)


def national(e164: str) -> str:
    """HubSpot phone search matches area code + local number, without the country code."""
    return e164[2:] if e164.startswith("+1") else e164.lstrip("+")


class HubSpot:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None, retries: int = 3):
        self.http = httpx.AsyncClient(base_url=BASE, timeout=10, transport=transport,
                                      headers={"Authorization": f"Bearer {token}"})
        self.retries = retries

    async def _req(self, method: str, path: str, json: dict | None = None) -> dict:
        for attempt in range(self.retries + 1):
            r = await self.http.request(method, path, json=json)
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < self.retries:
                    await asyncio.sleep(min(2 ** attempt, 8) * 0.5)
                    continue
            if r.status_code >= 400:
                raise CRMError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
            return r.json() if r.content else {}
        raise CRMError(f"{method} {path}: retries exhausted")

    async def find_contact_by_phone(self, e164: str) -> dict | None:
        digits = national(e164)
        body = {
            "filterGroups": [  # groups are OR'd
                {"filters": [{"propertyName": "phone", "operator": "EQ", "value": e164}]},
                {"filters": [{"propertyName": "hs_searchable_calculated_phone_number", "operator": "EQ", "value": digits}]},
                {"filters": [{"propertyName": "mobilephone", "operator": "EQ", "value": e164}]},
            ],
            "properties": ["firstname", "phone", "mobilephone", "address"],
            "limit": 1,
        }
        res = await self._req("POST", "/crm/v3/objects/contacts/search", body)
        return (res.get("results") or [None])[0]

    async def upsert_contact(self, *, phone: str, firstname: str, address: str = "") -> tuple[str, bool]:
        """Returns (contact_id, created). Never overwrites a stored name with the caller's guess."""
        existing = await self.find_contact_by_phone(phone)
        if existing:
            props = existing.get("properties") or {}
            update = {}
            if not props.get("firstname") and firstname:
                update["firstname"] = firstname
            if address and props.get("address") != address:
                update["address"] = address
            if update:
                await self._req("PATCH", f"/crm/v3/objects/contacts/{existing['id']}", {"properties": update})
            return existing["id"], False
        created = await self._req("POST", "/crm/v3/objects/contacts", {"properties": {
            "firstname": firstname or "Caller", "phone": phone, "address": address,
            "lifecyclestage": "lead"}})
        return created["id"], True

    async def create_meeting(self, contact_id: str, *, job_id: str, date: str, window: str, problem: str,
                             address: str, urgency: str) -> str:
        start, end = window_utc(date, window)
        title = f"{'EMERGENCY ' if urgency == 'emergency' else ''}Plumbing visit {job_id}: {problem}"[:200]
        body = {
            "properties": {
                "hs_timestamp": start,
                "hs_meeting_title": title,
                "hs_meeting_body": f"Job {job_id}. Problem: {problem}. Address: {address}. Urgency: {urgency}. "
                                   "Booked by the Blue Ridge Plumbing phone agent.",
                "hs_meeting_start_time": start,
                "hs_meeting_end_time": end,
                "hs_meeting_location": address,
                "hs_meeting_outcome": "SCHEDULED",
            },
            "associations": [{"to": {"id": contact_id}, "types": [
                {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": MEETING_TO_CONTACT}]}],
        }
        return (await self._req("POST", "/crm/v3/objects/meetings", body))["id"]

    async def move_meeting(self, meeting_id: str, *, date: str, window: str) -> None:
        start, end = window_utc(date, window)
        await self._req("PATCH", f"/crm/v3/objects/meetings/{meeting_id}", {"properties": {
            "hs_timestamp": start, "hs_meeting_start_time": start, "hs_meeting_end_time": end,
            "hs_meeting_outcome": "RESCHEDULED"}})

    async def sync_job(self, job) -> dict:
        """Upsert contact + create (or move) the job's meeting. Returns ids for the call log."""
        contact_id, created = await self.upsert_contact(phone=job.phone, firstname=job.name, address=job.address)
        if getattr(job, "meeting_id", None):
            await self.move_meeting(job.meeting_id, date=job.date, window=job.window)
            meeting_id = job.meeting_id
        else:
            meeting_id = await self.create_meeting(contact_id, job_id=job.job_id, date=job.date, window=job.window,
                                                   problem=job.problem, address=job.address, urgency=job.urgency)
            job.meeting_id = meeting_id
        logger.info(f"CRM {job.job_id}: contact {contact_id} ({'created' if created else 'updated'}), "
                    f"meeting {meeting_id}, caller {mask_phone(job.phone)}")
        return {"contact_id": contact_id, "contact_created": created, "meeting_id": meeting_id}

    async def aclose(self):
        await self.http.aclose()


class CRMSync:
    """Runs CRM writes for one call in the background, one at a time, and records the outcome.

    A booking followed by a quick change must not race (two meetings), so syncs are serialized.
    Failures are logged and kept in `results`; the caller is never told about CRM errors.
    """

    def __init__(self, crm: HubSpot | None):
        self.crm = crm
        self._lock = asyncio.Lock()
        self.tasks: list[asyncio.Task] = []
        self.results: list[dict] = []

    def submit(self, job) -> None:
        if self.crm:
            self.tasks.append(asyncio.create_task(self._run(job)))

    async def _run(self, job) -> None:
        async with self._lock:
            try:
                self.results.append({"job_id": job.job_id, "ok": True, **await self.crm.sync_job(job)})
            except Exception as e:  # keep the call alive whatever HubSpot does
                logger.error(f"CRM sync failed for {job.job_id}: {e}")
                self.results.append({"job_id": job.job_id, "ok": False, "error": str(e)[:300]})

    async def drain(self) -> list[dict]:
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        return self.results
