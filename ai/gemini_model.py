"""
GmailAI Assistant - Google Gemini Cloud Model Client

Uses the official google-genai SDK to access Gemini models
(gemini-2.0-flash, gemini-2.5-flash, etc.) as a cloud AI provider.
Drop-in replacement alongside CloudOpenAIClient in the Hybrid Router.
"""
import json
import logging
from typing import Dict, Any, Optional

from app.config import config_manager
from core.exceptions import CloudModelError

logger = logging.getLogger("GmailAI.GeminiModel")


class CloudGeminiClient:
    """Communicates with Google Gemini models via the google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, default_model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.default_model = default_model

    def _get_api_key(self) -> str:
        key = self.api_key or config_manager.get_gemini_api_key()
        if not key:
            raise CloudModelError("Google Gemini API Key is not configured. Please add it in Settings.")
        return key

    def _get_client(self):
        from google import genai
        return genai.Client(api_key=self._get_api_key())

    def is_configured(self) -> bool:
        """Returns True if a Gemini API key is available."""
        return bool(self.api_key or config_manager.get_gemini_api_key())

    def test_connection(self) -> bool:
        """Validates API Key with a lightweight request."""
        try:
            client = self._get_client()
            models = client.models.list()
            return bool(models)
        except Exception as e:
            logger.warning(f"Gemini test connection failed: {e}")
            return False

    def generate_json(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Requests structured JSON output from Gemini."""
        client = self._get_client()
        target_model = model or config_manager.config.gemini_model or self.default_model

        try:
            from google.genai import types

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            content = response.text
            return json.loads(content)
        except Exception as e:
            logger.error(f"Gemini JSON completion failed: {e}")
            raise CloudModelError(f"Gemini AI analysis failed: {e}")

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
        """Generates text completions from Gemini."""
        client = self._get_client()
        target_model = model or config_manager.config.gemini_model or self.default_model

        try:
            from google.genai import types

            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                ),
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini text generation failed: {e}")
            raise CloudModelError(f"Gemini AI generation failed: {e}")
