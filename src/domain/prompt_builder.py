from typing import List, Dict
from .types import ClaudeMessage

class SummaryPromptBuilder:
    def __init__(self):
        self._system_message = """You are an experienced writer which can analyze and summarize and write articles from different text sources: lectures, interviews, tech talks, entertainment, etc."""
        
        self._summary_structure = """You must write a summary in article style following this structure..."""  # Your full prompt here

    def get_system_message(self) -> str:
        return self._system_message

    def create_messages(self, title: str, contents: List[str]) -> List[Dict[str, str]]:
        messages = []
        
        messages.append(ClaudeMessage(
            role="user",
            content=f"I want to analyze content titled '{title}'. I will share multiple parts that need to be combined into one comprehensive summary."
        ))

        messages.append(ClaudeMessage(
            role="assistant",
            content="I'll help analyze all parts. Please share them and I'll ensure each part is incorporated into the final summary."
        ))

        for i, content in enumerate(contents, 1):
            messages.extend([
                ClaudeMessage(
                    role="user",
                    content=f"Here is Part {i}:\n\n{content}"
                ),
                ClaudeMessage(
                    role="assistant",
                    content=f"I've received and processed Part {i}. I'll keep this content in mind for the complete analysis. Please proceed with any remaining parts."
                )
            ])

        messages.append(ClaudeMessage(
            role="user",
            content=self._summary_structure
        ))

        return [{"role": m.role, "content": m.content} for m in messages]
