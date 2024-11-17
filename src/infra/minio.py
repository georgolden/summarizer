from minio import Minio
from minio.error import S3Error
from infra.core_types import FileStorage
import io
import asyncio
from functools import partial

class MinioFileStorage(FileStorage):
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = True
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket = bucket
        self._ensure_bucket()
        
    def _ensure_bucket(self) -> None:
        """Ensure bucket exists"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            raise Exception(f"Failed to initialize MinIO bucket: {e}")

    async def read(self, path: str) -> bytes:
        """Read file from MinIO asynchronously"""
        try:
            # Run get_object in thread pool since minio-py is synchronous
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                partial(self.client.get_object, self.bucket, path)
            )
            
            # Read data
            data = await loop.run_in_executor(
                None,
                response.read
            )
            
            return data
            
        except S3Error as e:
            raise Exception(f"Failed to read file from MinIO: {e}")
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()

    async def write(self, path: str, data: bytes) -> None:
        """Write file to MinIO asynchronously"""
        try:
            data_stream = io.BytesIO(data)
            data_length = len(data)
            
            # Run put_object in thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                partial(
                    self.client.put_object,
                    self.bucket,
                    path,
                    data_stream,
                    data_length
                )
            )
            
        except S3Error as e:
            raise Exception(f"Failed to write file to MinIO: {e}")
        finally:
            if 'data_stream' in locals():
                data_stream.close()

    async def delete(self, path: str) -> None:
        """Delete file from MinIO asynchronously"""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                partial(self.client.remove_object, self.bucket, path)
            )
        except S3Error as e:
            raise Exception(f"Failed to delete file from MinIO: {e}")
