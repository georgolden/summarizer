from dataclasses import dataclass
from typing import Protocol, Any
from typing_extensions import Callable

@dataclass
class Event:
    id: str
    name: str
    data: Any
    timestamp: str

class FileStorage(Protocol):
    async def read(self, path: str) -> bytes: ...

class EventStore(Protocol):
    async def write_event(self, data: Event) -> str: ...
    async def process_events(self, handler: Callable) -> None: ...
