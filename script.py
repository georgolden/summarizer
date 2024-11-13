import os
import sys
import re
from pathlib import Path
from typing import List
import anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv();

def clean_text(title: str) -> str:
    """Clean text to contain only letters and spaces."""
    title = title.replace('-', ' ').replace('_', ' ')
    cleaned = re.sub(r'[^a-zA-Z\s]', '', title)
    cleaned = ' '.join(word for word in cleaned.split() if word)
    return cleaned

def extract_common_title(file_paths: List[Path]) -> str:
    """Extract and clean common title from file paths."""
    sample_name = file_paths[0].stem
    if '_' in sample_name:
        sample_name = sample_name.split('_', 2)[-1]
    return clean_text(sample_name)

def read_transcription_file(file_path: Path) -> str:
    """Read transcription file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
            lines = content.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip() and not (line.strip().startswith('{') or line.strip().startswith('"')):
                    start_idx = i
                    break
            return '\n'.join(lines[start_idx:])
    except Exception as e:
        raise Exception(f"Error reading transcription file {file_path}: {e}")

def get_summary(client: anthropic.Client, contents: List[str], title: str) -> str:
    """Get summary using official system prompt behavior."""
    try:
        system_message = """You are an experienced writer which can analyze and summarize and write articles from different text sources: lectures, interviews, tech talks, entertainment, etc."""

        messages = []

        # Initial message
        messages.append({
            "role": "user",
            "content": f"I want to analyze content titled '{title}'. I will share multiple parts that need to be combined into one comprehensive summary."
        })

        messages.append({
            "role": "assistant",
            "content": "I'll help analyze all parts. Please share them and I'll ensure each part is incorporated into the final summary."
        })

        # Add each part with explicit acknowledgment
        for i, content in enumerate(contents, 1):
            messages.extend([
                {
                    "role": "user",
                    "content": f"Here is Part {i}:\n\n{content}"
                },
                {
                    "role": "assistant",
                    "content": f"I've received and processed Part {i}. I'll keep this content in mind for the complete analysis. Please proceed with any remaining parts."
                }
            ])

        # Final summary request
        messages.append({
            "role": "user",
            "content": f"""
You must write a summary in article style following this structure.
Each section must contain as much points as there is in text do not limit yourself with 2-3 points
EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT
It is not just a summary it is an article - it means reader must understand everything without needing ot read the full text.

1. Overview
   - Briefly state the primary purpose or theme of the content.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

2. Key Points
   - Each main idea or essential detail must be included.
   - Provide relevant context for clarity.
   - Add subpoints with examples or important information where needed.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

3. PRACTICAL METHODS/TECHNIQUES EXTRACTED FROM TEXT  
   - Extract all actionable methods, strategies, or techniques from the text, ensuring each is outlined clearly and with necessary context, details and specifix examples.
   - For each technique, specify steps, best practices, frameworks, or conditions for effective application.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

4. NOTABLE CASE STUDIES WITH ASSOCIATED DATA POINTS
   - Identify and list all examples, case studies, or real-world applications highlighted in the text with necessary context, details and specifix examples.
   - Include any significant data points, metrics, or outcomes for each example to provide a thorough understanding of its relevance.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

5. CONTRADICTIONS/TENSIONS IN IDEAS OR FINDINGS
   - Summarize any contradictions, opposing views, or tensions present in the content with necessary context, noting implications or unresolved issues.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

6. Supporting Details
   - Add any critical supporting information, examples, or illustrations that reinforce main points with necessary context.
   - EXPLAIN EACH POINT IN DETAILS AND DO NOT IGNORE THIS INSTRUCTION NO MATTER WHAT

7. Conclusion/Insight
   - Summarize final takeaways, emphasizing the text’s overarching message or relevance.

List any major points from the original text not included and explain why.

Summarize text"""
        })

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0.5,
            system=system_message,
            messages=messages
        )
        
        if hasattr(message, 'content') and len(message.content) > 0:
            return message.content[0].text
        raise Exception("Empty response from Claude API")
        
    except Exception as e:
        raise Exception(f"Error getting summary: {e}")

def main():
    test_paths = [
        Path("transcriptions/transcription_5272d3b6-57b4-481e-94f0-2d4c81f984d1_Joe Rogan Experience #2219 - Donald Trump-1.txt"),
        Path("transcriptions/transcription_5272d3b6-57b4-481e-94f0-2d4c81f984d1_Joe Rogan Experience #2219 - Donald Trump-2.txt"),
        Path("transcriptions/transcription_5272d3b6-57b4-481e-94f0-2d4c81f984d1_Joe Rogan Experience #2219 - Donald Trump-3.txt")
    ]

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    try:
        client = anthropic.Client(api_key=api_key)

        # Verify files exist
        for path in test_paths:
            if not path.exists():
                raise FileNotFoundError(f"Input file not found: {path}")

        # Get title
        title = extract_common_title(test_paths)
        print(f"Using title: {title}")

        # Read transcripts
        print("Reading transcripts...")
        transcripts = []
        for path in test_paths:
            with open(path, 'r', encoding='utf-8') as file:
                transcripts.append(file.read().strip())
        print(f"Successfully read {len(transcripts)} transcripts")

        # Get summary
        print("Requesting summary...")
        summary = get_summary(client, transcripts, title)
        print("Received summary")

        # Save result
        output_dir = Path('summaries')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{title}_{timestamp}.md"
        
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(summary)
        
        print(f"Summary saved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
