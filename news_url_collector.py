import asyncio
import logging
import random
from browser_service import BrowserService
from file_watcher import FileWatcher
from rss_monitor import RSSMonitor
from news_detector import NewsDetector

class NewsURLCollector:
    def __init__(self, config: dict, browser_service: BrowserService, queue: asyncio.Queue, processed_urls: set):
        """从配置字典初始化"""
        processor_config = config.get("news_url_collector", {})
        self.input_dir = processor_config.get("input_dir", "input_data")
        self.output_dir = processor_config.get("output_dir", "processed_data")
        self.rss_urls = processor_config.get("rss_urls", [])
        self.detect_url = processor_config.get("detect_url", "https://www.xxx.com/stocks")
        self.browser_service = browser_service
        self.queue = queue
        self.processed_urls = processed_urls
        self.logger = logging.getLogger('NewsURLCollector')
        self.file_watcher = FileWatcher(self.input_dir, self.queue, self.processed_urls)
        self.rss_monitor = RSSMonitor(self.rss_urls, self.queue)
        self.news_detector = NewsDetector(self.detect_url, self.browser_service, self.queue)

    async def collect(self, min_interval: int = 600, max_interval: int = 900, max_runs: int = None) -> None:
        """监控文件和新闻网站，将新 URL 放入队列"""
        self.file_watcher.start()
        runs = 0
        try:
            while max_runs is None or runs < max_runs:
                await self.rss_monitor.check_new_news()
                await self.news_detector.check_new_news()
                sleep_time = random.uniform(min_interval, max_interval)
                self.logger.info(f"Waiting {sleep_time/60:.1f} minutes until next check")
                await asyncio.sleep(sleep_time)
                runs += 1
        finally:
            self.file_watcher.stop()