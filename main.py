import argparse
import asyncio
import logging
import os
import yaml
from browser_service import BrowserService
from news_url_collector import NewsURLCollector
from news_crawler import NewsCrawler

def load_config(config_file: str = "config.yaml") -> dict:
    """加载 YAML 配置文件"""
    logger = logging.getLogger(__name__)
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config is None:
                logger.warning(f"Config file {config_file} is empty")
                return {}
            return config
    except Exception as e:
        logger.error(f"Failed to load config from {config_file}: {str(e)}")
        return {}

def parse_args() -> dict:
    """解析命令行参数并覆盖配置文件"""
    parser = argparse.ArgumentParser(description="Financial News Processor")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    # Top-level
    parser.add_argument("--queue-size", type=int, help="Queue size")
    # BrowserService - Fingerprint
    parser.add_argument("--browser-type", help="Browser type for fingerprint")
    parser.add_argument("--user-agent", help="User agent for fingerprint")
    parser.add_argument("--randomize", action="store_true", help="Randomize User-Agent")
    parser.add_argument("--screen-width", type=int, help="Screen width")
    parser.add_argument("--screen-height", type=int, help="Screen height")
    parser.add_argument("--locale", help="Browser locale")
    parser.add_argument("--timezone-id", help="Timezone ID")
    parser.add_argument("--device-scale-factor", type=float, help="Device scale factor")
    parser.add_argument("--latitude", type=float, help="Geolocation latitude")
    parser.add_argument("--longitude", type=float, help="Geolocation longitude")
    # BrowserService - Throttle
    parser.add_argument("--min-rate", type=float, help="Minimum request interval (seconds)")
    parser.add_argument("--max-concurrent", type=int, help="Maximum concurrent requests")
    # NewsURLCollector
    parser.add_argument("--input-dir", help="Input directory")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--rss-urls", nargs="+", help="RSS feed URLs")
    parser.add_argument("--detect-url", help="URL to detect new articles")
    parser.add_argument("--min-interval", type=int, help="Minimum check interval (seconds)")
    parser.add_argument("--max-interval", type=int, help="Maximum check interval (seconds)")
    # NewsCrawler
    parser.add_argument("--ollama-endpoint", help="Ollama service endpoint")
    parser.add_argument("--prompt-file", help="Prompt file path")
    parser.add_argument("--batch-size", type=int, help="Batch size for processing URLs")
    # AdaptiveManager
    parser.add_argument("--min-delay", type=float, help="Minimum delay (seconds)")
    parser.add_argument("--max-delay", type=float, help="Maximum delay (seconds)")
    parser.add_argument("--adjust-threshold-slow", type=float, help="Slow response threshold (seconds)")
    parser.add_argument("--adjust-threshold-fast", type=float, help="Fast response threshold (seconds)")
    parser.add_argument("--random-jitter", type=float, help="Random jitter range (seconds)")
    # DataSaver
    parser.add_argument("--format", choices=["parquet", "csv"], help="Output format (parquet/csv)")

    args = parser.parse_args()
    config = load_config(args.config)

    # 顶层配置
    if args.queue_size:
        config["queue_size"] = args.queue_size

    # BrowserService 配置
    fingerprint_config = config.setdefault("browser_service", {}).setdefault("fingerprint", {})
    if args.browser_type:
        fingerprint_config["browser_type"] = args.browser_type
    if args.user_agent:
        fingerprint_config["user_agent"] = args.user_agent
    if args.randomize:
        fingerprint_config["randomize"] = True
    if args.screen_width:
        fingerprint_config["screen_width"] = args.screen_width
    if args.screen_height:
        fingerprint_config["screen_height"] = args.screen_height
    if args.locale:
        fingerprint_config["locale"] = args.locale
    if args.timezone_id:
        fingerprint_config["timezone_id"] = args.timezone_id
    if args.device_scale_factor:
        fingerprint_config["device_scale_factor"] = args.device_scale_factor
    if args.latitude or args.longitude:
        geo = fingerprint_config.setdefault("geolocation", {})
        geo["latitude"] = args.latitude if args.latitude is not None else geo.get("latitude", 0)
        geo["longitude"] = args.longitude if args.longitude is not None else geo.get("longitude", 0)

    throttle_config = config.setdefault("browser_service", {}).setdefault("throttle", {})
    if args.min_rate is not None:
        throttle_config["min_rate"] = args.min_rate
    if args.max_concurrent is not None:
        throttle_config["max_concurrent"] = args.max_concurrent

    # NewsURLCollector 配置
    collector_config = config.setdefault("NewsURLCollector", {})
    if args.input_dir:
        collector_config["input_dir"] = args.input_dir
    if args.output_dir:
        collector_config["output_dir"] = args.output_dir
        config.setdefault("data_saver", {})["base_filename"] = f"{args.output_dir}/processed_articles"
    if args.rss_urls:
        collector_config["rss_urls"] = args.rss_urls
    if args.detect_url:
        collector_config["detect_url"] = args.detect_url
    if args.min_interval:
        collector_config["min_interval"] = args.min_interval
    if args.max_interval:
        collector_config["max_interval"] = args.max_interval

    # NewsCrawler 配置
    crawler_config = config.setdefault("news_crawler", {})
    if args.ollama_endpoint:
        crawler_config["ollama_endpoint"] = args.ollama_endpoint
    if args.prompt_file:
        crawler_config["prompt_file"] = args.prompt_file
    if args.batch_size:
        crawler_config["batch_size"] = args.batch_size

    # AdaptiveManager 配置
    adaptive_config = config.setdefault("adaptive_manager", {})
    if args.min_delay is not None:
        adaptive_config["min_delay"] = args.min_delay
    if args.max_delay is not None:
        adaptive_config["max_delay"] = args.max_delay
    if args.adjust_threshold_slow is not None:
        adaptive_config["adjust_threshold_slow"] = args.adjust_threshold_slow
    if args.adjust_threshold_fast is not None:
        adaptive_config["adjust_threshold_fast"] = args.adjust_threshold_fast
    if args.random_jitter is not None:
        adaptive_config["random_jitter"] = args.random_jitter

    # DataSaver 配置
    data_saver_config = config.setdefault("data_saver", {})
    if args.format:
        data_saver_config["format"] = args.format

    return config

def setup_logging(log_file: str = "logs/news_processor.log", level: int = logging.INFO) -> None:
    """配置全局日志"""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger('')
    root_logger.setLevel(level)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger('playwright').setLevel(logging.WARNING)

async def main() -> None:
    """主函数，启动新闻收集和抓取任务"""
    config = parse_args()
    setup_logging(log_file="logs/news_processor.log")
    logger = logging.getLogger(__name__)
    logger.info("Starting Financial News Processor")

    browser_service = BrowserService(config)
    queue = asyncio.Queue(maxsize=config.get("queue_size", 10))
    processed_urls = set()

    news_crawler = NewsCrawler(config, browser_service, queue, processed_urls)
    news_url_collector = NewsURLCollector(config, browser_service, queue, processed_urls)

    collector_config = config.get("NewsURLCollector", {})
    try:
        await asyncio.gather(
            news_crawler.process_urls(batch_size=config.get("news_crawler", {}).get("batch_size", 10)),
            news_url_collector.collect(
                min_interval=collector_config.get("min_interval", 600),
                max_interval=collector_config.get("max_interval", 900),
                max_runs=collector_config.get("max_runs", None)
            )
        )
    except Exception as e:
        logger.error(f"Main loop terminated with error: {str(e)}")
    finally:
        logger.info("Shutting down Financial News Processor")

if __name__ == "__main__":
    asyncio.run(main())