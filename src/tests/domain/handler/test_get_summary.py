import pytest
from unittest.mock import AsyncMock, Mock

from domain.handler.get_summary import (
    get_summary, 
    extract_text_from_response
)
from domain.types import Deps, TranscriptionCreatedEvent, SummaryCreatedEvent

@pytest.fixture
def mock_deps():
    return Mock(
        file_storage=AsyncMock(),
        anthropic_client=Mock(messages=AsyncMock()),
        event_store=AsyncMock()
    )

@pytest.fixture
def valid_transcriptions():
    return [
        {"title": "Test Talk", "path": "test/path1.txt"},
        {"title": "Test Talk Part 2", "path": "test/path2.txt"}
    ]

@pytest.fixture
def valid_event(valid_transcriptions):
    return TranscriptionCreatedEvent(
        name="transcriptions_created",
        data=valid_transcriptions
    )

def test_extract_text_from_response_single_content():
    response = Mock()
    response.content = [{"type": "text", "text": "Test summary content"}]
    result = extract_text_from_response(response)
    assert result == "Test summary content"

def test_extract_text_from_response_multiple_content():
    response = Mock()
    response.content = [
        {"type": "text", "text": "First part. "},
        {"type": "text", "text": "Second part."}
    ]
    result = extract_text_from_response(response)
    assert result == "First part. Second part."

def test_extract_text_from_response_no_text_attribute():
    response = Mock()
    response.content = [{"type": "image"}]
    with pytest.raises(ValueError, match="No valid text content"):
        extract_text_from_response(response)

def test_extract_text_from_response_mixed_content():
    response = Mock()
    response.content = [
        {"type": "text", "text": "Valid text"},
        {"type": "image"},
        {"type": "text", "text": "More valid text"}
    ]
    result = extract_text_from_response(response)
    assert result == "Valid text More valid text"

@pytest.mark.asyncio
async def test_get_summary_success(mock_deps, valid_event):
    mock_deps.file_storage.read.side_effect = [b"First content", b"Second content"]
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Test summary"}]
    )

    result = await get_summary(mock_deps, valid_event)

    assert mock_deps.file_storage.read.call_count == 2
    expected_event = SummaryCreatedEvent(
        name="summary_created",
        data={
            'title': "Summary of 2 transcriptions: Test Talk, Test Talk Part 2",
            'summary': "Test summary"
        }
    )
    mock_deps.event_store.write_event.assert_called_once_with(expected_event)
    assert result == expected_event

@pytest.mark.asyncio
async def test_get_summary_success_single_transcription(mock_deps):
    single_event = TranscriptionCreatedEvent(
        name="transcriptions_created",
        data=[{"title": "Single Talk", "path": "test/single.txt"}]
    )
    
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Test summary"}]
    )

    result = await get_summary(mock_deps, single_event)

    expected_event = SummaryCreatedEvent(
        name="summary_created",
        data={
            'title': "Single Talk",
            'summary': "Test summary"
        }
    )
    assert result == expected_event
    mock_deps.file_storage.read.assert_called_once()
    mock_deps.event_store.write_event.assert_called_once_with(expected_event)

@pytest.mark.asyncio
async def test_get_summary_success_many_transcriptions(mock_deps):
    many_titles = [f"Talk {i}" for i in range(5)]
    many_event = TranscriptionCreatedEvent(
        name="transcriptions_created",
        data=[{"title": title, "path": f"test/path{i}.txt"} for i, title in enumerate(many_titles)]
    )
    
    mock_deps.file_storage.read.side_effect = [b"Content"] * 5
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Combined summary"}]
    )

    result = await get_summary(mock_deps, many_event)

    expected_title = "Summary of 5 transcriptions: Talk 0, Talk 1, Talk 2..."
    expected_event = SummaryCreatedEvent(
        name="summary_created",
        data={
            'title': expected_title,
            'summary': "Combined summary"
        }
    )
    assert result == expected_event
    assert mock_deps.file_storage.read.call_count == 5
    mock_deps.event_store.write_event.assert_called_once_with(expected_event)

@pytest.mark.asyncio
async def test_get_summary_invalid_transcription_data(mock_deps):
    invalid_event = TranscriptionCreatedEvent(
        name="transcriptions_created",
        data=[{"title": "Invalid"}]  # Missing path
    )

    with pytest.raises(ValueError, match="Invalid transcription format"):
        await get_summary(mock_deps, invalid_event)

    mock_deps.file_storage.read.assert_not_called()

@pytest.mark.asyncio
async def test_get_summary_file_read_error(mock_deps, valid_event):
    mock_deps.file_storage.read.side_effect = Exception("File not found")

    with pytest.raises(Exception, match="File not found"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_claude_api_error(mock_deps, valid_event):
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_empty_claude_response(mock_deps, valid_event):
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(content=[])

    with pytest.raises(ValueError, match="Empty response from Claude API"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_no_valid_text_content(mock_deps, valid_event):
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "image"}]
    )

    with pytest.raises(ValueError, match="No valid text content in Claude API response"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_empty_summary_text(mock_deps, valid_event):
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "   "}]
    )

    with pytest.raises(ValueError, match="Generated summary is empty"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_utf8_decode_error(mock_deps, valid_event):
    mock_deps.file_storage.read.return_value = b"\xff\xff\xff"  # Invalid UTF-8

    with pytest.raises(UnicodeDecodeError):
        await get_summary(mock_deps, valid_event)
