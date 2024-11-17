import pytest
from minio import Minio
from minio.error import S3Error
from infra.minio import MinioFileStorage

@pytest.fixture
def minio_storage():
    storage = MinioFileStorage(
        endpoint="0.0.0.0:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",
        secure=False
    )
    return storage

@pytest.mark.asyncio
async def test_bucket_initialization(minio_storage):
    # Ensure bucket exists
    assert minio_storage.client.bucket_exists("test-bucket")

@pytest.mark.asyncio
async def test_write_read_delete_file(minio_storage):
    # Write a file
    path = "test-file.txt"
    data = b"Hello, MinIO!"
    await minio_storage.write(path, data)
    
    # Read the file
    read_data = await minio_storage.read(path)
    assert read_data == data

    # Delete the file
    await minio_storage.delete(path)
    with pytest.raises(Exception, match="NoSuchKey"):
        await minio_storage.read(path)

@pytest.mark.asyncio
async def test_read_non_existent_file(minio_storage):
    with pytest.raises(Exception, match="NoSuchKey"):
        await minio_storage.read("non-existent-file.txt")

@pytest.mark.asyncio
async def test_delete_non_existent_file(minio_storage):
    # Deleting a non-existent file should not raise an error but log a warning
    try:
        await minio_storage.delete("non-existent-file.txt")
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")
