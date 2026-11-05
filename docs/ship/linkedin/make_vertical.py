"""15 s vertical (1080x1920) LinkedIn cut of the live hand-off, from the caption-free render.

Run after: python docs/video/build.py --nocap
"""
import asyncio, subprocess
from pathlib import Path
from playwright.async_api import async_playwright

H = Path(__file__).parent
SRC = H.parents[1] / "video/out/phone-agent-nocap.mp4"
LOGO = (Path.home() / "Desktop/GHAI/aa-social/logo/mark-light.svg").read_text().replace("<svg ", '<svg class="aa" ', 1)
VEND = 52.55  # console() fades in at ~52.8 s
SEGS = [(34.55, 39.40), (40.15, 46.15), (50.45, 54.00)]  # caller line, Sam's safety line, bridge + narration
HEAD = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=Instrument+Serif:ital@1&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<style>*{{margin:0;box-sizing:border-box}}html,body{{width:1080px;height:438px;overflow:hidden;background:#F7F4EE;color:#16130F;font-family:Archivo,sans-serif;position:relative}}
.l{{position:absolute;left:64px;top:64px;font-size:24px;font-weight:700;letter-spacing:.16em;color:#C63C22;display:flex;gap:16px;align-items:center}}
.l::before{{content:"";width:40px;height:3px;background:#C63C22}}
.aa{{position:absolute;right:64px;top:56px;height:44px;width:auto}}
h1{{position:absolute;left:60px;top:118px;font-size:96px;font-weight:900;letter-spacing:-.05em;line-height:.95}}
h1 em{{font-family:"Instrument Serif",serif;font-style:italic;font-weight:400;color:#C63C22;letter-spacing:-.01em;font-size:108px}}
.s{{position:absolute;left:64px;bottom:34px;font:500 22px "IBM Plex Mono",monospace;color:#6B655B}}</style></head><body>
<div class="l">LIVE HAND-OFF</div>{LOGO}<h1>Burst pipe at 2 AM.<br><em>Live</em> hand-off.</h1>
<div class="s">simulated call · transfer tested in dry-run</div></body></html>"""

async def header():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1080, "height": 438})
        f = H / "_head.html"; f.write_text(HEAD); await pg.goto(f"file://{f}"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=str(H / "_head.png")); f.unlink(); await b.close()

def main():
    asyncio.run(header())
    v, a = [], []
    for i, (s, e) in enumerate(SEGS):
        d = e - s
        ve = min(e, VEND)  # picture holds on the last frame before the console reveal
        hold = f",tpad=stop_mode=clone:stop_duration={e - ve:.2f}" if e > ve else ""
        v.append(f"[0:v]trim={s}:{ve},setpts=PTS-STARTPTS{hold}[v{i}]")
        a.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:d=0.06,afade=t=out:st={d-0.12:.2f}:d=0.12[a{i}]")
    n = len(SEGS)
    cat = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]"
    lay = ("[cv]split[x][y];[x]crop=860:590:70:420,scale=1080:741[top];[y]crop=860:590:990:420,scale=1080:741[bot];"
           "[1:v][top][bot]vstack=inputs=3,format=yuv420p[out]")
    out = H / "vertical-handoff-15s.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(SRC), "-loop", "1", "-i", str(H / "_head.png"),
                    "-filter_complex", ";".join(v + a + [cat, lay]), "-map", "[out]", "-map", "[ca]", "-shortest",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-r", "30", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(out)], check=True)
    (H / "_head.png").unlink()
    print("wrote", out)

main()
