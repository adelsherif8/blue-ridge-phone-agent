"""Voice eval: run scenarios as simulated phone calls against the local server, then grade
the server's call records with the same rules and judge as the text eval, and summarize latency.

Needs the server running locally with TRANSFER_NUMBER set and TRANSFER_DRY_RUN=1:
  PORT=8790 TRANSFER_NUMBER=+1... TRANSFER_DRY_RUN=1 uv run python -m app.server
Usage: uv run python -m evals.run_voice [--calls 20] [--only id1,id2]
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evals.run_text import GLOBAL_JUDGE, judge, rule_checks  # noqa: E402
from evals.scenarios import SCENARIOS  # noqa: E402
from sim_call import run as sim_run  # noqa: E402


def find_record(call_sid: str, timeout: float = 20) -> dict | None:
    end = time.time() + timeout
    while time.time() < end:
        hits = sorted((ROOT / "data/calls").glob(f"*/*-{call_sid}.json"))
        if hits:
            return json.loads(hits[-1].read_text())
        time.sleep(0.5)
    return None


def outcome(tool_calls: list) -> dict:
    ok = lambda c, s: c["result"].get("status") == s  # noqa: E731
    books = [c for c in tool_calls if c["name"] == "book_job" and ok(c, "Booked")]
    changes = [c for c in tool_calls if c["name"] == "change_booking" and ok(c, "Changed")]
    last = (changes or books or [None])[-1]
    names = [c["name"] for c in tool_calls]
    first_ok = next((i for i, c in enumerate(tool_calls) if c in books + changes), None)
    return {
        "booked": bool(books), "n_books": len(books),
        "day": last["args"].get("day") if last else None,
        "urgency": next((b["args"].get("urgency") for b in books), None),
        "callback": any(c["name"] == "request_callback" and ok(c, "Saved") for c in tool_calls),
        "transfer": next((c["args"] for c in tool_calls if c["name"] == "transfer_to_human" and ok(c, "Transferring")), None),
        "checked_first": first_ok is None or "check_slots" in names[:first_ok],
        "address": books[-1]["args"].get("address", "") if books else "",
    }


def checks_for(exp: dict, o: dict) -> dict:
    c = {}
    if exp.get("book_or_transfer"):
        c["booked_or_handed_off"] = o["booked"] or bool(o["transfer"]) or o["callback"]
    else:
        c["booked"] = o["booked"] == exp["booked"]
    want = exp.get("transfer")
    if exp.get("handoff"):
        c["handed_off"] = bool(o["transfer"]) or o["callback"]
    elif want == "optional":
        pass
    elif want:
        allowed = [want] if isinstance(want, str) else want
        c["transferred"] = bool(o["transfer"]) and o["transfer"].get("reason") in allowed
    else:
        c["no_transfer"] = o["transfer"] is None
    if "callback" in exp:
        c["callback"] = o["callback"] == exp["callback"]
    if exp.get("urgency") and o["booked"]:
        c["urgency"] = o["urgency"] == exp["urgency"]
    if exp.get("day") and o["booked"]:
        c["day"] = o["day"] == exp["day"]
    if o["booked"]:
        c["checked_before_booking"] = o["checked_first"]
        c["single_booking"] = o["n_books"] == 1
    return c


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


async def run_one(sc: dict, port: int) -> dict:
    call_sid = "CAsim" + uuid.uuid4().hex[:24]
    client_turns: list = []
    t0 = time.time()
    try:
        lines = await sim_run(sc, port, call_sid=call_sid, client_turns=client_turns)
        error = None
    except Exception as e:
        lines, error = [], repr(e)
    rec = await asyncio.to_thread(find_record, call_sid)
    if not rec:
        return {"id": sc["id"], "passed": False, "error": error or "no call record", "checks": {}}
    o = outcome(rec["tool_calls"])
    checks = checks_for(sc["expect"], o)
    # transcript as the caller heard it (STT of bot audio) plus the server's tool calls, for the judge
    heard = "\n".join(f"{who}: {text}" for who, text in lines)
    tools_txt = "\n".join(f"TOOL: {c['name']}({json.dumps(c['args'])}) -> {c['result'].get('status', 'ok')}"
                          for c in rec["tool_calls"])
    answers = await judge(sc["expect"].get("judge", []) + GLOBAL_JUDGE,
                          f"{heard}\n\n(Tool calls in order, server log:)\n{tools_txt}", rec["tool_calls"])
    for a in answers:
        checks[f"judge: {a['q'][:70]}"] = bool(a["yes"])
    replies = [t["text"] for t in rec["transcript"] if t["role"] == "assistant"]
    return {"id": sc["id"], "call_sid": call_sid, "passed": all(checks.values()) and not error, "error": error,
            "checks": checks, "rules": rule_checks(replies), "turns": rec["turns"], "client_turns": client_turns,
            "first_speech_secs": rec.get("first_speech_secs"), "tts_chars": rec.get("tts_chars"),
            "heard": heard, "ended_by": rec.get("ended_by"), "secs": round(time.time() - t0, 1)}


def summarize(results: list) -> dict:
    # Only turns anchored at the caller's end of speech. Pipecat anchors the bot's second reply after a
    # tool call (filler -> tool -> answer) at client_connected, which is elapsed call time, not latency.
    turns = [t for r in results for t in r.get("turns", []) if t.get("measured_from") == "user_silence"]
    v2v = [t["voice_to_voice_secs"] for t in turns]
    no_tool = [t["voice_to_voice_secs"] for t in turns if not t.get("tools")]
    with_tool = [t["voice_to_voice_secs"] for t in turns if t.get("tools")]
    client = [t["secs"] for r in results for t in r.get("client_turns", [])]
    by = lambda svc: [t["ttfb"][svc] for t in turns if svc in t.get("ttfb", {})]  # noqa: E731
    row = lambda xs: {"n": len(xs), "median": round(statistics.median(xs), 3) if xs else None,  # noqa: E731
                      "p95": round(pct(xs, 95), 3) if xs else None}
    return {"server_voice_to_voice": row(v2v), "server_no_tool_turns": row(no_tool),
            "server_tool_turns": row(with_tool), "client_perceived": row(client),
            "stt_ttfb": row(by("stt")), "llm_ttfb": row(by("llm")), "tts_ttfb": row(by("tts")),
            "first_greeting": row([r["first_speech_secs"] for r in results if r.get("first_speech_secs")])}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=20)
    ap.add_argument("--only", default="")
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args()
    scs = [s for s in SCENARIOS if not args.only or s["id"] in args.only.split(",")]
    plan = [scs[i % len(scs)] for i in range(args.calls)]
    results = []
    for i, sc in enumerate(plan, 1):  # sequential: concurrent calls would distort latency
        r = await run_one(sc, args.port)
        results.append(r)
        bad = [k for k, v in r["checks"].items() if not v]
        print(f"[{i}/{len(plan)}] {sc['id']}: {'PASS' if r['passed'] else 'FAIL'} {r.get('error') or ''} {'; '.join(bad)}",
              flush=True)
    summary = summarize(results)
    out = ROOT / "evals/results" / f"voice-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=1))
    print(f"\n{sum(r['passed'] for r in results)}/{len(results)} calls passed")
    for k, v in summary.items():
        print(f"{k:24} n={v['n']:<3} median={v['median']}  p95={v['p95']}")
    print(f"saved {out}")


if __name__ == "__main__":
    asyncio.run(main())
