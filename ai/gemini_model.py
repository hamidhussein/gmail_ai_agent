"""
GmailAI Assistant - Google Gemini Cloud Model Client

Uses the official google-genai SDK to access Gemini models
(gemini-3.6-flash, etc.) as a cloud AI provider.
Drop-in replacement alongside CloudOpenAIClient in the Hybrid Router.
"""
import json
import logging
from typing import Dict, Any, Optional

from app.config import config_manager
from core.exceptions import CloudModelError

logger = logging.getLogger("GmailAI.GeminiModel")

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DEPRECATED_MODELS = {"gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"}


class CloudGeminiClient:
    """Communicates with Google Gemini models via the google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, default_model: str = DEFAULT_GEMINI_MODEL):
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

    def _resolve_model(self, model: Optional[str] = None) -> str:
        configured = config_manager.config.gemini_model if config_manager else None
        target = model or configured or self.default_model
        if target in DEPRECATED_MODELS:
            target = DEFAULT_GEMINI_MODEL
        return target

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
        target_model = self._resolve_model(model)

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
            raw = response.text.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(raw)
        except Exception as e:
            err_str = str(e)
            if "404" in err_str and target_model != DEFAULT_GEMINI_MODEL:
                logger.warning(f"Model {target_model} returned 404, retrying with {DEFAULT_GEMINI_MODEL}...")
                return self.generate_json(prompt, system_prompt, model=DEFAULT_GEMINI_MODEL)
            logger.error(f"Gemini JSON completion failed: {e}")
            raise CloudModelError(f"Gemini AI analysis failed: {e}")

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
        """Generates text completions from Gemini."""
        client = self._get_client()
        target_model = self._resolve_model(model)

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
            err_str = str(e)
            if "404" in err_str and target_model != DEFAULT_GEMINI_MODEL:
                logger.warning(f"Model {target_model} returned 404, retrying with {DEFAULT_GEMINI_MODEL}...")
                return self.generate_text(prompt, system_prompt, model=DEFAULT_GEMINI_MODEL)
            logger.error(f"Gemini text generation failed: {e}")
            raise CloudModelError(f"Gemini AI generation failed: {e}")
