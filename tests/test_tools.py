from datetime import datetime

import pytest

from app.facts import SYSTEM_PROMPT, call_context
from app.schedule import TZ, Board, normalize_window
from app.tools import Tools


def board_at(hour: int, minute: int = 0) -> Board:
    return Board(now_fn=lambda: datetime(2026, 11, 4, hour, minute, tzinfo=TZ))


def windows(result):
    return [w["window"] for w in result["open_windows"]]


def job(**kw):
    base = dict(name="Ana", phone="+15551234567", address="12 Oak St", problem="leaking sink",
                day="tomorrow", window="4-6", urgency="routine")
    base.update(kw)
    return base


# --- check_slots ---------------------------------------------------------

def test_today_early_morning_matches_seed_board():
    # 7 AM: nothing has started. 8-10: only Luis free; 10-12: Dave busy, Mike busy, Luis busy -> closed.
    assert windows(board_at(7).check_slots("today")) == ["8-10", "12-2", "2-4", "4-6"]


def test_started_windows_are_not_offered():
    assert windows(board_at(13).check_slots("today")) == ["2-4", "4-6"]
    assert windows(board_at(16, 5).check_slots("today")) == []


def test_late_evening_today_is_empty_but_tomorrow_is_open():
    b = board_at(21)
    assert b.check_slots("today")["open_windows"] == []
    assert "Nothing open" in b.check_slots("today")["note"]
    assert windows(b.check_slots("tomorrow")) == ["8-10", "10-12", "12-2", "2-4", "4-6"]


def test_check_slots_rejects_other_days():
    assert "error" in board_at(9).check_slots("friday")


def test_open_windows_carry_spoken_wording():
    first = board_at(7).check_slots("tomorrow")["open_windows"][0]
    assert first == {"window": "8-10", "say": "eight to ten AM"}


# --- book_job ------------------------------------------------------------

def test_book_success_assigns_first_free_truck_and_records_job():
    b = board_at(9)
    r = b.book_job(**job())
    assert r["status"] == "Booked" and r["job_id"] == "BRP-1001"
    assert r["technician"] == "Mike" and r["say"] == "four to six PM"
    assert b.jobs[0].date == "2026-11-05" and b.jobs[0].phone == "+15551234567"


def test_booking_fills_window_until_all_trucks_busy():
    b = board_at(9)
    for i in range(3):
        assert b.book_job(**job(name=f"C{i}"))["status"] == "Booked"
    r = b.book_job(**job(name="Late"))
    assert r["status"] == "Not booked" and "4-6" not in [w["window"] for w in r["open_windows"]]


def test_cannot_book_a_booked_window():
    # Tomorrow 2-4: Dave (repipe) and Luis (water heater) busy, Mike free -> one booking only.
    b = board_at(9)
    assert b.book_job(**job(window="2-4"))["status"] == "Booked"
    assert b.book_job(**job(window="2-4"))["status"] == "Not booked"


def test_cannot_book_a_window_that_already_started():
    r = board_at(15).book_job(**job(day="today", window="2-4"))
    assert r["status"] == "Not booked" and windows(r) == ["4-6"]


@pytest.mark.parametrize("field", ["name", "phone", "address", "problem"])
def test_missing_required_field_is_not_booked(field):
    r = board_at(9).book_job(**job(**{field: "  "}))
    assert r["status"] == "Not booked" and field in r["reason"]


@pytest.mark.parametrize("raw,key", [("8-10", "8-10"), ("8 to 10", "8-10"), ("10am-12pm", "10-12"),
                                     ("noon to 2", "12-2"), ("2-4 PM", "2-4"), ("4 – 6", "4-6"),
                                     ("3-5", None), ("morning", None)])
def test_window_normalization(raw, key):
    assert normalize_window(raw) == key


def test_bad_day_and_window_rejected():
    b = board_at(9)
    assert b.book_job(**job(day="next week"))["status"] == "Not booked"
    assert b.book_job(**job(window="7-9"))["reason"] == "Unknown window."


def test_urgency_is_normalized():
    b = board_at(9)
    b.book_job(**job(urgency="EMERGENCY!!"))
    assert b.jobs[0].urgency == "routine"
    b.book_job(**job(urgency="emergency", window="12-2"))
    assert b.jobs[1].urgency == "emergency"


# --- Tools wrapper -------------------------------------------------------

def checked(t: Tools) -> Tools:
    t.run("check_slots", {"day": "today"})
    t.run("check_slots", {"day": "tomorrow"})
    return t


def test_tools_use_caller_id_when_no_phone_given_and_never_log_phone():
    t = checked(Tools(board_at(9), caller_id="+15559876543"))
    args = job()
    args.pop("phone")
    assert t.run("book_job", args)["status"] == "Booked"
    assert t.board.jobs[0].phone == "+15559876543"
    t.run("book_job", job(window="12-2", phone="555 000 1111"))
    assert t.board.jobs[1].phone == "+15550001111"
    assert all("phone" not in c["args"] for c in t.calls)


def test_hidden_caller_id_without_phone_is_not_booked():
    t = checked(Tools(board_at(9), caller_id=None))
    args = job()
    args.pop("phone")
    r = t.run("book_job", args)
    assert r["status"] == "Not booked" and "phone" in r["reason"]


def test_unknown_tool():
    assert "error" in Tools(board_at(9)).run("delete_everything", {})


def test_openai_tool_schema_shape():
    specs = Tools(board_at(9)).openai_tools()
    assert [s["function"]["name"] for s in specs] == ["check_slots", "book_job"]
    assert specs[1]["function"]["parameters"]["required"][:3] == ["name", "address", "problem"]


# --- prompt rules --------------------------------------------------------

def test_system_prompt_is_stable_and_call_data_is_separate():
    assert "{" not in SYSTEM_PROMPT  # no unfilled template slots
    ctx = call_context(datetime(2026, 11, 4, 14, 5, tzinfo=TZ), "+15551234567")
    assert "Wednesday November 4, 2:05 PM" in ctx and "+15551234567" in ctx
    assert "hidden" in call_context(datetime(2026, 11, 4, tzinfo=TZ), None)


def test_prompt_has_only_the_allowed_price():
    import re
    assert not re.search(r"\$\d", SYSTEM_PROMPT)
    assert "eighty-nine dollar" in SYSTEM_PROMPT


def test_book_job_refused_until_that_day_was_checked():
    t = Tools(board_at(9), caller_id="+15559876543")
    r = t.run("book_job", job())
    assert r["status"] == "Not booked" and "check_slots" in r["reason"]
    t.run("check_slots", {"day": "today"})
    assert t.run("book_job", job())["status"] == "Not booked"  # tomorrow still unchecked
    t.run("check_slots", {"day": "tomorrow"})
    assert t.run("book_job", job())["status"] == "Booked"


@pytest.mark.parametrize("raw,e164", [
    ("828 555 0142", "+18285550142"), ("(828) 555-0142", "+18285550142"), ("1-828-555-0142", "+18285550142"),
    ("+18285550142", "+18285550142"), ("eight two eight five five five oh one four two", "+18285550142"),
    ("+20 100 555 0199", "+201005550199"), ("555 0142", None), ("", None)])
def test_phone_normalization(raw, e164):
    from app.schedule import normalize_phone
    assert normalize_phone(raw) == e164


def test_incomplete_phone_is_not_booked():
    r = board_at(9).book_job(**job(phone="555 0142"))
    assert r["status"] == "Not booked" and "ten-digit" in r["reason"]
