# Summarizer Microservice

A microservice that processes transcriptions and generates summaries using Claude AI.

## Features
- Process multiple transcriptions in parallel
- Generate summaries using Claude 3.5 Sonnet
- Store results in Redis event store
- File storage support via MinIO

## Requirements
- Python >= 3.10
- Redis
- MinIO
- Claude API key

## Installation

1. Clone the repository:
```bash
git clone git@github.com:georgolden/summarizer.git
cd summarizer

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e ".[test]"  # Install with test dependencies
# OR
pip install .  # Install without test dependencies
```

## Configuration

Create `.env` file in project root:
```env
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=transcriptions
MINIO_SECURE=False

# Anthropic
ANTHROPIC_API_KEY=your_api_key_here
```

## Running Tests

Run all tests with coverage:
```bash
pytest
```

Run specific test file:
```bash
pytest src/tests/domain/handler/test_get_summary.py
```

Run tests with detailed output:
```bash
pytest -v
```

Coverage report will be generated showing which code paths are tested.

## Project Structure
```
summarizer/                      # Root project directory
├── src/
│   ├── summarizer/             # Main package
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── handler/
│   │   │   │   ├── __init__.py
│   │   │   │   └── get_summary.py
│   │   │   ├── constants.py
│   │   │   ├── dependencies.py
│   │   │   ├── prompt_builder.py
│   │   │   └── types.py
│   │   └── infra/
│   │       ├── __init__.py
│   │       ├── core_types.py
│   │       ├── minio.py
│   │       └── redis.py
│   └── tests/                  # Test package
│       ├── __init__.py
│       └── domain/
│           ├── __init__.py
│           └── handler/
│               ├── __init__.py
│               └── test_get_summary.py
├── .env
└── pyproject.toml
```

## Running the Service

From project root:
```bash
python src/summarizer.py
```

## API Reference

### Input Event Structure
```python
{
    "id": "event-id",
    "name": "transcriptions_created",
    "data": [
        {
            "title": "Talk Title",
            "path": "storage/path/to/transcription.txt"
        }
    ],
    "timestamp": "2024-01-01T00:00:00Z"
}
```

### Output Event Structure
```python
{
    "name": "summary_created",
    "data": {
        "title": "Talk Title",
        "summary": "Generated summary text..."
    }
}
```

## Error Handling
- Invalid transcription data throws ValueError
- File read errors are propagated from storage
- Claude API errors are propagated
- Empty or invalid summaries throw ValueError

## Development

Install development dependencies:
```bash
pip install -e ".[test]"
```

Run tests while developing:
```bash
pytest -v --cov=summarizer --cov-report=term-missing
```