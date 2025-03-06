import time

# 环境清理模块
class EnvironmentCleaner:
    def __init__(self):
        self.default_state = {
            "cookies": {},
            "local_storage": {},
            "session_storage": {},
            "cache": {},
            "last_cleaned": 0
        }
        self.current_state = self.default_state.copy()

    async def clean_session(self, context: dict) -> None:
        """异步清理会话环境"""
        session_id = context.get("session_id", "unknown")
        if "cookies" in context:
            context["cookies"] = {}
            print(f"Cleaned cookies for session {session_id}")
        if "local_storage" in context:
            context["local_storage"] = {}
            print(f"Cleaned localStorage for session {session_id}")
        if "session_storage" in context:
            context["session_storage"] = {}
            print(f"Cleaned sessionStorage for session {session_id}")
        if "cache" in context:
            context["cache"] = {}
            print(f"Cleaned cache for session {session_id}")

        self.current_state.update({
            "cookies": context.get("cookies", {}),
            "local_storage": context.get("local_storage", {}),
            "session_storage": context.get("session_storage", {}),
            "cache": context.get("cache", {}),
            "last_cleaned": int(time.time())
        })
        print(f"Session {session_id} environment cleaned")

    async def reset_environment(self) -> None:
        """异步重置环境"""
        self.current_state = self.default_state.copy()
        print(f"Environment reset at {int(time.time())}")