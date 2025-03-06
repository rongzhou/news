import asyncio
import logging
from abc import ABC, abstractmethod

class Plugin(ABC):
    @abstractmethod
    async def execute(self, context: dict) -> None:
        """执行插件并修改上下文"""
        pass

class PluginManager:
    def __init__(self):
        self.logger = logging.getLogger('PluginManager')
        self.plugins: list[Plugin] = []

    def register_plugin(self, plugin: Plugin) -> None:
        """注册新插件"""
        if plugin not in self.plugins:
            self.plugins.append(plugin)
            self.logger.info(f"Registered plugin: {plugin.__class__.__name__}, total plugins: {len(self.plugins)}")
        else:
            self.logger.warning(f"Plugin {plugin.__class__.__name__} already registered")

    async def execute_plugins(self, context: dict) -> None:
        """异步执行所有插件并根据反馈触发对策"""
        if not self.plugins:
            self.logger.info("No plugins registered")
            return

        tasks = [plugin.execute(context) for plugin in self.plugins]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for plugin, result in zip(self.plugins, results):
            plugin_name = plugin.__class__.__name__
            if isinstance(result, Exception):
                self.logger.error(f"Error executing plugin {plugin_name}: {str(result)}")
            else:
                self.logger.info(f"Plugin {plugin_name} executed successfully")

        # 根据 context 触发对策
        if context.get("adjust_fingerprint"):
            self.logger.info("Triggering fingerprint adjustment based on plugin feedback")

        if suggested_delay := context.get("suggested_delay"):
            self.logger.info(f"Applying suggested delay: {suggested_delay:.2f} seconds")
            await asyncio.sleep(suggested_delay)

    def get_registered_plugins(self) -> list[str]:
        """获取已注册插件的名称列表"""
        return [plugin.__class__.__name__ for plugin in self.plugins]

class AntiBotPlugin(Plugin):
    def __init__(self):
        self.logger = logging.getLogger('AntiBotPlugin')

    async def execute(self, context: dict) -> None:
        """检测反爬机制并建议对策"""
        response = context.get("response", {})
        content = response.get("content", "").lower()
        if "cloudflare" in content or "captcha" in content:
            self.logger.info("AntiBotPlugin: Cloudflare or CAPTCHA detected, applying countermeasures")
            context["adjust_fingerprint"] = True
            context["suggested_delay"] = 2.0