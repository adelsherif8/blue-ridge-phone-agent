"""Voice the video lines with Deepgram Aura-2 (the same TTS the agent uses). Writes audio/*.mp3 + lines.json."""
import json, os, subprocess, urllib.request
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent.parent / ".env")
KEY = os.environ["DEEPGRAM_API_KEY"]
V = {"sam": "aura-2-thalia-en", "ana": "aura-2-andromeda-en", "marcus": "aura-2-orion-en",
     "twilio": "aura-2-helena-en", "narr": "aura-2-zeus-en"}
# Call lines are taken from saved test-call transcripts (redacted fields filled with the scenario's made-up persona).
LINES = {
    "narr": {
        "hook": "Most AI phone agents are a black box you rent by the minute. This one is a pipeline I own.",
        "xfer": "Safety advice first. Then a live hand-off to a person. The bot leaves, the call stays up.",
        "cta": "Want your own voice stack, not a rented one? Let's build it.",
    },
    "call1": [
        ["ana", "Hi Sam, my bathroom faucet is dripping constantly. Can someone come tomorrow afternoon?"],
        ["sam", "Tomorrow afternoon we have two to four PM and four to six PM. Which works best?"],
        ["ana", "Two to four, please. I'm at 41 Laurel Drive."],
        ["sam", "That's forty-one Laurel Drive, right?"],
        ["ana", "Yes."],
        ["sam", "Your visit is booked for tomorrow, two to four PM, with an eighty-nine dollar call-out fee."],
    ],
    "call2": [
        ["marcus", "This is Marcus. A pipe burst in my basement and water is spraying everywhere!"],
        ["sam", "If you can reach it safely, shut off the main water valve now. I'm connecting you to our on-call technician."],
        ["twilio", "Connecting you to our on-call team now. Please stay on the line."],
    ],
}


def speak(voice, text, out):
    if not out.exists():
        req = urllib.request.Request(f"https://api.deepgram.com/v1/speak?model={voice}&encoding=mp3",
                                     data=json.dumps({"text": text}).encode(), method="POST",
                                     headers={"Authorization": f"Token {KEY}", "Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        out.write_bytes(opener.open(req, timeout=60).read())
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout
    return round(float(d), 3)


def main():
    a = HERE / "audio"; a.mkdir(exist_ok=True)
    res = {"narr": {}, "call1": [], "call2": []}
    for k, t in LINES["narr"].items():
        f = a / f"n_{k}.mp3"; res["narr"][k] = {"file": str(f.relative_to(HERE)), "text": t, "dur": speak(V["narr"], t, f)}
    for call in ("call1", "call2"):
        for i, (who, t) in enumerate(LINES[call]):
            f = a / f"{call}_{i}.mp3"
            res[call].append({"speaker": who, "text": t, "file": str(f.relative_to(HERE)), "dur": speak(V[who], t, f)})
    (HERE / "lines.json").write_text(json.dumps(res, indent=1))
    tot = sum(v["dur"] for v in res["narr"].values()) + sum(x["dur"] for c in ("call1", "call2") for x in res[c])
    print("audio seconds:", round(tot, 1))


if __name__ == "__main__":
    main()
