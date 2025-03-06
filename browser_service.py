import logging
from playwright.async_api import Page, BrowserContext
from playwright_stealth import stealth_async
from fingerprint_manager import FingerprintManager
from throttle_manager import ThrottleManager


class BrowserService:
    def __init__(self, config: dict):
        self.logger = logging.getLogger('BrowserService')
        browser_config = config.get("browser_service", {})
        fingerprint_config = browser_config.get("fingerprint", {})
        self.fingerprint_manager = FingerprintManager(
            browser_type=fingerprint_config.get("browser_type", "chromium"),
            user_agent=fingerprint_config.get("user_agent", None),
            randomize=fingerprint_config.get("randomize", False),
            screen_width=fingerprint_config.get("screen_width", 1280),
            screen_height=fingerprint_config.get("screen_height", 720),
            locale=fingerprint_config.get("locale", "en-US"),
            timezone_id=fingerprint_config.get("timezone_id", "UTC"),
            device_scale_factor=fingerprint_config.get("device_scale_factor", 1.0),
            geolocation=fingerprint_config.get("geolocation", {"latitude": 0, "longitude": 0})
        )

        self.throttle_manager = ThrottleManager(browser_config)
        self.current_fingerprint = None

    def generate_fingerprint(self) -> dict:
        """生成并缓存浏览器指纹"""
        self.current_fingerprint = self.fingerprint_manager.generate_fingerprint()
        return self.current_fingerprint

    def update_throttle_rate(self, rate: float) -> None:
        """更新节流速率"""
        self.throttle_manager.update_rate(rate)

    async def limit_rate(self) -> None:
        """限制请求速率"""
        await self.throttle_manager.limit_rate()

    def complete_request(self) -> None:
        """完成请求并更新状态"""
        self.throttle_manager.complete_request()

    async def stealth_async(self, page: Page) -> None:
        """对页面应用伪装"""
        await stealth_async(page)

    async def adjust_fingerprint(self,
                                 context: BrowserContext,
                                 page: Page,
                                 trigger_reason: str = "plugin_suggestion") -> tuple[BrowserContext, Page]:
        """调整指纹并返回新的上下文和页面"""
        self.logger.info(f"Adjusting fingerprint due to: {trigger_reason}")
        if page:
            await page.close()
        if context:
            await context.close()

        self.current_fingerprint = self.fingerprint_manager.adjust_fingerprint(self.current_fingerprint)
        self.logger.info(f"New fingerprint generated: {self.current_fingerprint['userAgent']}")

        # 创建并返回新的上下文和页面
        new_context = await context.browser.new_context(**self.current_fingerprint)
        new_page = await new_context.new_page()
        await self.stealth_async(new_page)
        return new_context, new_page

    def should_adjust_fingerprint(self, response: dict) -> bool:
        """判断是否需要调整指纹"""
        if not response or "content" not in response:
            return True
        content = response.get("content", "")
        status = response.get("status", 200)
        if status >= 400 or "captcha" in content.lower() or len(content) < 100:
            return True

        return False

    async def process_page(self,
                           context: BrowserContext,
                           page: Page,
                           response: dict = None) -> tuple[BrowserContext, Page]:
        """处理页面并在需要时调整指纹"""
        if response and self.should_adjust_fingerprint(response):
            return await self.adjust_fingerprint(context, page, trigger_reason="response_analysis")

        return context, page