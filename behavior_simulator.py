import asyncio
import logging
import random
from typing import Dict
from playwright.async_api import Page

class BehaviorSimulator:
    def __init__(self):
        self.logger = logging.getLogger('BehaviorSimulator')
        self.actions = [
            self._move_mouse_smoothly,
            self._scroll_page,
            self._hover_element,
            self._click_element,
            self._simulate_reading
        ]

    async def simulate(self, page: Page, context: Dict) -> None:
        """模拟用户行为，根据页面和上下文执行随机交互"""
        self.logger.info(f"Simulating behavior for {context['url']}")
        await page.wait_for_load_state("domcontentloaded", timeout=10000)  # 等待页面加载

        # 随机选择 3-5 个行为
        num_actions = random.randint(3, 5)
        selected_actions = random.sample(self.actions, num_actions)

        for action in selected_actions:
            try:
                await action(page, context)
                await asyncio.sleep(random.uniform(0.5, 2.0))  # 行为间随机间隔
            except Exception as e:
                self.logger.warning(f"Action {action.__name__} failed: {str(e)}")

        self.logger.info(f"Completed behavior simulation for {context['url']}")

    async def _move_mouse_smoothly(self, page: Page, context: Dict) -> None:
        """模拟平滑的鼠标移动轨迹"""
        steps = random.randint(3, 6)  # 轨迹分段
        for _ in range(steps):
            x = random.randint(100, min(1200, page.viewport_size["width"] - 100))
            y = random.randint(100, min(800, page.viewport_size["height"] - 100))
            await page.mouse.move(x, y, steps=random.randint(5, 15))
            await asyncio.sleep(random.uniform(0.1, 0.3))
        self.logger.debug(f"Mouse moved smoothly to ({x}, {y})")

    async def _scroll_page(self, page: Page, context: Dict) -> None:
        """模拟多次随机滚动"""
        scroll_steps = random.randint(1, 3)
        for _ in range(scroll_steps):
            scroll_distance = random.randint(200, 600)
            direction = random.choice(["up", "down"])
            await page.evaluate(f"window.scrollBy(0, {'-' if direction == 'up' else ''}{scroll_distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        self.logger.debug(f"Scrolled page {scroll_steps} times")

    async def _hover_element(self, page: Page, context: Dict) -> None:
        """悬停在随机可交互元素上"""
        elements = await page.query_selector_all("a, button, [role='button']")
        if elements:
            target = random.choice(elements)
            await target.hover()
            self.logger.debug("Hovered over an interactive element")
        else:
            self.logger.debug("No interactive elements found for hover")

    async def _click_element(self, page: Page, context: Dict) -> None:
        """点击随机可交互元素"""
        elements = await page.query_selector_all("a[href], button, [role='button']")
        if elements:
            target = random.choice(elements)
            try:
                await target.click(timeout=5000)
                self.logger.debug("Clicked an interactive element")
            except Exception as e:
                self.logger.warning(f"Click failed: {str(e)}")
        else:
            await page.click("body")  # 回退到点击页面主体
            self.logger.debug("No interactive elements found, clicked body")

    async def _simulate_reading(self, page: Page, context: Dict) -> None:
        """模拟阅读时间"""
        content_length = len(await page.evaluate("document.body.innerText") or "")
        reading_time = min(10.0, content_length / 500)  # 假设每 500 字符 1 秒
        delay = random.uniform(reading_time * 0.8, reading_time * 1.2)
        await asyncio.sleep(delay)
        self.logger.debug(f"Simulated reading for {delay:.1f} seconds")