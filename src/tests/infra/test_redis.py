import json
import pytest
import asyncio
from redis.asyncio import Redis
from redis.exceptions import RedisError
from infra.redis import RedisEventStore
from infra.core_types import Event

@pytest.fixture
async def redis_client():
    client = Redis(
        host='0.0.0.0',
        port=6379,
        decode_responses=False
    )
    yield client
    await client.flushall()
    await client.aclose()

@pytest.fixture
async def event_store(redis_client):
    # event_name is the stream name
    store = RedisEventStore(
        redis=redis_client,
        event_name="transcriptions_created",
        service_name="test_service"
    )
    yield store
    store._running = False

@pytest.fixture
def test_event():
    return Event(
        id="test-id",
        name="transcriptions_created",
        data={"title": "Test Title", "content": "Test Content"}
    )

# Basic event writing and reading
@pytest.mark.asyncio
async def test_write_event(event_store, test_event):
    # Write to event stream
    msg_id = await event_store.write_event(test_event)
    assert msg_id, "Should return message ID"
    
    # Verify written using stream name (event name)
    messages = await event_store.redis.xread({test_event.name: 0})
    assert messages, "Should find written message"
    assert len(messages) == 1
    stream_name, stream_messages = messages[0]
    assert stream_name.decode() == test_event.name

@pytest.mark.asyncio
async def test_ensure_consumer_group(event_store):
    # Create group
    await event_store.ensure_consumer_group()
    # Second call should handle existing group
    await event_store.ensure_consumer_group()
    
    # Verify group exists in the event stream
    groups = await event_store.redis.xinfo_groups(event_store.stream_name)
    assert len(groups) == 1
    
    # Access the group name using the correct key
    group_info = groups[0]
    assert event_store.service_name in {
        g.decode() if isinstance(g, bytes) else g 
        for g in [group_info.get(b'name'), group_info.get('name')]
        if g is not None
    }

@pytest.mark.asyncio
async def test_event_processing(event_store, test_event):
    processed = []
    
    async def handler(event):
        processed.append(event)
        # Stop processing after receiving one event
        event_store._running = False
    
    # First start the consumer task
    consumer_task = asyncio.create_task(event_store.process_events(handler))
    
    # Give consumer time to set up
    await asyncio.sleep(0.1)
    
    # Then write the event
    await event_store.write_event(test_event)
    
    # Wait for processing to complete with timeout
    try:
        await asyncio.wait_for(consumer_task, timeout=2.0)
    except asyncio.TimeoutError:
        event_store._running = False
        await consumer_task
    
    # Verify processing
    assert len(processed) == 1
    processed_event = processed[0]
    assert processed_event.data == test_event.data
    assert processed_event.name == test_event.name

@pytest.mark.asyncio
async def test_event_acknowledgment(event_store, test_event):
    processed = []
    
    async def handler(event):
        processed.append(event)
        # Stop after processing one event
        event_store._running = False
    
    # First start consumer
    task = asyncio.create_task(event_store.process_events(handler))
    
    # Wait for consumer setup
    await asyncio.sleep(0.1)
    
    # Write event
    await event_store.write_event(test_event)
    
    # Wait for processing
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        event_store._running = False
        await task
    
    # Check no pending messages using xpending_range instead
    pending = await event_store.redis.xpending_range(
        name=event_store.stream_name,
        groupname=event_store.service_name,
        min='-',
        max='+',
        count=10
    )
    
    # Empty list means no pending messages
    assert len(pending) == 0, "Should have no pending messages"
    assert len(processed) == 1, "Should have processed the message"

# Error cases
@pytest.mark.asyncio
async def test_handler_error(event_store, test_event):
    async def failing_handler(event):
        raise ValueError("Handler failed")
    
    await event_store.write_event(test_event)
    
    with pytest.raises(ValueError, match="Handler failed"):
        await event_store.process_events(failing_handler)

@pytest.mark.asyncio
async def test_missing_group_creation(event_store, test_event):
    # Try to process events without group - should create it
    processed = []
    async def handler(event):
        processed.append(event)
    
    task = asyncio.create_task(event_store.process_events(handler))
    await asyncio.sleep(0.1)
    await event_store.write_event(test_event)
    event_store._running = False
    await task
    
    assert len(processed) == 1, "Should process event after auto-creating group"

# Edge Cases for write_event
@pytest.mark.asyncio
async def test_write_event_with_empty_data(event_store):
    empty_event = Event(
        id="empty-id",
        name="transcriptions_created",
        data={}
    )
    msg_id = await event_store.write_event(empty_event)
    assert msg_id, "Should handle empty data"

@pytest.mark.asyncio
async def test_write_event_with_large_data(event_store):
    large_data = {"content": "x" * 1000000}  # 1MB of data
    large_event = Event(
        id="large-id",
        name="transcriptions_created",
        data=large_data
    )
    msg_id = await event_store.write_event(large_event)
    assert msg_id, "Should handle large data"

@pytest.mark.asyncio
async def test_write_event_with_special_characters(event_store):
    special_event = Event(
        id="special-id",
        name="transcriptions_created",
        data={"title": "тест 测试 🚀 \n\t\"'"}
    )
    msg_id = await event_store.write_event(special_event)
    assert msg_id, "Should handle special characters"

# Connection and Error Cases
@pytest.mark.asyncio
async def test_write_event_redis_connection_error():
    bad_client = Redis(host='0.0.0.0', port=6380)  # Wrong port
    store = RedisEventStore(
        redis=bad_client,
        event_name="transcriptions_created",
        service_name="test_service"
    )
    
    with pytest.raises(RedisError):
        await store.write_event(Event(
            id="test",
            name="transcriptions_created",
            data={"test": "data"}
        ))
    
    await bad_client.aclose()

@pytest.mark.asyncio
async def test_consumer_group_multiple_consumers(event_store, redis_client, test_event):
    store2 = RedisEventStore(
        redis=redis_client,
        event_name="transcriptions_created",
        service_name="test_service"
    )

    processed1, processed2 = [], []

    async def handler1(event):
        processed1.append(event)
        if len(processed1) + len(processed2) == 5:
            event_store._running = False
            store2._running = False

    async def handler2(event):
        processed2.append(event)
        if len(processed1) + len(processed2) == 5:
            event_store._running = False
            store2._running = False

    task1 = asyncio.create_task(event_store.process_events(handler1))
    task2 = asyncio.create_task(store2.process_events(handler2))

    try:
        await asyncio.sleep(0.1)

        events = [Event(id=f"test-{i}", name="transcriptions_created", data={"count": i}) for i in range(5)]
        for event in events:
            await event_store.write_event(event)

        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)
    except asyncio.TimeoutError:
        pass
    finally:
        event_store._running = False
        store2._running = False
        await asyncio.gather(task1, task2, return_exceptions=True)

    total_processed = len(processed1) + len(processed2)
    assert total_processed == 5, "All events should be processed"

@pytest.mark.asyncio
async def test_consumer_group_redelivery(event_store, test_event):
    # First consumer that fails
    processed = []
    
    async def failing_handler(event):
        processed.append(event)
        raise Exception("Simulated failure")
    
    # Write event
    await event_store.write_event(test_event)
    
    # First attempt - will fail
    task = asyncio.create_task(event_store.process_events(failing_handler))
    await asyncio.sleep(0.1)
    event_store._running = False
    
    try:
        await task
    except Exception:
        pass
    
    # Check message is pending
    pending = await event_store.redis.xpending_range(
        name=event_store.stream_name,
        groupname=event_store.service_name,
        min='-',
        max='+',
        count=1
    )
    assert len(pending) == 1, "Message should be pending after failure"

@pytest.mark.asyncio
async def test_concurrent_group_creation(redis_client):
    # Create multiple stores concurrently
    stores = [
        RedisEventStore(
            redis=redis_client,
            event_name="transcriptions_created",
            service_name="test_service"
        ) for _ in range(5)
    ]
    
    # Try to create groups concurrently
    await asyncio.gather(*(
        store.ensure_consumer_group() 
        for store in stores
    ))
    
    # Should only create one group
    groups = await redis_client.xinfo_groups("transcriptions_created")
    assert len(groups) == 1, "Should only create one consumer group"

@pytest.mark.asyncio
async def test_process_events_with_invalid_json(event_store):
    # Write event with invalid JSON in Redis directly
    event_data = {
        b'name': b'transcriptions_created',
        b'data': b'invalid{json',
        b'timestamp': b'2024-01-01T00:00:00Z'
    }
    
    await event_store.redis.xadd("transcriptions_created", event_data)
    
    processed = []
    async def handler(event):
        processed.append(event)
        event_store._running = False
    
    task = asyncio.create_task(event_store.process_events(handler))
    
    with pytest.raises(json.JSONDecodeError):
        await asyncio.wait_for(task, timeout=2.0)
