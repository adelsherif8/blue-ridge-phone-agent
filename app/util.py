"""Small helpers shared by the server and the bot."""

import re


def mask_phone(number: str | None) -> str:
    """Keep only the last 4 digits so logs never hold a full phone number."""
    if not number:
        return "unknown"
    digits = re.sub(r"\D", "", number)
    return f"***{digits[-4:]}" if len(digits) >= 4 else "***"
