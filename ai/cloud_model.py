"""
GmailAI Assistant - Cloud OpenAI Model Client
"""
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

from app.config import config_manager
from core.exceptions import CloudModelError

logger = logging.getLogger("GmailAI.CloudModel")


class CloudOpenAIClient:
    """Communicates with OpenAI models (GPT-4o, GPT-4o-mini)."""

    def __init__(self, api_key: Optional[str] = None, default_model: str = "gpt-4o-mini"):
        self.api_key = api_key or config_manager.get_openai_api_key()
        self.default_model = default_model

    def _get_client(self) -> OpenAI:
        key = self.api_key or config_manager.get_openai_api_key()
        if not key:
            raise CloudModelError("OpenAI API Key is not configured. Please add it in Settings.")
        return OpenAI(api_key=key)

    def is_configured(self) -> bool:
        """Returns True if an API key is available."""
        return bool(self.api_key or config_manager.get_openai_api_key())

    def test_connection(self) -> bool:
        """Validates API Key with a lightweight request."""
        try:
            client = self._get_client()
            models = client.models.list()
            return bool(models)
        except Exception as e:
            logger.warning(f"OpenAI test connection failed: {e}")
            return False

    def generate_json(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Requests structured JSON output from OpenAI."""
        client = self._get_client()
        target_model = model or config_manager.config.openai_model or self.default_model

        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"OpenAI JSON completion failed: {e}")
            raise CloudModelError(f"Cloud AI analysis failed: {e}")

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
        """Generates text completions from OpenAI."""
        client = self._get_client()
        target_model = model or config_manager.config.openai_model or self.default_model

        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI text generation failed: {e}")
            raise CloudModelError(f"Cloud AI generation failed: {e}")
