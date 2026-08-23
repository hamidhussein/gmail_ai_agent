"""
GmailAI Assistant - Email & Thread Summarizer
"""
import json
import logging
from typing import Dict, Any, List, Optional
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from app.config import config_manager

logger = logging.getLogger("GmailAI.Summarizer")

SUMMARIZE_SYSTEM_PROMPT = """You are an expert executive email summarizer.
Summarize the email or thread clearly and return ONLY a JSON object:
{
  "summary": "<2-3 sentence executive summary>",
  "key_points": ["<bullet point 1>", "<bullet point 2>"],
  "action_items": ["<to-do item 1>", "<to-do item 2>"],
  "deadline": "<extracted date/time or null>"
}
"""


class EmailSummarizer:
    """Summarizes emails and extracts actionable items using AI with extractive fallback."""

    def __init__(self):
        self.local_client = LocalOllamaClient(
            base_url=config_manager.config.ollama_url,
            default_model=config_manager.config.ollama_model,
        )
        self.cloud_client = CloudOpenAIClient(
            default_model=config_manager.config.openai_model,
        )

    def summarize(self, subject: str, sender: str, body_text: str) -> Dict[str, Any]:
        """Summarizes email content using hybrid AI with heuristic fallback."""
        prompt = f"Sender: {sender}\nSubject: {subject}\n\nEmail Content:\n{body_text[:4000]}"

        # Try Local AI
        try:
            res = self.local_client.generate_json(prompt, SUMMARIZE_SYSTEM_PROMPT)
            if res and "summary" in res:
                return res
        except Exception:
            pass

        # Try Cloud AI
        if self.cloud_client.is_configured():
            try:
                res = self.cloud_client.generate_json(prompt, SUMMARIZE_SYSTEM_PROMPT)
                if res and "summary" in res:
                    return res
            except Exception:
                pass

        # Extractive fallback
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]
        first_few = " ".join(lines[:3]) if lines else "No content available."
        action_candidates = [
            l for l in lines
            if any(w in l.lower() for w in ["please", "need", "urgent", "confirm", "review", "send", "by tomorrow", "deadline"])
        ]

        return {
            "summary": first_few[:300] + ("..." if len(first_few) > 300 else ""),
            "key_points": lines[:3] if len(lines) >= 3 else lines,
            "action_items": action_candidates[:3],
            "deadline": None,
        }


email_summarizer = EmailSummarizer()
