import asyncio
import re
import logging
from playwright.async_api import Page
from readability import Document
from newspaper import Article
from urllib.parse import urlparse

class ArticleParser:
    def __init__(self):
        self.logger = logging.getLogger('ArticleParser')
        self.preset_selectors = [
            "article", "main", "[role='main']", "#content", ".content",
            "#main", ".main", ".post", "#article", ".article"
        ]
        self.parser_history = {
            "readability": 0,
            "newspaper": 0,
            "preset_selector": 0,
            "biggest_text_block": 0,
            "failures": 0,
            "successful_fetches": 0,
            "failed_fetches": 0
        }
        self.domain_mapping = {
            "www.bbc.com": "BBC News",
            "www.bbc.co.uk": "BBC News",
            "www.nytimes.com": "The New York Times",
            "www.theguardian.com": "The Guardian",
            "www.washingtonpost.com": "The Washington Post",
            "www.reuters.com": "Reuters",
            "www.cnn.com": "CNN",
            "www.aljazeera.com": "Al Jazeera"
        }

    def clean_text(self, text: str) -> str:
        """清洗文本，去除多余空白"""
        return re.sub(r'\s+', ' ', text).strip() if text else ""

    async def extract_article(self, page: Page, html: str) -> dict[str, str | list[str] | None] | None:
        """提取文章的标题、发布日期、正文和来源，整合 RuleAdapter 的 HTML 抓取"""
        if not html:
            self.logger.warning("No HTML provided for extraction")
            self.parser_history["failures"] += 1
            self.parser_history["failed_fetches"] += 1
            return None

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            full_html = await page.content()
            if not full_html:
                self.logger.error("Failed to fetch full HTML content from page")
                self.parser_history["failed_fetches"] += 1
                self.parser_history["failures"] += 1
                return None
            self.logger.info(f"Fetched full HTML, length: {len(full_html)} characters")
            self.parser_history["successful_fetches"] += 1
        except Exception as e:
            self.logger.error(f"Error fetching full HTML: {str(e)}")
            self.parser_history["failed_fetches"] += 1
            self.parser_history["failures"] += 1
            return None

        result = {"title": None, "publish_date": None, "content": None, "source": None, "links": []}

        # 1. 尝试 Readability
        try:
            doc = Document(full_html)
            readability_content = self.clean_text(doc.summary())
            if readability_content and len(readability_content) > 50:
                result["title"] = self.clean_text(doc.title())
                result["content"] = readability_content
                result["publish_date"] = await self._extract_date(page)
                result["source"] = await self._extract_source(page)
                self.logger.info("Extracted article with Readability")
                self.parser_history["readability"] += 1
                return result
            self.logger.debug("Readability extracted insufficient content")
        except Exception as e:
            self.logger.error(f"Readability extraction failed: {str(e)}")

        # 2. 尝试 Newspaper4k
        try:
            article = Article(url=page.url)
            article.download(input_html=full_html)
            article.parse()
            newspaper_content = self.clean_text(article.text)
            if newspaper_content and len(newspaper_content) > 50:
                result["title"] = self.clean_text(article.title)
                result["content"] = newspaper_content
                result["publish_date"] = await self._extract_date(page)
                result["source"] = article.source_url or await self._extract_source(page)
                result["links"] = article.urls if hasattr(article, "urls") else []
                self.logger.info("Extracted article with Newspaper4k")
                self.parser_history["newspaper"] += 1
                return result
            self.logger.debug("Newspaper4k extracted insufficient content")
        except Exception as e:
            self.logger.error(f"Newspaper4k extraction failed: {str(e)}")

        # 3. 尝试预定义选择器
        for selector in self.preset_selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    content = await locator.first.text_content()
                    if content and len(content.strip()) > 50:
                        result["content"] = self.clean_text(content)
                        result["title"] = self.clean_text(await page.locator("title").first.text_content()) or "Untitled"
                        result["publish_date"] = await self._extract_date(page)
                        result["source"] = await self._extract_source(page)
                        self.logger.info(f"Extracted article with preset selector: {selector}")
                        self.parser_history["preset_selector"] += 1
                        return result
                self.logger.debug(f"Preset selector {selector} found no sufficient content")
            except Exception as e:
                self.logger.error(f"Preset selector {selector} failed: {str(e)}")

        # 4. 回退到最大文本块
        try:
            text_blocks = await page.evaluate(
                """() => {
                    const blocks = Array.from(document.querySelectorAll('p, div, article, section'));
                    let maxText = '';
                    for (let block of blocks) {
                        const text = block.innerText.trim();
                        if (text.length > maxText.length && text.length > 50) {
                            maxText = text;
                        }
                    }
                    return maxText || null;
                }"""
            )
            if text_blocks:
                result["content"] = self.clean_text(text_blocks)
                result["title"] = self.clean_text(await page.locator("title").first.text_content()) or "Untitled"
                result["publish_date"] = await self._extract_date(page)
                result["source"] = await self._extract_source(page)
                self.logger.info("Extracted article with biggest text block")
                self.parser_history["biggest_text_block"] += 1
                return result
            self.logger.debug("No significant text block found")
        except Exception as e:
            self.logger.error(f"Biggest text block extraction failed: {str(e)}")

        self.logger.error("All extraction methods failed")
        self.parser_history["failures"] += 1
        return None

    async def _extract_date(self, page: Page) -> str | None:
        """提取发布日期，支持多种英文和中文格式"""
        try:
            time_elem = await page.locator("time").first.text_content(timeout=5000)
            if time_elem:
                date = self.clean_text(time_elem)
                if matched_date := self._match_date_format(date):
                    return matched_date
        except Exception as e:
            self.logger.error(f"Date extraction from <time> failed: {str(e)}")

        try:
            meta_date = await page.locator("meta[name='publishdate'], meta[name='pubdate']").first.get_attribute(
                "content", timeout=5000)
            if meta_date:
                if matched_date := self._match_date_format(meta_date):
                    return self.clean_text(matched_date)
        except Exception as e:
            self.logger.error(f"Date extraction from meta failed: {str(e)}")

        try:
            full_text = await page.evaluate("() => document.body.innerText")
            if matched_date := self._match_date_format(full_text):
                return matched_date
        except Exception as e:
            self.logger.error(f"Date extraction from regex failed: {str(e)}")
        return None

    def _match_date_format(self, text: str) -> str | None:
        """匹配多种日期格式，返回标准化日期 (YYYY-MM-DD)"""
        if not text:
            return None

        months = {
            "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
            "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
            "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06", "jul": "07",
            "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
        }

        date_patterns = [
            (r'(\d{4})[-/](\d{2})[-/](\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            (r'(\d{2})[-/](\d{2})[-/](\d{4})', lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),\s+(\d{4})',
             lambda m: f"{m.group(3)}-{months[m.group(1).lower()]}-{m.group(2).zfill(2)}"),
            (r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})',
             lambda m: f"{m.group(3)}-{months[m.group(2).lower()]}-{m.group(1).zfill(2)}"),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        ]

        for pattern, formatter in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date = formatter(match)
                    year, month, day = map(int, date.split('-'))
                    if 1900 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31:
                        return date
                except (ValueError, IndexError):
                    continue
        return None

    async def _extract_source(self, page: Page) -> str | None:
        """优化提取来源，减少等待时间"""
        meta_selectors = [
            "meta[property='og:site_name']",
            "meta[name='publisher']",
            "meta[name='source']",
            "meta[name='og:site']",
            "meta[name='application-name']"
        ]
        brand_selectors = [
            ".bbc-logo", "#branding", ".site-brand", ".publisher", ".source",
            "[class*='logo']", "[id*='logo']", "header .brand"
        ]

        async def try_selector(selector: str, attribute: str = "content") -> str | None:
            try:
                elem = page.locator(selector).first
                value = await elem.get_attribute(attribute, timeout=500) if attribute else await elem.text_content(timeout=500)
                return self.clean_text(value) if value else None
            except Exception:
                return None

        meta_tasks = [try_selector(sel) for sel in meta_selectors]
        brand_tasks = [try_selector(sel) for sel in brand_selectors]
        all_tasks = meta_tasks + brand_tasks

        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, str) and res and len(res) > 2:
                source_type = "meta" if i < len(meta_selectors) else "brand"
                selector = meta_selectors[i] if i < len(meta_selectors) else brand_selectors[i - len(meta_selectors)]
                self.logger.info(f"Extracted source from {source_type} selector {selector}: {res}")
                return res

        try:
            title_text = await page.locator("title").first.text_content(timeout=500)
            if title_text:
                title_parts = re.split(r'[-|]', title_text)
                for part in title_parts:
                    cleaned_part = self.clean_text(part)
                    if cleaned_part and len(cleaned_part) > 2 and "news" in cleaned_part.lower():
                        self.logger.info(f"Extracted source from title: {cleaned_part}")
                        return cleaned_part
        except Exception as e:
            self.logger.error(f"Source extraction from title failed: {str(e)}")

        try:
            parsed_url = urlparse(page.url)
            domain = parsed_url.netloc
            mapped_source = self.domain_mapping.get(domain, domain)
            self.logger.info(f"Extracted source from URL: {mapped_source}")
            return mapped_source
        except Exception as e:
            self.logger.error(f"Source extraction from URL failed: {str(e)}")
        return None

    def get_parser_history(self) -> dict:
        return self.parser_history.copy()