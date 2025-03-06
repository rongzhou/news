import random
import logging

class AdaptiveManager:
    def __init__(self, config: dict):
        self.logger = logging.getLogger('AdaptiveManager')
        adaptive_config = config.get("adaptive_manager", {})
        self.min_delay = adaptive_config.get("min_delay", 1.0)
        self.max_delay = adaptive_config.get("max_delay", 5.0)
        self._current_delay = self.min_delay
        self.adjust_threshold_slow = adaptive_config.get("adjust_threshold_slow", 2.0)
        self.adjust_threshold_fast = adaptive_config.get("adjust_threshold_fast", 0.5)
        self.random_jitter = adaptive_config.get("random_jitter", 0.2)
        self.adjustments = {"delay_increased": 0, "delay_decreased": 0}

    def monitor_response(self, response: dict) -> dict[str, bool]:
        """监控响应并返回调整建议"""
        if not response:
            return {
                "slow_down": True,
                "speed_up": False,
                "retry_needed": True,
                "captcha_detected": False,
                "waf_detected": False
            }

        status = response.get("status", 200)
        content = response.get("content", "")
        load_time = response.get("load_time", 1.0)
        feedback = {
            "slow_down": False,
            "speed_up": False,
            "retry_needed": False,
            "captcha_detected": False,
            "waf_detected": False
        }

        if status == 429:
            feedback["slow_down"] = True
            feedback["retry_needed"] = True
        elif status == 403:
            feedback["waf_detected"] = True
            feedback["retry_needed"] = True
        elif status >= 400:
            feedback["retry_needed"] = True
        elif status == 200 and load_time < self.adjust_threshold_fast:
            feedback["speed_up"] = True
        elif status == 200 and load_time > self.adjust_threshold_slow:
            feedback["slow_down"] = True

        if "captcha" in content.lower():
            feedback["captcha_detected"] = True
            feedback["slow_down"] = True
        if "cloudflare" in content.lower():
            feedback["waf_detected"] = True

        self.logger.info(f"Monitoring response: status={status}, load_time={load_time}, feedback={feedback}")
        return feedback

    def adjust_strategy(self, feedback: dict[str, bool], context: dict) -> None:
        """根据反馈调整延迟策略"""
        if feedback["slow_down"]:
            self._current_delay = min(self._current_delay * 1.5, self.max_delay)
            self.adjustments["delay_increased"] += 1
            self.logger.info(f"Delay increased to {self._current_delay:.2f} seconds")
        elif feedback["speed_up"]:
            self._current_delay = max(self._current_delay * 0.8, self.min_delay)
            self.adjustments["delay_decreased"] += 1
            self.logger.info(f"Delay decreased to {self._current_delay:.2f} seconds")

        jitter = random.uniform(-self.random_jitter, self.random_jitter)
        self._current_delay += jitter
        self._current_delay = max(self.min_delay, min(self._current_delay, self.max_delay))

        if feedback["retry_needed"] and "attempts" in context:
            if context["attempts"] >= context.get("max_attempts", 3):  # 默认 max_attempts 为 3
                self.logger.info(f"Retry threshold reached: {context['attempts']} attempts")
                context["stop_attempts"] = True

    def get_current_delay(self) -> float:
        """获取当前的延迟值"""
        return self._current_delay

    def get_adjustments(self) -> dict[str, int]:
        """获取调整统计"""
        return self.adjustments.copy()