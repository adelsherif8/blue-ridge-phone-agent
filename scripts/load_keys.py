"""Copy keys from ~/Desktop/phone-agent-keys.txt (KEY=value lines) into .env.

Keeps existing .env values for keys not in the file. OPENAI_API_KEY falls back
to ~/Desktop/GHAI/card-id-pricing/.env. Prints key names only, never values.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = Path.home() / "Desktop" / "phone-agent-keys.txt"
OPENAI_ENV = Path.home() / "Desktop" / "GHAI" / "card-id-pricing" / ".env"
NEEDED = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "DEEPGRAM_API_KEY", "OPENAI_API_KEY"]


def parse(path: Path) -> dict[str, str]:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


env_path = ROOT / ".env"
env = parse(ROOT / ".env.example")
env = {k: v.split("#")[0].strip() for k, v in env.items()}
env.update(parse(env_path))
env.update({k: v for k, v in parse(KEYS).items() if v})
if not env.get("OPENAI_API_KEY"):
    env["OPENAI_API_KEY"] = parse(OPENAI_ENV).get("OPENAI_API_KEY", "")

env_path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
env_path.chmod(0o600)
missing = [k for k in NEEDED if not env.get(k)]
print("wrote .env;", "missing: " + ", ".join(missing) if missing else "all required keys present")
