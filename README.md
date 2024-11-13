# Transcription Summarization Tool

A Python script that processes transcription files and generates comprehensive summaries using the Anthropic Claude API.

## Features

- Processes multiple transcription files
- Extracts common titles from filenames
- Generates structured summaries using Claude AI
- Saves summaries with timestamps
- Handles file encoding and error cases
- Supports batch processing

## Prerequisites

- Python 3.8+
- Anthropic API key

## Installation

### Option 1: Local Installation with Virtual Environment

1. Clone the repository:
```bash
git clone git@github.com:georgolden/summarizer.git
cd summarizer
```

2. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a .env file in the project root:
```bash
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

### Option 2: Docker Installation

1. Clone the repository:
```bash
git clone git@github.com:georgolden/summarizer.git
cd summarizer
```

2. Create a .env file with your Anthropic API key:
```bash
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

3. Build and run the Docker container:
```bash
# Build the image
docker build -t transcription-summarizer .

# Run the container with mounted volumes
docker run --env-file .env \
  -v "$(pwd)/transcriptions:/app/transcriptions" \
  -v "$(pwd)/summaries:/app/summaries" \
  transcription-summarizer
```

## Usage

1. Place your transcription files in the `transcriptions` directory

2. Run the script:
   
   With virtual environment:
   ```bash
   # Activate venv if not already activated
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   
   # Run script
   python script.py
   ```

   With Docker:
   ```bash
   docker run --env-file .env \
     -v "$(pwd)/transcriptions:/app/transcriptions" \
     -v "$(pwd)/summaries:/app/summaries" \
     transcription-summarizer
   ```

3. Check the `summaries` directory for the generated summary files

## Directory Structure

```
.
├── script.py
├── requirements.txt
├── Dockerfile
├── .env
├── transcriptions/
│   └── (your transcription files)
└── summaries/
    └── (generated summary files)
```

## File Naming

The script expects transcription files to follow a pattern like:
```
transcription_<uuid>_<title>-<part>.txt
```

Generated summaries will be named:
```
<title>_YYYYMMDD_HHMMSS.md
```

## Development

### Virtual Environment Tips
- Always activate the virtual environment before working on the project
- If you install new packages, update requirements.txt:
```bash
pip freeze > requirements.txt
```
- To deactivate the virtual environment:
```bash
deactivate
```

### Docker Development Tips
- Build new image after requirements changes:
```bash
docker build -t transcription-summarizer .
```
- Run with mounted volumes for development:
```bash
docker run --env-file .env \
  -v "$(pwd)/transcriptions:/app/transcriptions" \
  -v "$(pwd)/summaries:/app/summaries" \
  transcription-summarizer
```
- Check container logs:
```bash
docker logs <container-id>
```

## Error Handling

The script includes error handling for:
- Missing API keys
- File not found errors
- File reading errors
- API errors
- Invalid file formats

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)
