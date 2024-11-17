from ..types import Deps
from ..types import TranscriptionsCreatedEvent
from ..prompt_builder import SummaryPromptBuilder

async def get_summary(deps: Deps, event: TranscriptionsCreatedEvent) -> None:
    try:
        transcriptions = event.data
        if not isinstance(transcriptions, list):
            raise ValueError("Expected list of transcriptions")

        contents = []
        for transcription in transcriptions:
            content = await deps.file_storage.read(transcription['path'])
            contents.append(content.decode('utf-8'))

        prompt_builder = SummaryPromptBuilder()
        messages = prompt_builder.create_messages(transcriptions[0]['title'], contents)

        message = await deps.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0.5,
            system=prompt_builder.get_system_message(),
            messages=messages
        )

        if not hasattr(message, 'content') or len(message.content) == 0:
            raise Exception("Empty response from Claude API")

        summary = message.content[0].text
        
        await deps.event_store.write_event({
            'title': transcriptions[0]['title'],
            'summary': summary
        })
        
    except Exception as e:
        print(f"Error processing summary: {e}")
        raise
