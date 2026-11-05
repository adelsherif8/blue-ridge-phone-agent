"""Compose framed, annotated Upwork screenshots (2000x1500) from the clean sources in src/."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
LOGO = Path.home() / "Desktop/GHAI/aa-social/logo/mark-light.svg"
W = 900  # css width of the framed image

SHOTS = [
 dict(out="2-live-call", src="a-live.png", sw=1920, label="01 · Live call", title="A live call, <em>stage by stage</em>",
      bar="blue-ridge-phone-agent · live pipeline",
      marks=[(1088, 92, "Caller audio streams through speech-to-text, the LLM and the voice in real time"),
             (718, 327, "Tries to book too early? Code refuses until the schedule is checked"),
             (1398, 466, "Offers only the windows that are really open")]),
 dict(out="3-booked", src="b-booked.png", sw=1920, label="02 · Booking + CRM", title="Booked and <em>synced</em>. No data entry.",
      bar="blue-ridge-phone-agent · live pipeline",
      marks=[(62, 740, "Reads the address back before booking"),
             (1398, 466, "Books an open window on the live schedule"),
             (972, 766, "Creates the HubSpot contact and a linked meeting")]),
 dict(out="4-handoff", src="c-handoff.png", sw=1920, label="03 · Live hand-off", title="Emergency? A <em>live</em> hand-off.",
      bar="blue-ridge-phone-agent · live pipeline",
      marks=[(62, 775, "Safety advice first: shut off the main water valve"),
             (972, 456, "The on-call technician hears a spoken summary first"),
             (1420, 700, "The bot leaves. Caller and technician stay connected")]),
 dict(out="5-console", src="d-console.png", sw=1920, label="04 · Call console", title="Every call <em>on the record</em>",
      bar="blue-ridge-phone-agent / docs / console.html",
      marks=[(150, 142, "Median 1.74 s, p95 4.61 s across 20 simulated calls"),
             (568, 372, "Names, numbers and addresses redacted before saving"),
             (1556, 290, "Every turn timed: speech-to-text, LLM, voice")]),
]

CSS = """
:root{--paper:#F7F4EE;--paper2:#EFE9DC;--ink:#16130F;--grey:#6B655B;--red:#C63C22;--lift:#F2643F}
*{box-sizing:border-box;margin:0}
html,body{width:1000px;height:750px;overflow:hidden}
body{background:radial-gradient(ellipse at 70% 60%,#F2E7D8 0%,var(--paper) 55%),var(--paper);color:var(--ink);font-family:Archivo,sans-serif;position:relative}
.lbl{position:absolute;left:50px;top:38px;font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--red);display:flex;align-items:center;gap:10px}
.lbl::before{content:"";width:24px;height:2px;background:var(--red)}
h1{position:absolute;left:50px;top:58px;font-size:38px;font-weight:800;letter-spacing:-.035em;line-height:1}
h1 em{font-family:"Instrument Serif",serif;font-style:italic;font-weight:400;color:var(--red);letter-spacing:-.01em}
.aa{position:absolute;right:50px;top:40px;height:24px;width:auto}
.fr{position:absolute;left:50px;top:122px;width:900px;border-radius:12px;overflow:visible;box-shadow:0 30px 60px -24px rgba(22,19,15,.55),0 2px 8px -2px rgba(22,19,15,.2)}
.bar{height:24px;background:#221D17;border-radius:12px 12px 0 0;display:flex;align-items:center;gap:6px;padding:0 12px}
.bar i{width:9px;height:9px;border-radius:50%;background:#4A4034}
.bar span{margin-left:10px;font:10px "IBM Plex Mono",monospace;color:#7A7265}
.img{position:relative;line-height:0}
.img img{width:900px;display:block;border-radius:0 0 12px 12px}
.mk{position:absolute;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;background:linear-gradient(135deg,var(--lift),var(--red));color:#fff;font:800 15px Archivo,sans-serif;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 8px 18px -6px rgba(198,60,34,.8)}
.leg{position:absolute;left:50px;right:50px;top:672px;display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.leg div{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;line-height:1.3;font-weight:500;color:#3A342C}
.leg b{flex:none;width:22px;height:22px;border-radius:50%;background:var(--red);color:#fff;font-size:12px;display:grid;place-items:center}
.fn{position:absolute;right:50px;bottom:12px;font:9.5px "IBM Plex Mono",monospace;color:var(--grey)}
"""

def page(s):
    k = W / s["sw"]
    logo = LOGO.read_text().replace("<svg ", '<svg class="aa" ', 1)
    mk = "".join(f'<div class="mk" style="left:{x*k:.0f}px;top:{y*k:.0f}px">{i+1}</div>' for i, (x, y, _) in enumerate(s["marks"]))
    leg = "".join(f"<div><b>{i+1}</b><span>{t}</span></div>" for i, (_, _, t) in enumerate(s["marks"]))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=Instrument+Serif:ital@1&family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="lbl">{s['label']}</div><h1>{s['title']}</h1>{logo}
<div class="fr"><div class="bar"><i></i><i></i><i></i><span>{s['bar']}</span></div>
<div class="img"><img src="src/{s['src']}">{mk}</div></div>
<div class="leg">{leg}</div>
<div class="fn">Simulated calls over Twilio Media Streams · timings measured · names redacted</div>
</body></html>"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1000, "height": 750}, device_scale_factor=2)
        for s in SHOTS:
            f = HERE / f"_{s['out']}.html"; f.write_text(page(s))
            await pg.goto(f"file://{f}"); await pg.wait_for_timeout(1200)
            await pg.screenshot(path=str(HERE / f"{s['out']}.png")); f.unlink()
        await b.close()

asyncio.run(main())
