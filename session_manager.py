import time, uuid

# 会话管理模块
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = 3600  # 1 小时

    async def create_session(self) -> str:
        """异步创建新会话"""
        session_id = str(uuid.uuid4())
        current_time = int(time.time())
        self.sessions[session_id] = {
            "created_at": current_time,
            "last_active": current_time,
            "cookies": {},
            "auth": None,
            "state": {},
            "active": True
        }
        print(f"Created new session: {session_id}")
        return session_id

    async def maintain_session(self, session_id: str, context: dict) -> None:
        """异步维护会话状态"""
        if session_id not in self.sessions:
            print(f"Session {session_id} not found")
            return

        session = self.sessions[session_id]
        current_time = int(time.time())

        if current_time - session["last_active"] > self.session_timeout:
            print(f"Session {session_id} expired")
            session["active"] = False
            return

        if "cookies" in context:
            session["cookies"].update(context["cookies"])
            print(f"Updated cookies for session {session_id}")
        if "auth" in context:
            session["auth"] = context["auth"]
            print(f"Updated auth for session {session_id}")
        if "state" in context:
            session["state"].update(context["state"])
            print(f"Updated state for session {session_id}")

        session["last_active"] = current_time
        context["session"] = session
        print(f"Session {session_id} maintained")

    async def close_session(self, session_id: str) -> None:
        """异步关闭会话"""
        if session_id not in self.sessions:
            print(f"Session {session_id} not found")
            return

        session = self.sessions[session_id]
        session["active"] = False
        session["closed_at"] = int(time.time())
        session["cookies"] = {}
        session["auth"] = None
        print(f"Session {session_id} closed at {session['closed_at']}")