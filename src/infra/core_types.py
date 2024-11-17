from dataclasses import dataclass
from typing import Protocol, Any
from typing_extensions import Callable

class FileStorage(Protocol):
    async def read(self, path: str) -> bytes: ...

class EventStore(Protocol):
    async def write_event(self, data: Any) -> str: ...
    async def process_events(self, handler: Callable) -> None: ...

@dataclass
class Event:
    id: str
    name: str
    data: Any
    timestamp: str
