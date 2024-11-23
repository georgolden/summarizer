import asyncio
from typing import List, Dict
import logging
from domain.types import Deps, SummaryCreatedEvent, TranscriptionCreatedEvent, ClaudeMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def validate_transcriptions(transcriptions: List[Dict[str, str]]) -> None:
    """Validate transcriptions data structure"""
    if not isinstance(transcriptions, list):
        raise ValueError("Expected list of transcriptions")
    if not transcriptions:
        raise ValueError("Transcriptions list is empty")
    for t in transcriptions:
        if not isinstance(t, dict) or 'title' not in t or 'path' not in t:
            raise ValueError("Invalid transcription format - missing title or path")

def extract_text_from_response(response) -> str:
    """Extract text from Claude API response"""
    if not hasattr(response, 'content') or not response.content:
        raise ValueError("Empty response from Claude API")
    
    # The content is a list of content blocks
    for content_block in response.content:
        # Content block is already an object with text attribute
        if hasattr(content_block, 'text'):
            return content_block.text.strip()
    
    raise ValueError("No valid text content in Claude API response")

class KnowledgeExtractorPromptBuilder:
    def __init__(self):
        self._system_message = """You are an expert at extracting and structuring knowledge into universal, actionable frameworks.
        Focus on principles and methodologies that can be applied."""

        self._analysis_prompt = """Analyze this content section and create a structured knowledge framework.
        For each major concept:

        1. Core Definition
           - What it means in principle
           - How to recognize it
           - Why it matters

        2. Universal Application
           - General principles
           - Domain-agnostic methodologies
           - Adaptation guidelines

        3. Implementation Framework
           - Detection/Assessment methods
           - Step-by-step approach
           - Progress measurement
           - Common pitfalls

        4. Integration Guide
           - How it connects with other concepts
           - Prerequisites if any
           - Next steps

        Format in Markdown with clear hierarchical structure.
        Focus on creating a framework that could be applied."""
        self._practical_guide_prompt = """Create an implementation guide based on the analyzed concepts.

        Structure your response as follows:

        # Implementation Framework

        ## 1. Assessment Phase
        - How to evaluate current state
        - Framework for identifying gaps
        - Measurement criteria

        ## 2. Preparation Phase
        - Universal setup steps
        - Resource requirements
        - Prerequisite checklist

        ## 3. Implementation Phase
        - Step-by-step methodology
        - Progress tracking methods
        - Adjustment triggers

        ## 4. Evaluation & Iteration
        - Success criteria
        - Measurement framework
        - Iteration protocol

        For each section:
        - Provide clear, actionable steps
        - Include verification methods
        - List potential obstacles and solutions
        - Define success criteria

        Keep all guidance applicable."""

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _chunk_content(self, content: str, max_tokens: int = 4000) -> List[str]:
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
                
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def create_analysis_messages(self, content: str) -> List[Dict[str, str]]:
        chunks = self._chunk_content(content)
        messages = []
        
        for i, chunk in enumerate(chunks, 1):
            messages.extend([
                ClaudeMessage(
                    role="user",
                    content=f"Content Section {i}:\n\n{chunk}\n\n{self._toc_prompt}"
                )
            ])
        
        return [{"role": m.role, "content": m.content} for m in messages]

    def create_practical_guide_message(self, analyses: List[str]) -> Dict[str, str]:
        combined_analyses = "\n\n---\n\n".join(f"Analysis {i+1}:\n{analysis}" 
                                             for i, analysis in enumerate(analyses))
        return {
            "role": "user",
            "content": f"Based on these analyses:\n\n{combined_analyses}\n\n{self._practical_guide_prompt}"
        }

async def get_summary(deps: Deps, event: TranscriptionCreatedEvent) -> SummaryCreatedEvent:
    try:
        logger.info(f"Got event: {event}")
        transcriptions = event.data
        await validate_transcriptions(transcriptions)

        content_tasks = [deps.file_storage.read(t['path']) for t in transcriptions]
        contents_bytes = await asyncio.gather(*content_tasks)
        contents = [content.decode('utf-8') for content in contents_bytes]
        titles = [t['title'] for t in transcriptions]

        prompt_builder = KnowledgeExtractorPromptBuilder()
        all_analyses = []

        # Process each content for analysis
        for content in contents:
            analysis_messages = prompt_builder.create_analysis_messages(content)
            content_analyses = []

            for message in analysis_messages:
                response = deps.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    temperature=0.5,
                    system=prompt_builder._system_message,
                    messages=[message]
                )
                analysis = extract_text_from_response(response)
                content_analyses.append(analysis)

            all_analyses.extend(content_analyses)

        # Generate practical implementation guide
        practical_message = prompt_builder.create_practical_guide_message(all_analyses)
        practical_response = deps.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.5,
            system=prompt_builder._system_message,
            messages=[practical_message]
        )
        practical_guide = extract_text_from_response(practical_response)

        # Combine analyses and practical guide into final markdown
        final_output = f"""# Content Analysis and Implementation Guide

## Content Overview
{all_analyses[0]}  # First analysis contains ToC and key concepts

## Detailed Analyses
{'---'.join(all_analyses[1:])}  # Remaining detailed analyses

## Practical Implementation Guide
{practical_guide}
"""

        # Create combined title
        combined_title = (
            titles[0] if len(titles) == 1 
            else f"Knowledge Extract of {len(titles)} transcriptions: {', '.join(titles[:3])}{'...' if len(titles) > 3 else ''}"
        )

        out_event = SummaryCreatedEvent(
            name="summary_created",
            meta=event.meta,
            data={
                'title': combined_title,
                'summary': final_output
            }
        )

        await deps.event_store.write_event(out_event)
        logger.info(f"Written event {out_event}")
        return out_event
        
    except Exception as e:
        logger.error(f"Error in knowledge extraction: {e}")
        raise
