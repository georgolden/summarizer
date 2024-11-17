from dataclasses import dataclass

@dataclass(frozen=True)
class ServiceConfig:
    NAME: str = "summarizer"
    EVENT_NAME: str = "transcriptions_created"
