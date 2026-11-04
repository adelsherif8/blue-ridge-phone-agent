"""Blue Ridge Plumbing truck board: the only source of truth for availability.

Three trucks, five 2-hour windows a day, bookable today or tomorrow. Windows that
have already started (Eastern time) are not offered. Pure logic, no I/O, so the
tools can be unit-tested without a phone call or an LLM.
"""

from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")

# key -> (start hour, spoken label)
WINDOWS = {
    "8-10": (8, "eight to ten AM"),
    "10-12": (10, "ten AM to noon"),
    "12-2": (12, "noon to two PM"),
    "2-4": (14, "two to four PM"),
    "4-6": (16, "four to six PM"),
}
DAYS = ("today", "tomorrow")

# Demo board (today matches VoiceDesk's recovery dashboard). A value = already booked.
SEED = {
    "today": {
        "Mike, truck 1": {"8-10": "Water heater", "10-12": "Drain"},
        "Dave, truck 2": {"8-10": "Repipe", "10-12": "Repipe", "12-2": "Repipe"},
        "Luis, truck 3": {"10-12": "Faucet", "12-2": "Leak"},
    },
    "tomorrow": {
        "Mike, truck 1": {"8-10": "Maintenance"},
        "Dave, truck 2": {"8-10": "Repipe", "10-12": "Repipe", "12-2": "Repipe", "2-4": "Repipe"},
        "Luis, truck 3": {"2-4": "Water heater"},
    },
}


def normalize_window(raw: str) -> str | None:
    """Accept '8-10', '8 to 10', '8-10am', '10am-12pm', 'noon to 2', '2 to 4 PM' and similar."""
    s = raw.lower().replace("noon", "12").replace("–", "-").replace(" to ", "-")
    nums = re.findall(r"\d{1,2}", s)
    if len(nums) < 2:
        return None
    a, b = (int(n) % 12 or 12 for n in nums[:2])
    key = f"{a}-{b}"
    return key if key in WINDOWS else None


_DIGIT_WORDS = {"zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                "six": "6", "seven": "7", "eight": "8", "nine": "9"}


def normalize_phone(raw: str) -> str | None:
    """'828 555 0142', '(828) 555-0142', 'eight two eight five five five oh one four two' -> '+18285550142'.
    Non-US numbers already in +E.164 form are kept. Returns None if it is not a full number."""
    s = (raw or "").strip()
    if s.startswith("+") and not s.startswith("+1"):
        digits = re.sub(r"\D", "", s)
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    words = re.findall(r"[a-z]+|\d", s.lower())
    digits = "".join(_DIGIT_WORDS.get(w, w if w.isdigit() else "") for w in words)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"+1{digits}" if len(digits) == 10 else None


def normalize_day(raw: str) -> str | None:
    s = raw.strip().lower()
    return s if s in DAYS else None


@dataclass
class Job:
    job_id: str
    name: str
    phone: str
    address: str
    problem: str
    day: str
    window: str
    urgency: str
    truck: str
    date: str


@dataclass
class Board:
    now_fn: callable = field(default=lambda: datetime.now(TZ))
    slots: dict = field(default_factory=lambda: copy.deepcopy(SEED))
    jobs: list[Job] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1001))

    def _started(self, day: str, window: str) -> bool:
        if day != "today":
            return False
        return self.now_fn().hour >= WINDOWS[window][0]

    def free_trucks(self, day: str, window: str) -> list[str]:
        if self._started(day, window):
            return []
        return [t for t, booked in self.slots[day].items() if window not in booked]

    def open_windows(self, day: str) -> list[str]:
        return [w for w in WINDOWS if self.free_trucks(day, w)]

    def check_slots(self, day: str) -> dict:
        d = normalize_day(day)
        if not d:
            return {"error": "Only today or tomorrow can be checked. For a later day, offer a callback from the office."}
        open_ = self.open_windows(d)
        return {
            "day": d,
            "open_windows": [{"window": w, "say": WINDOWS[w][1]} for w in open_],
            "note": "Offer at most two of these. Never offer a window that is not listed."
            if open_
            else f"Nothing open {d}.",
        }

    def book_job(self, *, name: str, phone: str, address: str, problem: str, day: str, window: str,
                 urgency: str = "routine") -> dict:
        missing = [k for k, v in (("name", name), ("phone", phone), ("address", address), ("problem", problem))
                   if not (v or "").strip()]
        if missing:
            return {"status": "Not booked", "reason": f"Missing {', '.join(missing)}. Ask the caller for it."}
        e164 = normalize_phone(phone)
        if not e164:
            return {"status": "Not booked", "reason": "Phone number is incomplete. Ask for the full ten-digit number."}
        d, w = normalize_day(day or ""), normalize_window(window or "")
        if not d:
            return {"status": "Not booked", "reason": "Day must be today or tomorrow."}
        if not w:
            return {"status": "Not booked", "reason": "Unknown window.", "open_windows": self._alts(d)}
        trucks = self.free_trucks(d, w)
        if not trucks:
            return {"status": "Not booked", "reason": "That window is not open.", "open_windows": self._alts(d)}
        truck = trucks[0]
        self.slots[d][truck][w] = problem.strip()[:40]
        date = self.now_fn().date()
        if d == "tomorrow":
            date = date.fromordinal(date.toordinal() + 1)
        job = Job(f"BRP-{next(self._ids)}", name.strip(), e164, address.strip(), problem.strip(),
                  d, w, "emergency" if urgency == "emergency" else "routine", truck, date.isoformat())
        self.jobs.append(job)
        return {"status": "Booked", "job_id": job.job_id, "day": d, "window": w, "say": WINDOWS[w][1],
                "technician": truck.split(",")[0], "fee": "eighty-nine dollar diagnostic call-out fee"}

    def _alts(self, day: str) -> list[dict]:
        return [{"window": w, "say": WINDOWS[w][1]} for w in self.open_windows(day)]
