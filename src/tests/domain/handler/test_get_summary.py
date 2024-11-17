import pytest
from unittest.mock import AsyncMock, Mock

from domain.handler.get_summary import (
    get_summary, 
    validate_transcriptions,
    extract_text_from_response
)
from domain.types import Deps, TranscriptionsCreatedEvent

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
    return TranscriptionsCreatedEvent(
        id="test-id",
        name="transcriptions_created",
        data=valid_transcriptions,
        timestamp="2024-01-01T00:00:00Z"
    )

def test_extract_text_from_response_single_content():
    # Mock Claude's response format: [{"type": "text", "text": "Hi, I'm Claude."}]
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
    response.content = [{"type": "image"}]  # No text field
    with pytest.raises(ValueError, match="No valid text content"):
        extract_text_from_response(response)

def test_extract_text_from_response_mixed_content():
    response = Mock()
    response.content = [
        {"type": "text", "text": "Valid text"},
        {"type": "image"},  # Should be skipped
        {"type": "text", "text": "More valid text"}
    ]
    result = extract_text_from_response(response)
    assert result == "Valid text More valid text"

@pytest.mark.asyncio
async def test_get_summary_success(mock_deps, valid_event):
    # Setup mocks
    mock_deps.file_storage.read.side_effect = [b"First content", b"Second content"]
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Test summary"}]
    )

    result = await get_summary(mock_deps, valid_event)

    # Verify calls
    assert mock_deps.file_storage.read.call_count == 2
    mock_deps.event_store.write_event.assert_called_once_with({
        'name': "summary_created",
        'data': {
            'title': "Test Talk",
            'summary': "Test summary"
        }
    })
    assert result == {
        'name': "summary_created",
        'data': {
            'title': "Test Talk",
            'summary': "Test summary"
        }
    }

@pytest.mark.asyncio
async def test_get_summary_success_single_transcription(mock_deps):
    # Test with single transcription
    single_event = TranscriptionsCreatedEvent(
        id="test-id",
        name="transcriptions_created",
        data=[{"title": "Single Talk", "path": "test/single.txt"}],
        timestamp="2024-01-01T00:00:00Z"
    )
    
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Test summary"}]
    )

    result = await get_summary(mock_deps, single_event)

    assert isinstance(result, dict)
    assert result['name'] == "summary_created"
    assert result['data']['title'] == "Single Talk"
    assert result['data']['summary'] == "Test summary"
    mock_deps.file_storage.read.assert_called_once()
    mock_deps.event_store.write_event.assert_called_once_with(result)

@pytest.mark.asyncio
async def test_get_summary_success_multiple_transcriptions(mock_deps, valid_event):
    # Test with multiple transcriptions
    mock_deps.file_storage.read.side_effect = [
        b"First content",
        b"Second content"
    ]
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Combined summary"}]
    )

    result = await get_summary(mock_deps, valid_event)

    assert result['name'] == "summary_created"
    assert result['data']['title'] == "Test Talk"
    assert result['data']['summary'] == "Combined summary"
    assert mock_deps.file_storage.read.call_count == 2
    mock_deps.event_store.write_event.assert_called_once_with(result)

@pytest.mark.asyncio
async def test_get_summary_invalid_transcription_data(mock_deps):
    # Test with invalid transcription data
    invalid_event = TranscriptionsCreatedEvent(
        id="test-id",
        name="transcriptions_created",
        data=[{"title": "Invalid"}],  # Missing path
        timestamp="2024-01-01T00:00:00Z"
    )

    with pytest.raises(ValueError, match="Invalid transcription format"):
        await get_summary(mock_deps, invalid_event)

    mock_deps.file_storage.read.assert_not_called()

@pytest.mark.asyncio
async def test_get_summary_file_read_error(mock_deps, valid_event):
    # Test file reading error
    mock_deps.file_storage.read.side_effect = Exception("File not found")

    with pytest.raises(Exception, match="File not found"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_claude_api_error(mock_deps, valid_event):
    # Test Claude API error
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_empty_claude_response(mock_deps, valid_event):
    # Test empty response from Claude
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(content=[])

    with pytest.raises(ValueError, match="Empty response from Claude API"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_no_valid_text_content(mock_deps, valid_event):
    # Test response with content but no valid text
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "image"}]  # No text content
    )

    with pytest.raises(ValueError, match="No valid text content in Claude API response"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_empty_summary_text(mock_deps, valid_event):
    # Test empty summary text
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "   "}]
    )

    with pytest.raises(ValueError, match="Generated summary is empty"):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_utf8_decode_error(mock_deps, valid_event):
    # Test UTF-8 decode error
    mock_deps.file_storage.read.return_value = b"\xff\xff\xff"  # Invalid UTF-8

    with pytest.raises(UnicodeDecodeError):
        await get_summary(mock_deps, valid_event)

@pytest.mark.asyncio
async def test_get_summary_preserves_original_title(mock_deps):
    # Test that original title is preserved in output
    title = "Special Title: With Punctuation! 123"
    preserves_event = TranscriptionsCreatedEvent(
        id="test-id",
        name="transcriptions_created",
        data=[{"title": title, "path": "test/path.txt"}],
        timestamp="2024-01-01T00:00:00Z"
    )
    
    mock_deps.file_storage.read.return_value = b"Test content"
    mock_deps.anthropic_client.messages.create.return_value = Mock(
        content=[{"type": "text", "text": "Summary"}]
    )

    result = await get_summary(mock_deps, preserves_event)

    assert result['data']['title'] == title
    mock_deps.event_store.write_event.assert_called_once_with(result)
