"""Two LinkedIn document carousels (1080x1350 pages, PDF) in the adelatya brand. Measured facts only."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

H = Path(__file__).parent
LG = Path.home() / "Desktop/GHAI/aa-social/logo"
MARK = {"ink": (LG / "mark-dark.svg").read_text(), "paper": (LG / "mark-light.svg").read_text()}
CONSOLE = "adelatya.com/voice-agent-engineer/phone-agent"

CSS = """
*{margin:0;box-sizing:border-box}
@page{size:1080px 1350px;margin:0}
body{font-family:Archivo,sans-serif}
.s{width:1080px;height:1350px;position:relative;overflow:hidden;page-break-after:always;padding:150px 90px 190px;display:flex;flex-direction:column;justify-content:center}
.paper{background:#F7F4EE;color:#16130F}.ink{background:#16130F;color:#F7F4EE}
.ink::before{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(242,100,63,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(242,100,63,.045) 1px,transparent 1px);background-size:40px 40px}
.s>*{position:relative}
.aa{position:absolute!important;right:90px;top:84px;height:44px;width:auto}
.lbl{font-size:24px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#C63C22;display:flex;gap:16px;align-items:center}
.ink .lbl{color:#F2643F}
.lbl::before{content:"";width:40px;height:3px;background:currentColor}
h1{font-size:118px;font-weight:900;letter-spacing:-.05em;line-height:.95;margin-top:60px}
h2{font-size:76px;font-weight:800;letter-spacing:-.04em;line-height:1;margin-top:46px}
em{font-family:"Instrument Serif",serif;font-style:italic;font-weight:400;color:#C63C22;letter-spacing:-.01em}
.ink em{color:#F2643F}
p{font-size:40px;line-height:1.38;margin-top:40px;color:#3A342C}.ink p{color:#D9D1C2}
.mono{font-family:"IBM Plex Mono",monospace}
.foot{position:absolute!important;left:90px;right:90px;bottom:70px;display:flex;justify-content:space-between;font-size:20px;font-weight:700;letter-spacing:.16em;color:#8A8274;border-top:1px solid rgba(138,130,116,.35);padding-top:22px}
.stat{display:flex;align-items:baseline;gap:28px;border-left:5px solid #C63C22;padding:6px 0 6px 30px;margin-top:44px}
.stat b{font:600 108px "IBM Plex Mono",monospace;letter-spacing:-.03em}.stat b small{font-size:48px}
.stat span{font-size:32px;color:#6B655B;line-height:1.25}
.bar{margin-top:46px}.bar .t{display:flex;justify-content:space-between;font-size:34px;font-weight:700}
.bar .t span{font:600 40px "IBM Plex Mono",monospace}
.bar .w{height:30px;background:#E4DCCB;border-radius:6px;margin-top:14px;overflow:hidden}.bar .w i{display:block;height:100%;border-radius:6px}
.bar .n{font-size:26px;color:#6B655B;margin-top:10px}
.note{font-size:31px;color:#6B655B;margin-top:56px;line-height:1.4;border-top:1px dashed #C9BFAE;padding-top:26px}
.ink .note{color:#ABA294;border-color:#3A3229}
ul{list-style:none;padding:0;margin-top:46px}li{font-size:39px;line-height:1.35;padding:20px 0 20px 56px;position:relative;border-bottom:1px solid rgba(138,130,116,.3)}
li::before{content:"";position:absolute;left:0;top:38px;width:26px;height:4px;background:#C63C22}
.num{font:600 30px "IBM Plex Mono",monospace;color:#C63C22;margin-top:60px}
.code{font:500 30px "IBM Plex Mono",monospace;background:#1E1A15;color:#F7F4EE;border-radius:16px;padding:30px 34px;margin-top:44px;line-height:1.5}
.paper .code{box-shadow:0 30px 60px -28px rgba(22,19,15,.6)}
.code .r{color:#F0776A}.code .g{color:#7FD39A}.code .c{color:#8A8274}
.cta{font:500 30px "IBM Plex Mono",monospace;color:#F2643F;margin-top:50px}
.swipe{position:absolute!important;right:90px;bottom:150px;font-size:26px;font-weight:700;letter-spacing:.12em;color:#F2643F}
"""

def slide(theme, body, n, total, swipe=False):
    mark = MARK[theme].replace("<svg ", '<svg class="aa" ', 1).replace('id="m"', f'id="m{n}"').replace("url(#m)", f"url(#m{n})")
    sw = '<div class="swipe">SWIPE <i class="fa-solid fa-arrow-right"></i></div>' if swipe else ""
    return (f'<section class="s {theme}">{mark}{body}{sw}<div class="foot"><span>AA · AI VOICE AGENTS</span>'
            f'<span>{n:02d} / {total:02d}</span></div></section>')

def bar(name, val, maxv, note, color):
    return (f'<div class="bar"><div class="t">{name}<span>{val:.2f} s</span></div>'
            f'<div class="w"><i style="width:{val/maxv*100:.0f}%;background:{color}"></i></div><div class="n">{note}</div></div>')

LAT = [
 ("ink", '<div class="lbl">Voice agent latency</div><h1>Where <em>1.74 s</em> goes.</h1>'
         '<p>The median reply time of my AI phone agent over 20 simulated calls. Every stage, measured.</p>'),
 ("paper", '<div class="lbl">What I timed</div><h2>Caller stops talking. <em>Bot starts speaking.</em></h2>'
           '<div class="stat"><b>1.74<small> s</small></b><span>median<br>55 turns, 20 calls</span></div>'
           '<div class="stat"><b>4.61<small> s</small></b><span>p95<br>the slow tail</span></div>'
           '<p class="note">Measured on the server. The simulated caller measured almost the same: 1.80 s median, 4.63 s p95.</p>'),
 ("paper", '<div class="lbl">The three stages</div><h2>Medians, <em>stage by stage</em></h2>'
           + bar("Speech-to-text", .47, 1.0, "Deepgram, time to final transcript", "#8FB3C9")
           + bar("LLM first token", .87, 1.0, "gpt-4.1-mini", "#F2643F")
           + bar("Voice first audio", .24, 1.0, "Deepgram Aura-2", "#E9B04A")
           + '<p class="note">Medians of the parts don\'t add up to the median whole. The rest is the wait for the caller to finish, turn detection and sentence buffering.</p>'),
 ("ink", '<div class="lbl">Biggest piece</div><h2>The LLM\'s first token: <em>0.87 s</em></h2>'
         '<p>The largest single stage is the model starting to answer. It is the first place I look when a reply feels slow: prompt size, model choice, and whether a tool call sits in the turn.</p>'),
 ("paper", '<div class="lbl">The slow tail</div><h2>1 turn in 20 takes <em>4.6 s</em> or more.</h2>'
           '<p>A median hides the turns callers remember. The call console shows a waterfall for every turn, so a slow one points at the stage that stalled.</p>'
           '<div class="code"><span class="c">turn latency · burst pipe call</span><br>endpointing wait   0.20<br>transcription      0.24<br>'
           '<span class="r">LLM inference      1.23</span><br>sentence buffer    0.32<br>speech synthesis   0.37</div>'),
 ("paper", '<div class="lbl">Honest limits</div><h2>What these numbers <em>leave out</em></h2>'
           '<ul><li>Calls were simulated over Twilio\'s Media Streams protocol, not dialed from a phone.</li>'
           '<li>So the phone network is not in the number. Real calls will be somewhat slower.</li>'
           '<li>The callers were an LLM following personas, not real people.</li></ul>'),
 ("ink", '<div class="lbl">Why measure this way</div><h2>Your own voice stack, <em>not a rented one.</em></h2>'
         '<p>Own the pipeline and every stage is yours to time and tune.</p>'
         f'<div class="cta">See every turn: {CONSOLE}</div><p style="font-size:30px">Adel Atya · AI voice agent engineer</p>'),
]

GUARD = [
 ("ink", '<div class="lbl">Voice agent guardrails</div><h1>The prompt says don\'t. <em>The code</em> makes sure.</h1>'
         '<p>Five rules my AI phone agent can\'t talk its way out of.</p>'),
 ("paper", '<div class="num">RULE 1</div><h2>No booking before <em>checking the schedule.</em></h2>'
           '<div class="code">book_job(tomorrow, 2-4)<br><span class="r">refused: check_slots first</span><br>check_slots(tomorrow)<br><span class="g">open windows returned</span></div>'
           '<p class="note">In some test calls the model tried to book too early. The code refused every time, and the bot checked the schedule as it should.</p>'),
 ("paper", '<div class="num">RULE 2</div><h2>One booking per call. <em>Never someone else\'s job.</em></h2>'
           '<p>A second booking on the same call is refused. A change moves the caller\'s own booking instead of creating a new one, and a job that belongs to another caller can\'t be edited.</p>'),
 ("paper", '<div class="num">RULE 3</div><h2>No transfer <em>without a reason.</em></h2>'
           '<p>Every hand-off carries a reason and a summary. Emergencies come with safety advice first:</p>'
           '<ul><li>Gas smell: leave the house, call the gas company or 911, then transfer.</li>'
           '<li>Burst pipe or flooding: shut-off valve first, then transfer.</li></ul>'),
 ("paper", '<div class="num">RULE 4</div><h2>Prices and facts <em>only from the business.</em></h2>'
           '<p>The call-out fee comes from the business\'s own fact card. A question it can\'t answer becomes a saved callback request, not a guess.</p>'),
 ("paper", '<div class="num">RULE 5</div><h2>Caller tricks <em>don\'t change the rules.</em></h2>'
           '<ul><li>A caller claiming an owner\'s discount and a free call-out.</li><li>A caller trying to override the instructions.</li></ul>'
           '<p class="note">Both are among the 19 scenarios graded on every test run.</p>'),
 ("ink", '<div class="lbl">How it\'s checked</div><h2>Rules in code. <em>Checked by tests.</em></h2>'
         '<div class="stat" style="border-color:#F2643F"><b style="color:#F7F4EE">57/57</b><span style="color:#ABA294">best of the last 3 text runs<br>(56, 56, 57 of 57)</span></div>'
         '<div class="stat" style="border-color:#F2643F"><b style="color:#F7F4EE">98</b><span style="color:#ABA294">unit tests, run in CI on every push</span></div>'
         f'<div class="cta">Call console: {CONSOLE}</div><p style="font-size:30px">Adel Atya · AI voice agent engineer</p>'),
]

def doc(slides):
    t = len(slides)
    body = "".join(slide(th, b, i + 1, t, swipe=(i == 0)) for i, (th, b) in enumerate(slides))
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;700;800;900&family=Instrument+Serif:ital@1&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">'
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">'
            f'<style>{CSS}</style></head><body>{body}</body></html>')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1080, "height": 1350})
        for name, slides in (("carousel-latency", LAT), ("carousel-guardrails", GUARD)):
            f = H / f"{name}.html"; f.write_text(doc(slides))
            await pg.goto(f"file://{f}"); await pg.wait_for_timeout(1500)
            await pg.pdf(path=str(H / f"{name}.pdf"), width="1080px", height="1350px", print_background=True)
            for i in range(len(slides)):  # preview PNGs for review
                await pg.evaluate(f"window.scrollTo(0,{i*1350})")
                await pg.screenshot(path=str(H / f"_{name}-{i+1}.png"), clip={"x": 0, "y": i * 1350, "width": 1080, "height": 1350}, full_page=True)
            f.unlink()
        await b.close()

asyncio.run(main())
