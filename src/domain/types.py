from dataclasses import dataclass
from typing import Protocol, Any
from infra.core_types import EventStore, FileStorage

@dataclass
class TranscriptionData:
    title: str
    path: str

@dataclass
class TranscriptionsCreatedEvent:
    id: str
    name: str
    data: TranscriptionData
    timestamp: str 

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
    data: Summary
