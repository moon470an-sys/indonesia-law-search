"""Test which per-page query string variant ESDM JDIH actually honors."""
from __future__ import annotations

import asyncio
import json

from playwright.async_api import async_playwright

CANDIDATES = [
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&per-page=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&PageSize=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&DokumenSearch%5Bper-page%5D=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?per-page=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&perPage=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&pageSize=50",
    "https://jdih.esdm.go.id/dokumen/peraturan?page=1&limit=50",
]


async def main() -> None:
    out = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="id-ID")
        page = await ctx.new_page()
        page.set_default_timeout(30_000)
        for url in CANDIDATES:
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                cards = await page.query_selector_all(".card-body.no-padding-tb")
                summary = await page.evaluate(
                    "() => { const e = document.querySelector('.summary'); return e ? e.textContent.trim() : null; }"
                )
                out.append({"url": url, "cards": len(cards), "summary": summary})
            except Exception as e:
                out.append({"url": url, "error": str(e)})
        await browser.close()
    import os
    os.makedirs("data", exist_ok=True)
    with open("data/probe_esdm_perpage.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("wrote data/probe_esdm_perpage.json")


if __name__ == "__main__":
    asyncio.run(main())
