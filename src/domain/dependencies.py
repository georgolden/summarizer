from typing import Any
from infra.core_types import FileStorage, EventStore

class Dependencies:
    def __init__(
        self,
        file_storage: FileStorage,
        anthropic_client: Any,
        event_store: EventStore
    ):
        self.file_storage = file_storage
        self.anthropic_client = anthropic_client
        self.event_store = event_store
