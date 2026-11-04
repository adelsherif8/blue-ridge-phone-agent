"""One JSON record per call: transcript, tool calls, per-turn latency, transfer, CRM result.

Written at hang-up to CALL_LOG_DIR (default data/calls/), PII-redacted with CallRedactor.
Latency comes from Pipecat's UserBotLatencyObserver: for each turn, the time from the
caller's actual end of speech (VAD-adjusted) to the bot's first audio, plus per-service
time-to-first-byte (STT, LLM, TTS) and tool-call durations.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.redact import CallRedactor
from app.util import mask_phone


def _service(processor: str) -> str:
    p = processor.lower()
    return "stt" if "stt" in p else "llm" if "llm" in p else "tts" if "tts" in p else processor


class CallLog:
    def __init__(self, call_sid: str, caller_id: str | None, scenario: str | None = None):
        self.call_sid = call_sid
        self.caller_id = caller_id
        self.scenario = scenario
        self.started = time.time()
        self.turns: list[dict] = []
        self.first_speech_secs: float | None = None

    def add_breakdown(self, b) -> None:
        """Record one user->bot cycle from a pipecat LatencyBreakdown."""
        ttfb: dict[str, float] = {}
        for t in b.ttfb:
            ttfb.setdefault(_service(t.processor), round(t.duration_secs, 3))
        self.turns.append({
            "voice_to_voice_secs": round(b.total_secs, 3),
            "measured_from": str(b.measured_from) if b.measured_from else None,
            "user_turn_secs": round(b.user_turn_secs, 3) if b.user_turn_secs is not None else None,
            "ttfb": ttfb,
            "tools": [{"name": f.function_name, "secs": round(f.duration_secs, 3)} for f in b.function_calls],
            "contributions": [c.model_dump(mode="json") for c in b.contributions],
        })

    def write(self, *, messages: list, tool_calls: list, transfer: dict | None, crm: list, ended_by: str) -> Path:
        names = [c["args"].get("name", "") for c in tool_calls if isinstance(c.get("args"), dict)]
        red = CallRedactor(names=names)
        transcript = [{"role": m["role"], "text": m["content"]} for m in messages
                      if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"]]
        record = {
            "call_sid": self.call_sid,
            "scenario": self.scenario,
            "caller": mask_phone(self.caller_id),
            "started_at": datetime.fromtimestamp(self.started, timezone.utc).isoformat(),
            "duration_secs": round(time.time() - self.started, 1),
            "ended_by": ended_by,
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "tts_voice": os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-thalia-en"),
            "first_speech_secs": self.first_speech_secs,
            "turns": self.turns,
            "transcript": red.redact_obj(transcript),
            "tool_calls": red.redact_obj(tool_calls),
            "transfer": red.redact_obj(transfer),
            "crm": [{k: v for k, v in r.items() if k in ("job_id", "ok", "contact_created", "error")} for r in crm],
            "tts_chars": sum(len(t["text"]) for t in transcript if t["role"] == "assistant"),
        }
        out = Path(os.getenv("CALL_LOG_DIR", "data/calls")) / datetime.now().strftime("%Y-%m-%d")
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{datetime.now():%H%M%S}-{self.call_sid}.json"
        path.write_text(json.dumps(record, indent=1))
        logger.info(f"Call record saved: {path}")
        return path
