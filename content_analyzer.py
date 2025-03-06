import json
import logging
import yaml
import aiohttp

class ContentAnalyzer:
    def __init__(self, ollama_endpoint: str = "http://localhost:11434/api/generate", prompt_file: str = "prompts.yaml"):
        """初始化，指定 Ollama 服务地址和提示词文件"""
        self.ollama_endpoint = ollama_endpoint
        self.model = "qwen2.5:latest"  # 默认模型，可调整
        self.analysis_history = {
            "successful_analyses": 0,
            "failed_analyses": 0
        }
        self.logger = logging.getLogger('ContentAnalyzer')
        self.prompt_templates = self._load_prompt_templates(prompt_file)

    def _load_prompt_templates(self, prompt_file: str) -> dict[str, str]:
        """从 YAML 文件加载提示词模板"""
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                templates = yaml.safe_load(f)
            if not templates or 'en' not in templates or 'zh' not in templates:
                raise ValueError("Invalid prompt file: missing 'en' or 'zh' templates")
            return templates
        except Exception as e:
            self.logger.error(f"Failed to load prompt templates: {str(e)}")
            return {
                "en": "Analyze the content: {content}",
                "zh": "分析内容：{content}"
            }

    async def analyze_content(self,
                              content: str,
                              language: str = "en",
                              max_keywords: int = 10,
                              summary_length: int = 100) -> dict | None:
        """分析文章正文，提取关键词、摘要和分类标签，支持动态参数"""
        if not content or len(content) < 50:
            self.logger.error("Content too short or empty for analysis")
            self.analysis_history["failed_analyses"] += 1
            return None

        try:
            # 根据语言选择提示词模板
            lang_key = "zh" if language == "zh" else "en"
            prompt_template = self.prompt_templates.get(lang_key, self.prompt_templates["en"])
            # 动态替换参数
            prompt = prompt_template.format(
                max_keywords=max_keywords,
                summary_length=summary_length,
                content=content
            )

            # 调用 Ollama LLM 服务
            response = await self._call_ollama(prompt)
            if not response:
                self.logger.error("Failed to get response from Ollama")
                self.analysis_history["failed_analyses"] += 1
                return None

            # 解析 JSON 响应
            result = json.loads(response)
            analysis = {
                "keywords": result.get("keywords", []),
                "summary": result.get("summary", ""),
                "labels": {
                    "market_type": result.get("labels", {}).get("market_type", "Other"),
                    "sentiment": result.get("labels", {}).get("sentiment", "Neutral"),
                    "market_impact": result.get("labels", {}).get("market_impact", "Neutral")
                }
            }

            self.logger.info(f"Analyzed content: {analysis}")
            self.analysis_history["successful_analyses"] += 1
            return analysis

        except Exception as e:
            self.logger.error(f"Content analysis failed: {str(e)}")
            self.analysis_history["failed_analyses"] += 1
            return None

    async def _call_ollama(self, prompt: str) -> str | None:
        """异步调用 Ollama 本地 LLM 服务"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.ollama_endpoint,
                                        json=payload,
                                        timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        print(f"Ollama request failed with status: {response.status}")
                        return None
                    data = await response.json()
                    return data.get("response", "")
        except Exception as e:
            print(f"Ollama call failed: {str(e)}")
            return None

    def get_analysis_history(self) -> dict:
        return self.analysis_history.copy()