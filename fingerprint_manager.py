import random
from fake_useragent import UserAgent

class FingerprintManager:
    def __init__(
            self,
            browser_type: str = "chromium",
            user_agent: str = None,
            randomize: bool = False,
            screen_width: int = 1280,
            screen_height: int = 720,
            locale: str = "en-US",
            timezone_id: str = "UTC",
            device_scale_factor: float = 1.0,
            geolocation: dict = None
    ):
        self.browser_type = browser_type.lower()
        self.user_agent = user_agent
        self.randomize = randomize
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.locale = locale
        self.timezone_id = timezone_id
        self.device_scale_factor = device_scale_factor
        self.geolocation = geolocation or {"latitude": 0, "longitude": 0}
        self.ua = UserAgent()
        self.browser_map = {
            "chromium": self.ua.chrome,
            "firefox": self.ua.firefox,
            "webkit": self.ua.safari
        }

    def generate_fingerprint(self) -> dict:
        """生成浏览器指纹"""
        if self.randomize:
            ua = self.ua.random
        elif self.user_agent:
            ua = self.user_agent
        else:
            ua = self.browser_map.get(self.browser_type, self.ua.chrome)

        width = self.screen_width if not self.randomize else random.randint(1024, 1920)
        height = self.screen_height if not self.randomize else random.randint(768, 1080)
        return {
            "userAgent": ua,
            "viewport": {"width": width, "height": height},
            "screen": {"width": width, "height": height},
            "locale": self.locale,
            "timezoneId": self.timezone_id,
            "deviceScaleFactor": self.device_scale_factor,
            "geolocation": self.geolocation,
            "browser_type": self.browser_type
        }

    def adjust_fingerprint(self, current_fingerprint: dict) -> dict:
        """动态调整指纹"""
        ua = self.ua.random
        width = random.randint(1024, 1920)
        height = random.randint(768, 1080)
        adjusted = current_fingerprint.copy()
        adjusted.update({
            "userAgent": ua,
            "viewport": {"width": width, "height": height},
            "screen": {"width": width, "height": height}
        })
        return adjusted