import asyncio
import random
import logging
from playwright.async_api import Page

class RequestManager:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 10.0,
                 backoff_factor: float = 2.0):
        self.logger = logging.getLogger('RequestManager')
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_stats = {"success": 0, "failure": 0}
        self._attempts = 0

    async def send_request(self, url: str, page: Page, context: dict) -> str | None:
        """发送请求并处理重试逻辑"""
        self._attempts = 0

        while self._attempts < self.max_attempts:
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                content = await page.content() if response and response.ok else ""
                status = response.status if response else 0

                context["response"] = {"content": content, "status": status}

                if await self._should_retry(context):
                    self._attempts += 1
                    if self._attempts >= self.max_attempts:
                        self.logger.error(f"Max retries ({self.max_attempts}) exceeded for {url}")
                        self.retry_stats["failure"] += 1
                        return None
                    await self._apply_retry_delay(url)
                    continue

                self.logger.info(f"Request succeeded for {url}, status: {status}, HTML length: {len(content)}")
                self.retry_stats["success"] += 1
                return content

            except Exception as e:
                self.logger.error(f"Request error for {url}: {str(e)}")
                self._attempts += 1
                if self._attempts >= self.max_attempts:
                    self.logger.error(f"Max retries ({self.max_attempts}) exceeded for {url}")
                    self.retry_stats["failure"] += 1
                    return None
                await self._apply_retry_delay(url)

        return None

    async def _should_retry(self, context: dict) -> bool:
        """判断是否需要重试"""
        if not context.get("response"):
            self.logger.warning("No response received, retry needed")
            return True

        response = context["response"]
        status = response.get("status", 200)
        content = response.get("content", "")

        retry_conditions = [
            status in [429, 503, 504],
            status >= 400,
            len(content) < 50,
            "captcha" in content.lower()
        ]

        should_retry = any(retry_conditions)
        self.logger.debug(
            f"Retry check: status={status}, attempts={self._attempts}/{self.max_attempts}, should_retry={should_retry}")
        return should_retry

    async def _apply_retry_delay(self, url: str) -> None:
        """应用退避延迟"""
        delay = min(self.base_delay * (self.backoff_factor ** (self._attempts - 1)), self.max_delay)
        jitter = random.uniform(0, 0.5)
        total_delay = delay + jitter
        self.logger.info(
            f"Retrying {url}, attempt {self._attempts}/{self.max_attempts}, delay={total_delay:.2f} seconds")
        await asyncio.sleep(total_delay)

    def reset_attempts(self) -> None:
        """重置重试计数"""
        self._attempts = 0

    def get_retry_stats(self) -> dict:
        """获取重试统计信息"""
        return self.retry_stats.copy()