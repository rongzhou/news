import asyncio
import logging
import os
import pandas as pd
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class FileWatcher(FileSystemEventHandler):
    def __init__(self, input_dir: str, queue: asyncio.Queue, processed_urls: set):
        self.input_dir = input_dir
        self.queue = queue
        self.processed_urls = processed_urls
        self.logger = logging.getLogger('FileWatcher')
        self.observer = Observer()
        self.observer.schedule(self, self.input_dir, recursive=False)

    def start(self) -> None:
        """启动文件监控并加载初始文件"""
        self.logger.info(f"Starting FileWatcher for directory: {self.input_dir}")
        self.observer.start()
        asyncio.run_coroutine_threadsafe(self.load_initial_urls(), asyncio.get_event_loop())

    def stop(self) -> None:
        """停止文件监控"""
        self.logger.info("Stopping FileWatcher")
        self.observer.stop()
        self.observer.join()

    def on_modified(self, event):
        """处理文件修改事件"""
        if not event.is_directory and event.src_path.endswith((".parquet", ".csv")):
            self.logger.info(f"File modified: {event.src_path}")
            asyncio.run_coroutine_threadsafe(self.load_new_urls(event.src_path), asyncio.get_event_loop())

    async def load_new_urls(self, filepath: str) -> None:
        """从指定文件中加载新 URL"""
        try:
            df = pd.read_parquet(filepath) if filepath.endswith(".parquet") else pd.read_csv(filepath)
            new_urls = 0
            for url in df["url"].dropna().unique():
                if url not in self.processed_urls:
                    await self.queue.put(url)
                    self.processed_urls.add(url)  # 添加到已处理集合
                    new_urls += 1
            self.logger.info(f"Loaded {new_urls} new URLs from {filepath}")
        except Exception as e:
            self.logger.error(f"Error loading URLs from {filepath}: {str(e)}")

    async def load_initial_urls(self) -> None:
        """加载输入目录中的初始文件"""
        self.logger.info(f"Loading initial URLs from directory: {self.input_dir}")
        for filename in os.listdir(self.input_dir):
            if filename.endswith((".parquet", ".csv")):
                filepath = os.path.join(self.input_dir, filename)
                await self.load_new_urls(filepath)