"""Render clean (caption-free) stage states and a console view as sources for the Upwork screenshots."""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).parent / "src"
L = json.loads((ROOT / "docs/video/lines.json").read_text())
j = json.dumps

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.goto(f"file://{ROOT}/docs/video/stage.html?upwork=1"); await pg.wait_for_timeout(1500)
        e = lambda c: pg.evaluate("api." + c)
        await pg.evaluate("document.getElementById('note').style.display='none'")
        c1, c2 = L["call1"], L["call2"]
        await e("stage()"); await e("call('Incoming call','***0199 · Ana')")
        await e(f"say('ana',{j(c1[0]['text'])})"); await e("think()")
        await e("tool('book_job()','refused: check_slots first','bad')"); await e("tool('check_slots(tomorrow)','open windows returned')"); await e("open()")
        await e("watch(1.39)"); await pg.wait_for_timeout(500); await e(f"say('sam',{j(c1[1]['text'])})"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=str(SRC / "a-live.png"))
        for ln in c1[2:]:
            await e(f"say({j(ln['speaker'])},{j(ln['text'])})")
        await e("tool('book_job(tomorrow, 2-4)','Booked · BRP-1001')"); await e("book()"); await e("watch(1.54)"); await pg.wait_for_timeout(1300)
        await pg.screenshot(path=str(SRC / "b-booked.png"))
        await e("ctx('Call 2 · 2:14 AM emergency')"); await e("clearTools()"); await e("emergency()"); await e("call('Incoming call','***0199 · Marcus')")
        await e(f"say('marcus',{j(c2[0]['text'])})"); await e("tool('transfer_to_human(emergency)','Transferring')"); await e("watch(2.37)")
        await e(f"say('sam',{j(c2[1]['text'])})"); await e(f"say('twilio',{j(c2[2]['text'])})"); await e("ringTech()"); await e("whisper()")
        await pg.wait_for_timeout(700); await e("bridge()"); await e("sys('bot left the call · caller and technician connected')"); await pg.wait_for_timeout(1300)
        await pg.screenshot(path=str(SRC / "c-handoff.png"))
        await pg.goto(f"file://{ROOT}/docs/console.html"); await pg.wait_for_timeout(1500)
        await pg.locator("[data-f=transfer]").click(); await pg.locator(".call", has_text="Burst pipe").first.click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=str(SRC / "d-console.png"))
        await b.close()

asyncio.run(main())
