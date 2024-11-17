from typing import List, Dict
import asyncio
from domain.types import Deps, SummaryCreatedEvent, TranscriptionsCreatedEvent
from domain.prompt_builder import SummaryPromptBuilder

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

    text_contents = []
    for content_block in response.content:
        if isinstance(content_block, dict) and content_block.get('type') == 'text' and content_block.get('text'):
            # Strip each text part to handle extra spaces
            text_contents.append(content_block['text'].strip())

    if not text_contents:
        raise ValueError("No valid text content in Claude API response")

    combined_text = ' '.join(text_contents)
    if not combined_text.strip():
        raise ValueError("Generated summary is empty")

    return combined_text

async def get_summary(deps: Deps, event: TranscriptionsCreatedEvent) -> SummaryCreatedEvent:
    """
    Process transcriptions and generate a summary using Claude API.
    
    Args:
        deps: Dependencies container with required services
        event: Event containing transcriptions data
        
    Raises:
        ValueError: If input data is invalid
        Exception: For various processing errors
    """
    try:
        transcriptions = event.data
        await validate_transcriptions(transcriptions)

        # Fetch all contents in parallel
        content_tasks = [
            deps.file_storage.read(t['path']) 
            for t in transcriptions
        ]
        contents_bytes = await asyncio.gather(*content_tasks)
        contents = [content.decode('utf-8') for content in contents_bytes]

        prompt_builder = SummaryPromptBuilder()
        messages = prompt_builder.create_messages(transcriptions[0]['title'], contents)

        response = await deps.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0.5,
            system=prompt_builder.get_system_message(),
            messages=messages
        )

        summary = extract_text_from_response(response)

        out_event = {
            'name': "summary_created",
            'data': {
                'title': transcriptions[0]['title'],
                'summary': summary
            }
        }

        await deps.event_store.write_event(out_event)
        return out_event
        
    except (ValueError, AttributeError) as e:
        print(f"Validation error in get_summary: {e}")
        raise
    except Exception as e:
        print(f"Error processing summary: {e}")
        raise
