import time
import asyncio
import logging

class ThrottleManager:
    def __init__(self, config: dict):
        self.logger = logging.getLogger('ThrottleManager')
        throttle_config = config.get("throttle", {})
        self.min_rate = throttle_config.get("min_rate", 1.0)
        self.current_rate = self.min_rate
        self.max_concurrent = max(throttle_config.get("max_concurrent", 5), 1)  # 确保至少为 1
        self.request_count = 0
        self.last_request_time = time.time()  # 初始化为当前时间
        self.active_requests = 0

    def update_rate(self, new_rate: float) -> None:
        """更新节流速率，确保不低于最小值"""
        self.current_rate = max(new_rate, self.min_rate)
        self.logger.info(f"Throttle rate updated to {self.current_rate:.2f} seconds")

    async def limit_rate(self) -> None:
        """限制请求速率和并发数"""
        while self.active_requests >= self.max_concurrent:
            self.logger.debug(f"Max concurrent requests ({self.max_concurrent}) reached, waiting...")
            await asyncio.sleep(0.5)

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.current_rate:
            wait_time = self.current_rate - time_since_last
            self.logger.debug(f"Throttling: waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)

        self.active_requests += 1
        self.request_count += 1
        self.last_request_time = time.time()

        self.logger.info(
            f"Request allowed: rate={self.current_rate:.2f}, "
            f"active_requests={self.active_requests}, "
            f"request_count={self.request_count}"
        )

    def complete_request(self) -> None:
        """完成请求并更新状态"""
        if self.active_requests > 0:
            self.active_requests -= 1
            self.logger.info(f"Request completed, active requests now {self.active_requests}")
        else:
            self.logger.warning("Attempted to complete a request when active_requests is 0")