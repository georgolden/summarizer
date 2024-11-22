from dataclasses import dataclass
from typing import List, Protocol, Any
from infra.core_types import EventStore, FileStorage

@dataclass
class TranscriptionInfo:
    title: str
    path: str

@dataclass
class TranscriptionCreatedEvent:
    name: str
    data: List[TranscriptionInfo]

@dataclass
class ClaudeMessage:
    role: str
    content: str

class Deps(Protocol):
    file_storage: FileStorage
    anthropic_client: Any
    event_store: EventStore

@dataclass
class Summary:
    title: str
    summary: str

@dataclass
class SummaryCreatedEvent:
    name: str
    meta: Any
    data: Summary
