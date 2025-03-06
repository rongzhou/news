from datetime import datetime, timedelta
from asyncio import Queue
import logging
import feedparser

class RSSMonitor:
    def __init__(self, rss_urls: list, queue: Queue):
        """初始化，指定 RSS URLs 和 Scheduler"""
        self.logger = logging.getLogger('RSSMonitor')
        self.rss_urls = rss_urls
        self.queue = queue
        self.last_checked = None

    async def check_new_news(self) -> None:
        """检查 RSS feed 中的新文章，并推送 URL 到队列"""
        self.logger.info(f"Checking RSS feeds at {datetime.now()}")
        current_time = datetime.now()
        time_threshold = current_time - timedelta(minutes=10)

        for rss_url in self.rss_urls:
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                self.logger.error(f"Failed to parse RSS: {rss_url}")
                continue

            new_entries = [
                entry for entry in feed.entries
                if "published" in entry and datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z") > time_threshold
            ]

            for entry in new_entries:
                url = entry.link
                self.logger.info(f"New RSS article detected: {entry.title} - {url}")
                await self.queue.put(url)

        self.last_checked = current_time