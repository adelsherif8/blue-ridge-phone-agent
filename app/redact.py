"""PII redaction for saved call records.

VoiceDesk's regex Redactor (app/pii.py) handles digits, emails, cards, written addresses
and known names. A voice agent also *says* numbers, so this adds two spoken-form rules
in front of it: phone numbers read as words ("eight two eight, five five five ...") and
street addresses read as words ("forty-one Laurel Drive").
"""

import re

from app.pii import Redactor

_DIGIT_WORD = r"(?:zero|oh|o|one|two|three|four|five|six|seven|eight|nine)"
SPOKEN_PHONE = re.compile(rf"\b{_DIGIT_WORD}(?:[\s,.-]+{_DIGIT_WORD}){{6,}}\b", re.I)

_NUM_WORD = (r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
             r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)")
_SUFFIX = r"(?:Street|St|Road|Rd|Drive|Dr|Avenue|Ave|Lane|Ln|Way|Court|Ct|Circle|Cir|Boulevard|Blvd|Place|Pl|Terrace|Trail|Parkway|Highway)"
SPOKEN_ADDRESS = re.compile(rf"\b{_NUM_WORD}(?:[\s-]+{_NUM_WORD})*(?:\s+[A-Z][a-z]+){{1,3}}\s+{_SUFFIX}\b", re.I)


class CallRedactor:
    def __init__(self, names=()):
        self.inner = Redactor(names=[n for n in names if n and n.lower() not in ("caller", "sam")], engine="regex")
        self.spoken: dict[str, str] = {}

    def _spoken(self, kind: str, value: str) -> str:
        key = (kind, " ".join(value.lower().split()))
        if key not in self.spoken:
            n = sum(1 for k in self.spoken if k[0] == kind) + 1
            self.spoken[key] = f"<{kind}_SPOKEN_{n}>"
        return self.spoken[key]

    def redact(self, text):
        if not isinstance(text, str) or not text:
            return text
        text = SPOKEN_PHONE.sub(lambda m: self._spoken("PHONE", m.group(0)), text)
        text = SPOKEN_ADDRESS.sub(lambda m: self._spoken("ADDRESS", m.group(0)), text)
        return self.inner.redact(text)

    def redact_obj(self, obj):
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.redact_obj(v) for v in obj]
        return obj
