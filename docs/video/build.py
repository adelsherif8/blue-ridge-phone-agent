"""Record the pipeline X-ray video: Playwright drives stage.html on a timeline, ffmpeg lays the audio on top.

Usage: python docs/video/build.py [--upwork]  (any Python with playwright + chromium installed)
Outputs: docs/video/out/phone-agent.mp4, .gif, and stills in docs/video/frames/.
"""
import asyncio
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
OUT, FR = HERE / "out", HERE / "frames"
L = json.loads((HERE / "lines.json").read_text())
SFX = HERE.resolve().parents[2] / "voicedesk/docs/vid2"  # ring + ding sfx from the VoiceDesk repo next to this one
# measured voice-to-voice seconds for the turns used (call records 19682806 and 04974b6c)
LAT1 = [1.39, 1.24, 1.54]  # windows offer, address read-back, booking
LAT2 = 2.37
# --upwork: same video without the domain on the end card (Upwork treats it as contact info)
UP = "--upwork" in sys.argv
# --nocap: no captions/callouts, source for the vertical LinkedIn cut (no gif, no stills)
NOCAP = "--nocap" in sys.argv
VAR = "upwork" if UP else "nocap" if NOCAP else ""
SUF = f"-{VAR}" if VAR else ""


async def main():
    RAW = OUT / "raw"; shutil.rmtree(RAW, ignore_errors=True); RAW.mkdir(parents=True); FR.mkdir(exist_ok=True)
    audio = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(RAW),
                                  record_video_size={"width": 1920, "height": 1080})
        pg = await ctx.new_page()
        t_rec = time.time()
        await pg.goto(f"file://{HERE}/stage.html" + (f"?{VAR}=1" if VAR else ""))
        fr = pg.frame_locator("#frame")  # pre-select the burst-pipe call in the console used at the reveal
        await fr.locator("[data-f=transfer]").dispatch_event("click")
        await fr.locator(".call", has_text="Burst pipe").first.dispatch_event("click")
        await pg.wait_for_timeout(1500)
        t0 = time.time()
        lead = t0 - t_rec
        now = lambda: time.time() - t0  # noqa: E731

        async def at(t):
            d = t - now()
            if d > 0:
                await pg.wait_for_timeout(int(d * 1000))

        async def api(c): await pg.evaluate(f"api.{c}")
        async def shot(n):
            if not VAR: await pg.screenshot(path=str(FR / f"{n}.png"))
        def snd(f, t): audio.append((str(HERE / f), t))  # lines.json paths are relative to docs/video
        def j(x): return json.dumps(x)

        # hook
        await at(0.3); await api("hook(1)"); snd(L["narr"]["hook"]["file"], 0.4)
        await at(3.2); await api("hook(2)"); await at(4.6); await shot("0-hook")
        await at(5.9); await api("stage()"); await api("call('Incoming call','***0199 · Ana')"); snd(SFX / "ring.mp3", 6.0)
        await api("cap('Real-time pipeline: Twilio, Deepgram, OpenAI, Pipecat','fa-diagram-project')")
        t = 7.6
        c1 = L["call1"]
        for i, ln in enumerate(c1):
            if ln["speaker"] == "sam":
                k = i // 2
                await at(t); await api("think()")
                if k == 0:
                    await at(t + 0.35); await api("tool('book_job()','refused: check_slots first','bad')")
                    await api("cap('Guardrail in code: no booking before checking the schedule','fa-shield-halved')")
                    await at(t + 0.7); await api("tool('check_slots(tomorrow)','open windows returned')"); await api("open()")
                if k == 2:
                    await at(t + 0.5); await api("tool('book_job(tomorrow, 2-4)','Booked · BRP-1001')")
                await api(f"watch({LAT1[k]})")
                t += 0.8
            await at(t); snd(ln["file"], t); await api(f"say({j(ln['speaker'])},{j(ln['text'])})")
            if i == 0: await api("cap('')")
            if i == 1:
                await at(t + 1.2); await api("cap('')"); await shot("1-live-call")
            if i == 3: await api("cap('Reads the address back before booking','fa-location-dot')")
            if i == 5:
                await api("book()"); snd(SFX / "ding.mp3", t + 0.2)
                await api("cap('Booked on the schedule and synced to HubSpot','fa-calendar-check')")
                await api("callout('Contact + linked meeting in HubSpot, no human touched it',1030,830)")
                await at(t + 2.6); await shot("2-booked")
            t += ln["dur"] + 0.25
        await at(t); await api("callout('')"); await api("cap('')")
        # call 2: emergency
        t += 0.2
        await at(t); await api("ctx('Call 2 · 2:14 AM emergency')"); await api("clearTools()"); await api("emergency()")
        await api("call('Incoming call','***0199 · Marcus')"); snd(SFX / "ring.mp3", t)
        t += 1.0
        c2 = L["call2"]
        await at(t); snd(c2[0]["file"], t); await api(f"say('marcus',{j(c2[0]['text'])})")
        t += c2[0]["dur"] + 0.2
        await at(t); await api("think()"); await api(f"watch({LAT2})")
        await at(t + 0.4); await api("tool('transfer_to_human(emergency)','Transferring')")
        t += 0.7
        await at(t); snd(c2[1]["file"], t); await api(f"say('sam',{j(c2[1]['text'])})")
        await api("cap('Safety advice first, then a live hand-off','fa-triangle-exclamation')")
        t += c2[1]["dur"] + 0.2
        await at(t); snd(c2[2]["file"], t); await api(f"say('twilio',{j(c2[2]['text'])})"); await api("ringTech()")
        await api("cap('Twilio redirects the call: Say, then Dial the on-call number','fa-right-left')")
        await at(t + 1.6); await api("whisper()"); await at(t + 2.4); await shot("3-handoff")
        t += c2[2]["dur"] + 0.1
        await at(t); await api("bridge()"); await api("sys('bot left the call · caller and technician connected')")
        await api("cap('The bot leaves. The call stays up.','fa-link')")
        snd(L["narr"]["xfer"]["file"], t + 0.2)
        await at(t + 2.2); await shot("4-bridged")
        # console reveal
        t += 2.2
        await at(t); await api("cap('')"); await api("console()")
        await at(t + 0.9); await api("czoom(1.25)")
        await api("callout('Every call logged, redacted and timed, turn by turn',260,880)")
        await at(t + 2.4); await shot("5-console")
        # CTA
        t += 3.1
        await at(t); await api("callout('')"); await api("end()"); snd(L["narr"]["cta"]["file"], t + 0.3)
        await at(t + 1.5); await shot("6-end")
        end_png, end_t = RAW / "end.png", now()  # crisp still laid over the recorder's smeared end card
        await pg.screenshot(path=str(end_png))
        await at(t + 3.9)
        total = now()
        await ctx.close(); await b.close()
    if not VAR:
        rel = [(os.path.relpath(f, HERE), t) for f, t in audio]
        (HERE / "timeline.json").write_text(json.dumps({"audio": rel, "total": total}, indent=1))
    raw = glob.glob(str(RAW / "*.webm"))[0]
    mux(raw, audio, total, lead, end_png, end_t)
    shutil.rmtree(RAW, ignore_errors=True)


def mux(raw, audio, total, lead, end_png, end_t):
    ins, flt = ["-ss", str(lead), "-i", raw], []
    n = len(audio) + 1  # input index of the end still
    for k, (f, t) in enumerate(audio):
        ins += ["-i", f]
        ms = int(t * 1000)
        flt.append(f"[{k + 1}:a]adelay={ms}|{ms},volume={0.35 if 'ring' in f or 'ding' in f else 1.0}[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(audio))) + f"amix=inputs={len(audio)}:normalize=0[a]"
    ins += ["-loop", "1", "-i", str(end_png)]
    vid = f"[0:v][{n}:v]overlay=0:0:enable='gte(t,{end_t:.2f})'[v]"
    mp4 = OUT / f"phone-agent{SUF}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(flt + [mix, vid]),
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k", str(mp4)], check=True)
    if NOCAP:
        print("wrote", mp4, f"{total:.1f}s"); return
    gif = OUT / f"phone-agent{SUF}.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                    "fps=8,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse",
                    str(gif)], check=True)
    print("wrote", mp4, f"{total:.1f}s", gif)


if __name__ == "__main__":
    asyncio.run(main())
