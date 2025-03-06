from datetime import datetime
from asyncio import Queue
import logging
from playwright.async_api import async_playwright
from browser_service import BrowserService

class NewsDetector:
    def __init__(self, base_url: str, browser_service: BrowserService, queue: Queue):
        """初始化，指定检测 URL 和 Scheduler"""
        self.base_url = base_url
        self.browser_service = browser_service
        self.queue = queue
        self.logger = logging.getLogger('NewsDetector')
        self.last_titles = set()

    async def check_new_news(self) -> None:
        """检查页面中的新新闻，并推送 URL 到队列"""
        self.logger.info(f"Checking {self.base_url} at {datetime.now()}")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                fingerprint = self.browser_service.generate_fingerprint()
                context = await browser.new_context(**fingerprint)
                page = await context.new_page()
                await self.browser_service.stealth_async(page)
                await self.browser_service.limit_rate()
                await page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)

                titles = set(await page.locator("h2, a").all_text_contents())
                new_titles = titles - self.last_titles

                if new_titles:
                    self.logger.info(f"Detected {len(new_titles)} new articles: {new_titles}")
                    for title in new_titles:
                        locator = page.locator(f"a:text('{title}')").first
                        link = await locator.get_attribute("href") if locator else None
                        if link:
                            if link.startswith('http'):
                                full_url = link
                            else:
                                full_url = f"{self.base_url.rstrip('/')}/{link.lstrip('/')}"
                            self.logger.info(f"Pushing URL to queue: {full_url}")
                            await self.queue.put(full_url)
                    else:
                        self.logger.warning("No valid URLs found for new titles")
                else:
                    self.logger.info("No new articles detected")

                self.last_titles = titles
                await self.browser_service.throttle_manager.complete_request()
                await context.close()

            except Exception as e:
                self.logger.error(f"Error detecting news at {self.base_url}: {str(e)}")
                self.browser_service.complete_request()
            finally:
                await browser.close()