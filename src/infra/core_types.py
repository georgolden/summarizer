from dataclasses import dataclass
from typing import Protocol, Any, Optional
from typing_extensions import Callable

@dataclass
class Event:
    id: str
    name: str
    data: Any
    meta: Any
    timestamp: Optional[str] = None

class FileStorage(Protocol):
    async def read(self, path: str) -> bytes: ...
    async def write(self, path: str, data: bytes) -> None: ...

class EventStore(Protocol):
    async def write_event(self, data: Event) -> str: ...
    async def process_events(self, handler: Callable) -> None: ...
