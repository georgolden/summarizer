import os
import asyncio
from typing import Any
from dotenv import load_dotenv
from redis.asyncio import Redis
import anthropic
from .domain.constants import ServiceConfig
from .infra.core_types import FileStorage
from .infra.minio import MinioFileStorage
from .infra.redis import RedisEventStore
from .domain.handler.get_summary import get_summary
from .domain.dependencies import Dependencies

class SummarizerMicroservice:
    """
    Complete runtime for the summarizer microservice, including initialization,
    dependency setup, and main execution loop.
    """
    @staticmethod
    async def create() -> 'SummarizerMicroservice':
        """Factory method to create and initialize the microservice"""
        load_dotenv()
        
        redis = Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379))
        )
        
        file_storage = MinioFileStorage(
            endpoint=os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
            access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
            secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin'),
            bucket=os.getenv('MINIO_BUCKET', 'transcriptions'),
            secure=os.getenv('MINIO_SECURE', 'False').lower() == 'true'
        )
        
        anthropic_client = anthropic.Client(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
        
        return SummarizerMicroservice(redis, file_storage, anthropic_client)

    def __init__(
        self,
        redis: Redis,
        file_storage: FileStorage,
        anthropic_client: Any
    ):
        self.redis = redis
        self.event_store = RedisEventStore(
            redis=redis,
            event_name=ServiceConfig.EVENT_NAME,
            service_name=ServiceConfig.NAME
        )
        self.deps = Dependencies(
            file_storage=file_storage,
            anthropic_client=anthropic_client,
            event_store=self.event_store
        )

    async def start(self) -> None:
        """Main execution loop of the summarizer service"""
        try:
            print(f"Starting {ServiceConfig.NAME} service...")
            await self.event_store.process_events(
                lambda event: get_summary(self.deps, event)
            )
        except Exception as e:
            print(f"Fatal error in {ServiceConfig.NAME} service: {e}")
            raise
        finally:
            await self.redis.close()

def main():
    """Entry point for the summarizer microservice"""
    async def run():
        service = await SummarizerMicroservice.create()
        await service.start()

    asyncio.run(run())

if __name__ == "__main__":
    main()
