from typing import Any, Optional
from redis.asyncio import Redis
import json
from datetime import datetime, timezone
from infra.core_types import Event, EventStore

class RedisEventStore(EventStore):
    def __init__(
        self,
        redis: Redis,
        event_name: str,
        service_name: str
    ):
        self.redis = redis
        self.stream_name = event_name
        self.service_name = service_name
        self.consumer_name = f"{service_name}-{id(self)}"
        self._running = False
        
    async def ensure_consumer_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.stream_name,
                self.service_name,
                mkstream=True,
                id='0'
            )
        except Exception as e:
            if 'BUSYGROUP' not in str(e):
                raise

    async def write_event(self, event: Event) -> str:
        event_data = {
            'name': event.name,
            'data': json.dumps(event.data)
        }
        # Add timestamp if not provided
        if hasattr(event, 'timestamp') and event.timestamp:
            event_data['timestamp'] = event.timestamp
        else:
            event_data['timestamp'] = datetime.now(timezone.utc).isoformat()

        try:
            message_id = await self.redis.xadd(event.name, event_data)
            return message_id.decode()
        except Exception as e:
            raise

    async def process_events(self, handler: Any) -> None:
        await self.ensure_consumer_group()
        self._running = True

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.service_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: '>'},
                    block=5000
                )
                
                if not messages:
                    continue

                for _, message_list in messages:
                    for message_id, data in message_list:
                        message_id = message_id.decode()
                        
                        # Decode message data
                        decoded_data = {}
                        for k, v in data.items():
                            key = k.decode()
                            value = v.decode()
                            if key == 'data':
                                decoded_data[key] = json.loads(value)
                            else:
                                decoded_data[key] = value

                        event = Event(
                            id=message_id,
                            name=decoded_data['name'],
                            data=decoded_data['data']
                            # timestamp is optional
                        )

                        try:
                            await handler(event)
                            await self.redis.xack(
                                self.stream_name, 
                                self.service_name, 
                                message_id
                            )
                        except Exception as e:
                            raise

            except Exception as e:
                self._running = False
                raise
