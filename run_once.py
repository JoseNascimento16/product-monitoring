import asyncio
import logging

from playwright.async_api import async_playwright

from app import load_state, monitor_cycle


async def main():
    state = load_state()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            await monitor_cycle(browser, state)
        finally:
            await browser.close()


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(main())
