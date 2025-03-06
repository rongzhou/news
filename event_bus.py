import asyncio

class EventBus:
    def __init__(self):
        self.listeners: dict[str, list[callable]] = {}

    def subscribe(self, event_type: str, callback: callable):
        if event_type not in self.listeners:
            self.listeners[event_type] = []

        self.listeners[event_type].append(callback)

    async def emit(self, event_type: str, data: dict = None):
        if event_type in self.listeners:
            tasks = [callback(data) for callback in self.listeners[event_type]]
            await asyncio.gather(*tasks)
