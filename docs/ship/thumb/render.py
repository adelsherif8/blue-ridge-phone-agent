import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
H = Path(__file__).parent
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1000, "height": 750}, device_scale_factor=2)
        await pg.goto(f"file://{H}/thumb.html"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=str(H / "cover.png")); await b.close()
asyncio.run(main())
