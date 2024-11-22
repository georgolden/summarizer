from typing import List, Dict
import logging
import asyncio
from domain.types import Deps, SummaryCreatedEvent, TranscriptionCreatedEvent, ClaudeMessage
from domain.prompt_builder import SummaryPromptBuilder
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def validate_transcriptions(transcriptions: List[Dict[str, str]]) -> None:
    """Validate transcriptions data structure"""
    if not isinstance(transcriptions, list):
        raise ValueError("Expected list of transcriptions")
    if not transcriptions:
        raise ValueError("Transcriptions list is empty")
    for t in transcriptions:
        if not isinstance(t, dict) or 'title' not in t or 'path' not in t:
            raise ValueError("Invalid transcription format - missing title or path")

def extract_text_from_response(response) -> str:
    """Extract text from Claude API response"""
    if not hasattr(response, 'content') or not response.content:
        raise ValueError("Empty response from Claude API")
    
    # The content is a list of content blocks
    for content_block in response.content:
        # Content block is already an object with text attribute
        if hasattr(content_block, 'text'):
            return content_block.text.strip()
    
    raise ValueError("No valid text content in Claude API response")

class ChunkedSummaryPromptBuilder:
    def __init__(self):
        self._system_message = """You are an experienced writer which can analyze and summarize and write articles from different text sources: lectures, interviews, tech talks, entertainment, etc."""
        
        self._intermediate_prompt = """Analyze this content section and provide a detailed summary of its key points, main ideas, and important details. This is part of a larger piece - focus on extracting the essential information that should be included in the final summary."""
        
        self._final_summary_prompt = """Using all the intermediate summaries provided, create a comprehensive final summary that captures the complete content. The summary should be coherent, well-structured, and maintain the context and relationships between different parts of the content."""

    def _estimate_tokens(self, text: str) -> int:
        # Rough estimation - about 4 chars per token
        return len(text) // 4

    def _chunk_content(self, content: str, max_tokens: int = 4000) -> List[str]:
        # Split content into paragraphs
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
                
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def create_intermediate_messages(self, content: str) -> List[Dict[str, str]]:
        chunks = self._chunk_content(content)
        messages = []
        
        for i, chunk in enumerate(chunks, 1):
            messages.extend([
                ClaudeMessage(
                    role="user",
                    content=f"Content Section {i}:\n\n{chunk}\n\n{self._intermediate_prompt}"
                )
            ])
        
        return [{"role": m.role, "content": m.content} for m in messages]

    def create_final_summary_message(self, intermediate_summaries: List[str]) -> Dict[str, str]:
        combined_summaries = "\n\n".join(f"Section {i+1} Summary:\n{summary}" 
                                       for i, summary in enumerate(intermediate_summaries))
        return {
            "role": "user",
            "content": f"Here are the summaries of all content sections:\n\n{combined_summaries}\n\n{self._final_summary_prompt}"
        }

async def get_summary(deps: Deps, event: TranscriptionCreatedEvent) -> SummaryCreatedEvent:
    try:
        logger.info(f"Got event: {event}")
        transcriptions = event.data
        await validate_transcriptions(transcriptions)

        # Fetch all contents
        content_tasks = [deps.file_storage.read(t['path']) for t in transcriptions]
        contents_bytes = await asyncio.gather(*content_tasks)
        contents = [content.decode('utf-8') for content in contents_bytes]
        titles = [t['title'] for t in transcriptions]

        prompt_builder = ChunkedSummaryPromptBuilder()
        all_intermediate_summaries = []

        # Process each content chunk
        for content in contents:
            intermediate_messages = prompt_builder.create_intermediate_messages(content)
            content_summaries = []

            for message in intermediate_messages:
                response = deps.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    temperature=0.5,
                    system=prompt_builder._system_message,
                    messages=[message]
                )
                summary = extract_text_from_response(response)
                content_summaries.append(summary)

            all_intermediate_summaries.extend(content_summaries)

        # Generate final summary
        final_message = prompt_builder.create_final_summary_message(all_intermediate_summaries)
        final_response = deps.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.5,
            system=prompt_builder._system_message,
            messages=[final_message]
        )
        final_summary = extract_text_from_response(final_response)

        # Create combined title
        combined_title = (
            titles[0] if len(titles) == 1 
            else f"Summary of {len(titles)} transcriptions: {', '.join(titles[:3])}{'...' if len(titles) > 3 else ''}"
        )

        out_event = SummaryCreatedEvent(
            name="summary_created",
            meta=event.meta,
            data={
                'title': combined_title,
                'summary': final_summary
            }
        )

        await deps.event_store.write_event(out_event)
        logger.info(f"Written event {out_event}")
        return out_event
        
    except Exception as e:
        logger.error(f"Error processing summary: {e}")
        raise
