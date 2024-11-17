"""Summarizer microservice for processing transcriptions."""

__version__ = "0.1.0"

from .summarizer import main, SummarizerMicroservice

__all__ = ["main", "SummarizerMicroservice"]
