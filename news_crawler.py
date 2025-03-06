from datetime import datetime
import time
import asyncio
import logging
from playwright.async_api import async_playwright, Page, BrowserContext
from browser_service import BrowserService
from behavior_simulator import BehaviorSimulator
from request_manager import RequestManager
from adaptive_manager import AdaptiveManager
from article_parser import ArticleParser
from content_analyzer import ContentAnalyzer
from session_manager import SessionManager
from environment_cleaner import EnvironmentCleaner
from plugin_manager import PluginManager, AntiBotPlugin
from data_saver import DataSaver

class NewsCrawler:
    def __init__(self, config: dict, browser_service: BrowserService, queue: asyncio.Queue, processed_urls: set):
        self.logger = logging.getLogger('NewsCrawler')
        news_crawler_config = config.get("news_crawler", {})
        self.ollama_endpoint = news_crawler_config.get("ollama_endpoint", "http://localhost:11434/api/generate")
        self.prompt_file = news_crawler_config.get("prompt_file", "prompts.yaml")
        self.browser_service = browser_service
        self.queue = queue
        self.processed_urls = processed_urls
        self.behavior_simulator = BehaviorSimulator()
        self.request_manager = RequestManager()
        self.adaptive_manager = AdaptiveManager(config)
        self.article_parser = ArticleParser()
        self.content_analyzer = ContentAnalyzer(self.ollama_endpoint, self.prompt_file)
        self.session_manager = SessionManager()
        self.env_cleaner = EnvironmentCleaner()
        self.plugin_manager = PluginManager()
        self.data_saver = DataSaver(**config.get("data_saver", {}))

    async def process_urls(self, batch_size: int = 10) -> None:
        """异步运行抓取任务的主循环"""
        await self.plugin_manager.register_plugin(AntiBotPlugin())
        async with async_playwright() as playwright:
            while True:
                browser = await playwright.chromium.launch(headless=True)
                if urls := await self.fetch_urls_from_queue(batch_size):
                    self.logger.info(f"Processing batch of {len(urls)} URLs: {urls}")
                    tasks = [self.process_single_url(url, browser) for url in urls]
                    await asyncio.gather(*tasks)
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(1)

                await browser.close()

    async def fetch_urls_from_queue(self, batch_size: int) -> list[str]:
        """从队列中获取 URL 批次"""
        urls = []
        while len(urls) < batch_size and self.queue.qsize() > 0:
            try:
                url = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                if url not in self.processed_urls:
                    urls.append(url)
                    self.processed_urls.add(url)

                self.queue.task_done()
            except asyncio.TimeoutError:
                break
        return urls

    async def process_single_url(self, url: str, browser) -> None:
        """处理单个 URL 的完整流程"""
        self.logger.info(f"Starting task for URL: {url}")
        session_id = await self.session_manager.create_session()
        context = {"url": url, "session_id": session_id, "attempts": 0, "max_attempts": 3}
        browser_context = None
        page = None
        try:
            fingerprint = self.browser_service.generate_fingerprint()
            browser_context = await browser.new_context(**fingerprint)
            if "geolocation" in fingerprint:
                await browser_context.grant_permissions(["geolocation"])

            page = await browser_context.new_page()
            await self.browser_service.stealth_async(page)

            response_content = await self.fetch_content(url, page, context)
            if not response_content:
                raise Exception("Failed to fetch content after retries")

            await self.behavior_simulator.simulate(page, context)
            parsed_data = await self.article_parser.extract_article(page, response_content)
            if not parsed_data:
                raise Exception("Failed to extract article content")

            language = "zh" if any(c in parsed_data["content"] for c in "的一是不") else "en"
            analysis = await self.content_analyzer.analyze_content(
                parsed_data["content"], language=language, max_keywords=5, summary_length=50
            )

            await self.handle_plugin_suggestions(context, page, browser_context)

            record = {
                "url": url,
                "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "title": parsed_data.get("title", ""),
                "publish_date": parsed_data.get("publish_date", ""),
                "content": parsed_data.get("content", ""),
                "source": parsed_data.get("source", ""),
                "keywords": analysis["keywords"] if analysis else [],
                "summary": analysis["summary"] if analysis else "",
                "market_type": analysis["labels"]["market_type"] if analysis else "Other",
                "sentiment": analysis["labels"]["sentiment"] if analysis else "Neutral",
                "market_impact": analysis["labels"]["market_impact"] if analysis else "Neutral",
                "language": language,
                "status": "success" if analysis else "failed"
            }
            self.data_saver.add_record(record)
            self.logger.info(f"Successfully fetched: {url}")

        except Exception as e:
            self.logger.error(f"Error for {url}: {str(e)}")
            await self.handle_plugin_suggestions(context, page, browser_context)
            record = {
                "url": url,
                "fetch_date": datetime.now().strftime("%Y-%m-d %H:%M:%S"),
                "title": parsed_data.get("title", "") if 'parsed_data' in locals() else "",
                "publish_date": parsed_data.get("publish_date", "") if 'parsed_data' in locals() else "",
                "content": parsed_data.get("content", "") if 'parsed_data' in locals() else "",
                "source": parsed_data.get("source", "") if 'parsed_data' in locals() else "",
                "keywords": [],
                "summary": "",
                "market_type": "Other",
                "sentiment": "Neutral",
                "market_impact": "Neutral",
                "language": "unknown",
                "status": "failed"
            }
            self.data_saver.add_record(record)
            self.data_saver.save_remaining()

        finally:
            if context:
                await self.env_cleaner.clean_session(context)

            await self.session_manager.close_session(session_id)
            if page:
                await page.close()

            if browser_context:
                await browser_context.close()

    async def fetch_content(self, url: str, page: Page, context: dict) -> str | None:
        """执行抓取并处理重试"""
        await self.browser_service.limit_rate()
        start_time = time.time()
        response_content = await self.request_manager.send_request(url, page, context)
        response_time = time.time() - start_time
        context["response"] = {
            "content": response_content,
            "status": 200 if response_content else 0,
            "load_time": response_time
        }
        feedback = self.adaptive_manager.monitor_response(context["response"])
        self.adaptive_manager.adjust_strategy(feedback, context)
        delay = self.adaptive_manager.get_current_delay()
        self.browser_service.update_throttle_rate(delay)

        await self.plugin_manager.execute_plugins(context)
        self.browser_service.complete_request()
        if response_content and not context.get("stop_attempts", False):
            return response_content

    async def handle_plugin_suggestions(self, context: dict, page: Page, browser_context: BrowserContext) -> None:
        """处理插件建议并触发对策"""
        await self.plugin_manager.execute_plugins(context)
        if context.get("adjust_fingerprint"):
            self.logger.info("Adjusting fingerprint due to plugin suggestion")
            fingerprint = self.browser_service.generate_fingerprint()
            await page.close()
            await browser_context.close()
            browser_context = await browser_context.browser.new_context(**fingerprint)
            page = await browser_context.new_page()
            await self.browser_service.stealth_async(page)
            context["browser_context"] = browser_context
            context["page"] = page

        if suggested_delay := context.get("suggested_delay"):
            current_delay = self.adaptive_manager.get_current_delay()
            new_delay = max(current_delay, suggested_delay)
            self.logger.info(f"Applying coordinated delay: {new_delay} seconds")
            self.browser_service.update_throttle_rate(new_delay)