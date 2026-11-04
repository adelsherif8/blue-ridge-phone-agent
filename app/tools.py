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
            "address": {"type": "string", "description": "Service street address as confirmed with the caller"},
            "problem": {"type": "string", "description": "Short description of the plumbing problem"},
            "day": {"type": "string", "enum": ["today", "tomorrow"]},
            "window": {"type": "string", "enum": ["8-10", "10-12", "12-2", "2-4", "4-6"]},
            "urgency": {"type": "string", "enum": ["routine", "emergency"]},
            "phone": {"type": "string", "description": "Callback number. Required when the caller ID is hidden; otherwise only if the caller gives a different one"},
        },
        "required": ["name", "address", "problem", "day", "window", "urgency"],
    },
]

FILLERS = {"check_slots": "One sec, checking the board.", "book_job": "One sec, booking that in."}


class Tools:
    """Runs tool calls for one phone call against a board."""

    def __init__(self, board: Board, caller_id: str | None = None):
        self.board = board
        self.caller_id = caller_id
        self.checked_days: set[str] = set()
        self.calls: list[dict] = []  # every call and result, for the call log and evals

    def run(self, name: str, args: dict) -> dict:
        if name == "check_slots":
            result = self.board.check_slots(args.get("day", ""))
            if "day" in result:
                self.checked_days.add(result["day"])
        elif name == "book_job" and (args.get("day") or "").lower() not in self.checked_days:
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
        else:
            result = {"error": f"unknown tool {name}"}
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
