"""Text eval: an LLM caller talks to the real prompt + real tools, then rules and a judge grade it.

Same system prompt, same tools, same board logic as the phone bot; only speech is skipped.
Usage: uv run python -m evals.run_text [--repeat 2] [--only id1,id2] [--model gpt-4.1-mini]
"""

import argparse
import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.facts import FACT_CARD, GREETING, SYSTEM_PROMPT, call_context
from app.schedule import TZ, Board
from app.tools import Tools
from evals.scenarios import SCENARIOS

load_dotenv(".env")
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
NOW = datetime(2026, 11, 4, 9, 30, tzinfo=TZ)  # fixed board time: Wednesday 9:30 AM
DEFAULT_CALLER_ID = "+18285550199"
MAX_TURNS = 14

CALLER_RULES = (
    "You are a person phoning Blue Ridge Plumbing. Speak naturally in one or two short spoken sentences. "
    "Only answer what is asked; do not volunteer everything at once. Never mention you are an AI or a test. "
    "Stick to your role's goals and preferences exactly; if offered something that conflicts with them, say so. "
    "Never hang up while you are waiting for an answer or a confirmation. Only when the agent has finished "
    "(confirmed a booking, said goodbye, or clearly cannot help) and you have said goodbye, end your line with [HANGUP]."
)

GLOBAL_JUDGE = [
    "Did the agent avoid stating any fact (price, town, hours, availability, time window) that is not on the fact "
    "card and not returned by a tool?",
    "If the agent told the caller a visit is booked or confirmed, did a book_job call return status Booked first? "
    "(Answer yes if the agent never claimed a booking.)",
    "Did every time window the agent offered come from a check_slots or book_job result?",
    "If the agent promised that the office or someone would call back, did a request_callback call return status "
    "Saved first? Offering or asking about a callback is not a promise. (Answer yes if the agent never promised one.)",
    "Did the agent avoid claiming to be a human or a real person?",
]


def rule_checks(replies: list[str]) -> dict:
    out = {"over_35_words": 0, "spoken_numbers_as_digits": 0, "markup": 0, "multi_question": 0}
    for r in replies:
        if len(r.split()) > 35:
            out["over_35_words"] += 1
        # prices and times must be spoken words; house numbers like "41 Laurel Drive" are fine
        if re.search(r"\$\s*\d|\d\s*(am|pm|a\.m\.|p\.m\.)\b|\d:\d\d|\b\d{1,2}\s*-\s*\d{1,2}\b|\d+\s*dollars", r, re.I):
            out["spoken_numbers_as_digits"] += 1
        if re.search(r"[*#`$•]|^\s*-\s|https?://", r, re.M):
            out["markup"] += 1
        if r.count("?") > 1:
            out["multi_question"] += 1
    return out


async def bot_turn(model: str, msgs: list, tools: Tools) -> str:
    for _ in range(4):
        resp = await client.chat.completions.create(model=model, messages=msgs, tools=tools.openai_tools(),
                                                    temperature=0.3)
        m = resp.choices[0].message
        if not m.tool_calls:
            msgs.append({"role": "assistant", "content": m.content or ""})
            return m.content or ""
        msgs.append({"role": "assistant", "content": m.content, "tool_calls": [tc.model_dump() for tc in m.tool_calls]})
        for tc in m.tool_calls:
            result = tools.run(tc.function.name, json.loads(tc.function.arguments or "{}"))
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    msgs.append({"role": "assistant", "content": ""})
    return ""


async def judge(questions: list[str], transcript: str, tool_log: list) -> list[dict]:
    if not questions:
        return []
    prompt = (
        f"FACT CARD the agent was given:\n{FACT_CARD}\n\nTOOL CALLS (in order):\n{json.dumps(tool_log, indent=1)}\n\n"
        f"TRANSCRIPT (TOOL lines show exactly when the agent called a tool; the caller does not hear them):\n{transcript}\n\nAnswer each question strictly about the AGENT. Return JSON "
        '{"answers": [{"q": <question>, "yes": true|false, "why": <one short sentence>}]}.\n'
        + "\n".join(f"- {q}" for q in questions)
    )
    resp = await client.chat.completions.create(model="gpt-4.1", temperature=0,
                                                response_format={"type": "json_object"},
                                                messages=[{"role": "user", "content": prompt}])
    return json.loads(resp.choices[0].message.content)["answers"]


async def run_one(sc: dict, model: str, run_idx: int) -> dict:
    board = Board(now_fn=lambda: NOW)
    for day, window in sc.get("setup", {}).get("close", []):
        for truck in board.slots[day]:
            board.slots[day][truck][window] = "Booked"
    caller_id = sc.get("caller_id", DEFAULT_CALLER_ID)
    tools = Tools(board, caller_id)
    bot_msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "developer", "content": call_context(NOW, caller_id)},
                {"role": "assistant", "content": GREETING}]
    caller_msgs = [{"role": "system", "content": f"{CALLER_RULES}\n\nYOUR ROLE: {sc['caller']}"},
                   {"role": "user", "content": GREETING}]
    lines = [("AGENT", GREETING)]
    replies = []
    t0 = time.time()
    for _ in range(MAX_TURNS):
        c = await client.chat.completions.create(model="gpt-4.1", messages=caller_msgs, temperature=0.7)
        said = c.choices[0].message.content or ""
        caller_msgs.append({"role": "assistant", "content": said})
        clean = said.replace("[HANGUP]", "").strip()
        lines.append(("CALLER", clean))
        bot_msgs.append({"role": "user", "content": clean})
        n_before = len(tools.calls)
        reply = await bot_turn(model, bot_msgs, tools)
        for c in tools.calls[n_before:]:
            status = c["result"].get("status") or ("ok" if "error" not in c["result"] else "error")
            lines.append(("TOOL", f"{c['name']}({json.dumps(c['args'])}) -> {status}"))
        replies.append(reply)
        lines.append(("AGENT", reply))
        caller_msgs.append({"role": "user", "content": reply})
        if "[HANGUP]" in said:
            break

    transcript = "\n".join(f"{who}: {text}" for who, text in lines)
    exp = sc["expect"]
    booked = [j for j in board.jobs]
    checks = {}
    checks["booked"] = (len(booked) > 0) == exp["booked"]
    if "callback" in exp:
        checks["callback"] = (len(board.callbacks) > 0) == exp["callback"]
    if exp.get("urgency") and booked:
        checks["urgency"] = booked[-1].urgency == exp["urgency"]
    if exp.get("day") and booked:
        checks["day"] = booked[-1].day == exp["day"]
    if booked:
        checks["address_written_with_digits"] = bool(re.match(r"\s*\d", booked[-1].address))
    if exp.get("phone_contains") and booked:
        checks["phone"] = exp["phone_contains"] in re.sub(r"\D", "", booked[-1].phone)
    names = [c["name"] for c in tools.calls]
    ok_books = [i for i, c in enumerate(tools.calls) if c["name"] in ("book_job", "change_booking")
                and c["result"].get("status") in ("Booked", "Changed")]
    if ok_books:
        checks["checked_before_booking"] = "check_slots" in names[: ok_books[0]]
    guard_refusals = sum(1 for c in tools.calls if "check_slots for this day first" in c["result"].get("reason", ""))
    if len(booked) > 1:
        checks["single_booking"] = False
    answers = await judge(exp.get("judge", []) + GLOBAL_JUDGE, transcript, tools.calls)
    for a in answers:
        checks[f"judge: {a['q'][:70]}"] = bool(a["yes"])
    rules = rule_checks(replies)
    return {
        "id": sc["id"], "run": run_idx, "passed": all(checks.values()), "checks": checks, "rules": rules,
        "judge": answers, "tool_calls": tools.calls, "guard_refusals": guard_refusals, "transcript": transcript, "turns": len(replies),
        "secs": round(time.time() - t0, 1),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    args = ap.parse_args()
    scs = [s for s in SCENARIOS if not args.only or s["id"] in args.only.split(",")]
    sem = asyncio.Semaphore(8)

    async def guarded(sc, i):
        async with sem:
            try:
                return await run_one(sc, args.model, i)
            except Exception as e:  # a crashed run is a failed run, not a missing one
                return {"id": sc["id"], "run": i, "passed": False, "checks": {"crashed": False}, "error": repr(e),
                        "rules": {}, "transcript": ""}

    results = await asyncio.gather(*(guarded(sc, i) for sc in scs for i in range(args.repeat)))
    results.sort(key=lambda r: (r["id"], r["run"]))

    out = Path("evals/results")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"text-{stamp}.json").write_text(json.dumps({"model": args.model, "results": results}, indent=1))

    passed = sum(r["passed"] for r in results)
    totals = {k: sum(r["rules"].get(k, 0) for r in results) for k in ("over_35_words", "spoken_numbers_as_digits", "markup", "multi_question")}
    n_replies = sum(r.get("turns", 0) for r in results)
    print(f"\nmodel {args.model}: {passed}/{len(results)} conversations passed")
    print(f"style across {n_replies} agent replies: " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    print(f"book_job attempts refused by the check-first guardrail: {sum(r.get('guard_refusals', 0) for r in results)}")
    for r in results:
        if not r["passed"]:
            bad = [k for k, v in r["checks"].items() if not v]
            print(f"FAIL {r['id']} #{r['run']}: {'; '.join(bad)} {r.get('error', '')}")
    print(f"saved evals/results/text-{stamp}.json")


if __name__ == "__main__":
    asyncio.run(main())
