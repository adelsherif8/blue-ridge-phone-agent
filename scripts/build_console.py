"""Build docs/console.html: a static call console from the redacted call records in data/calls.

Usage: uv run python scripts/build_console.py
Everything shown comes from saved records (transcripts are already redacted) and the latest voice eval summary.
"""
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUES = {
    "check_slots": re.compile(r"checking the board|\b(am|pm|noon)\b|open|available|full", re.I),
    "book_job": re.compile(r"booking that in|booked|confirmed", re.I),
    "change_booking": re.compile(r"moving that|moved|changed", re.I),
    "request_callback": re.compile(r"noting that|I will ask|I'll ask|will call you back|have noted|saved", re.I),
    "transfer_to_human": re.compile(r"connecting you|transferring|stay on the line|right away", re.I),
}


def outcome(rec: dict) -> dict:
    if rec.get("transfer"):
        return {"kind": "transfer", "label": f"Transferred: {rec['transfer']['reason'].replace('_', ' ')}"}
    for t in rec.get("tool_calls", []):
        if t["name"] in ("book_job", "change_booking") and t["result"].get("status") in ("Booked", "Changed"):
            w = t["result"]
            return {"kind": "booked", "label": f"Booked {w.get('day', '')} {w.get('window', '')}".strip()}
    for t in rec.get("tool_calls", []):
        if t["name"] == "request_callback" and str(t["result"].get("status", "")).startswith("Saved"):
            return {"kind": "callback", "label": "Callback saved"}
    return {"kind": "info", "label": "Answered"}


def timeline(rec: dict) -> list:
    """Merge consecutive caller fragments, attach per-turn latency to bot replies, and place tool calls
    after the bot line that announced them (their filler), or at the end."""
    lines = []
    for m in rec["transcript"]:
        role = "bot" if m["role"] == "assistant" else "caller"
        if lines and lines[-1]["role"] == role:
            lines[-1]["text"] += " " + m["text"]
        else:
            lines.append({"role": role, "text": m["text"]})
    turns = list(rec.get("turns", []))
    for i, ln in enumerate(lines):
        if ln["role"] == "bot" and turns and (i == 0 or lines[i - 1]["role"] == "caller"):
            t = turns.pop(0)
            if t.get("measured_from") == "user_silence" or i == 0:
                ln["turn"] = t
    # Tools run before the reply that uses their result. Place each one (in call order) before the first
    # later bot line that shows its result; a refused call goes with the next placed tool.
    before: dict[int, list] = {}
    pos, carry = 1, []
    for tool in rec.get("tool_calls", []):
        refused = str(tool["result"].get("status", "")).startswith(("Not", "Already", "Unavailable"))
        cue = CUES.get(tool["name"])
        hit = None
        if not refused and cue:
            ks = [k for k in range(pos, len(lines)) if lines[k]["role"] == "bot" and cue.search(lines[k]["text"])]
            hit = (ks[-1] if tool["name"] == "transfer_to_human" else ks[0]) if ks else None
        if hit is None:
            carry.append(tool)
            continue
        before.setdefault(hit, []).extend(carry + [tool])
        carry, pos = [], hit
    out = []
    for k, ln in enumerate(lines):
        out += [{"role": "tool", **t} for t in before.get(k, [])]
        out.append(ln)
    out += [{"role": "tool", **t} for t in carry]
    return out


def main():
    calls = []
    for f in sorted(glob.glob(str(ROOT / "data/calls/*/*.json")), reverse=True):
        rec = json.loads(Path(f).read_text())
        if not rec.get("transcript"):
            continue
        calls.append({"sid": rec["call_sid"][-6:], "scenario": rec.get("scenario") or "live",
                      "caller": rec.get("caller"), "started": rec.get("started_at", "")[:16].replace("T", " "),
                      "secs": rec.get("duration_secs"), "first": rec.get("first_speech_secs"),
                      "outcome": outcome(rec), "lines": timeline(rec), "transfer": rec.get("transfer"),
                      "model": rec.get("model"), "voice": rec.get("tts_voice"), "chars": rec.get("tts_chars")})
    voice = sorted(glob.glob(str(ROOT / "evals/results/voice-*.json")))
    summary, passed, total = {}, 0, 0
    for v in voice:
        d = json.loads(Path(v).read_text())
        if len(d["results"]) >= 20:
            summary = d["summary"]
            passed, total = sum(r["passed"] for r in d["results"]), len(d["results"])
    data = {"calls": calls, "summary": summary, "passed": passed, "total": total}
    tpl = (ROOT / "scripts/console_template.html").read_text()
    html = tpl.replace("/*DATA*/null", json.dumps(data).replace("</", "<\\/"))
    out = ROOT / "docs/console.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} with {len(calls)} calls")


if __name__ == "__main__":
    main()
