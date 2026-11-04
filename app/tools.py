"""LLM tools. One definition, used by the Pipecat bot and by the text eval harness."""

from __future__ import annotations

import json

from loguru import logger

from app.schedule import Board

TOOL_SPECS = [
    {
        "name": "check_slots",
        "description": "List the open technician windows for today or tomorrow. Call before offering any time.",
        "properties": {"day": {"type": "string", "enum": ["today", "tomorrow"]}},
        "required": ["day"],
    },
    {
        "name": "book_job",
        "description": "Book a technician visit in an open window. Needs the caller's name, service address and problem.",
        "properties": {
            "name": {"type": "string", "description": "Caller's first name"},
            "address": {"type": "string", "description": "Service street address in WRITTEN form with digits, e.g. '41 Laurel Drive' (not 'four one Laurel Drive')"},
            "problem": {"type": "string", "description": "Short description of the plumbing problem"},
            "day": {"type": "string", "enum": ["today", "tomorrow"]},
            "window": {"type": "string", "enum": ["8-10", "10-12", "12-2", "2-4", "4-6"]},
            "urgency": {"type": "string", "enum": ["routine", "emergency"]},
            "phone": {"type": "string", "description": "Callback number in digits, e.g. '828 555 0142'. Required when the caller ID is hidden; otherwise only if the caller gives a different one"},
        },
        "required": ["name", "address", "problem", "day", "window", "urgency"],
    },
    {
        "name": "change_booking",
        "description": "Move a visit booked earlier IN THIS CALL to another open window (use instead of booking again).",
        "properties": {
            "job_id": {"type": "string", "description": "job_id returned by book_job in this call"},
            "day": {"type": "string", "enum": ["today", "tomorrow"]},
            "window": {"type": "string", "enum": ["8-10", "10-12", "12-2", "2-4", "4-6"]},
        },
        "required": ["job_id", "day", "window"],
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the live call to the on-call person. Use for: the caller wants a person now; an "
                       "emergency (burst pipe, flooding, sewage, no water) after the safety advice; gas smell or danger "
                       "after the safety instructions; or when you cannot help after two tries. The system tells the "
                       "caller to hold; say nothing after calling it.",
        "properties": {
            "reason": {"type": "string", "enum": ["caller_request", "emergency", "stuck", "safety"]},
            "summary": {"type": "string", "description": "One sentence for the person taking the call: who, what, where"},
        },
        "required": ["reason", "summary"],
    },
    {
        "name": "request_callback",
        "description": "Save a request for a person at the office to call the caller back (owner or person requested, "
                       "questions you cannot answer, visits after tomorrow, quotes).",
        "properties": {
            "name": {"type": "string", "description": "Caller's first name, or 'Caller' if they will not give it"},
            "reason": {"type": "string", "description": "One sentence: what the office should call about"},
            "phone": {"type": "string", "description": "Callback number, only if different from the caller ID or it is hidden"},
        },
        "required": ["name", "reason"],
    },
]

FILLERS = {"check_slots": "One sec, checking the board.", "book_job": "One sec, booking that in.",
           "request_callback": "One sec, noting that for the office.", "change_booking": "One sec, moving that."}
NO_FILLER = {"transfer_to_human"}  # the transfer has its own hold line


class Tools:
    """Runs tool calls for one phone call against a board."""

    def __init__(self, board: Board, caller_id: str | None = None, on_job=None, on_transfer=None):
        self.board = board
        self.caller_id = caller_id
        self.on_job = on_job  # called with the Job after a booking or change (CRM sync)
        self.on_transfer = on_transfer  # called with (reason, summary); None = nobody to transfer to
        self.transfer: dict | None = None
        self.checked_days: set[str] = set()
        self.booked_ids: list[str] = []  # jobs booked in this call; only these may be changed
        self.calls: list[dict] = []  # every call and result, for the call log and evals

    def run(self, name: str, args: dict) -> dict:
        if name == "check_slots":
            result = self.board.check_slots(args.get("day", ""))
            if "day" in result:
                self.checked_days.add(result["day"])
        elif name == "book_job" and self.booked_ids:
            # One visit per call. A second book_job is almost always a reschedule; route it to change_booking.
            result = {"status": "Not booked", "reason": f"This caller already has visit {self.booked_ids[-1]}. "
                      "To move it, call change_booking with that job_id."}
        elif name in ("book_job", "change_booking") and (args.get("day") or "").lower() not in self.checked_days:
            # Guardrail in code, not just the prompt: never book a day nobody has looked at.
            result = {"status": "Not booked", "reason": "Call check_slots for this day first, then offer an open window."}
        elif name == "book_job":
            result = self.board.book_job(
                name=args.get("name", ""),
                phone=args.get("phone") or self.caller_id or "",
                address=args.get("address", ""),
                problem=args.get("problem", ""),
                day=args.get("day", ""),
                window=args.get("window", ""),
                urgency=args.get("urgency", "routine"),
            )
        elif name == "change_booking":
            if args.get("job_id") not in self.booked_ids:
                result = {"status": "Not changed", "reason": "Only a visit booked in this call can be changed."}
            else:
                result = self.board.change_booking(args["job_id"], day=args.get("day", ""), window=args.get("window", ""))
        elif name == "transfer_to_human":
            reason, summary = args.get("reason", ""), (args.get("summary") or "").strip()
            if self.transfer:
                result = {"status": "Already transferring"}
            elif reason not in ("caller_request", "emergency", "stuck", "safety") or not summary:
                result = {"status": "Not transferred", "reason": "Give a valid reason and a one-sentence summary."}
            elif not self.on_transfer:
                result = {"status": "Unavailable",
                          "reason": "No one can take a transfer right now. Offer a callback from the office instead."}
            else:
                self.transfer = {"reason": reason, "summary": summary}
                logger.info(f"TRANSFER reason={reason} summary={summary}")
                self.on_transfer(reason, summary)
                result = {"status": "Transferring", "note": "The system is telling the caller to hold. Say nothing more."}
        elif name == "request_callback":
            result = self.board.request_callback(name=args.get("name", ""), reason=args.get("reason", ""),
                                                 phone=args.get("phone") or self.caller_id or "")
        else:
            result = {"error": f"unknown tool {name}"}
        if name == "book_job" and result.get("status") == "Booked":
            self.booked_ids.append(result["job_id"])
        if self.on_job and result.get("status") in ("Booked", "Changed"):
            self.on_job(next(j for j in self.board.jobs if j.job_id == result["job_id"]))
        safe_args = {k: v for k, v in args.items() if k != "phone"}  # never log phone numbers
        logger.info(f"TOOL {name} {json.dumps(safe_args)} -> {json.dumps(result)[:300]}")
        self.calls.append({"name": name, "args": safe_args, "result": result})
        return result

    def openai_tools(self) -> list[dict]:
        return [
            {"type": "function", "function": {"name": s["name"], "description": s["description"],
                                              "parameters": {"type": "object", "properties": s["properties"],
                                                             "required": s["required"]}}}
            for s in TOOL_SPECS
        ]
