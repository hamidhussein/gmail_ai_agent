"""
GmailAI Assistant - Local Ollama AI Engine Client
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from core.exceptions import LocalModelUnavailableError

logger = logging.getLogger("GmailAI.LocalModel")


class LocalOllamaClient:
    """Communicates directly with the local Ollama daemon via REST API."""

    def __init__(self, base_url: str = "http://localhost:11434", default_model: str = "qwen2.5:latest"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = 90  # seconds (allows model cold start and complex parsing)

    def is_available(self) -> bool:
        """Checks if the Ollama local daemon is running."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Returns list of models installed locally in Ollama."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return models
        except Exception as e:
            logger.debug(f"Could not retrieve Ollama models list: {e}")
            return []

    def generate_json(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Sends a prompt to Ollama requesting structured JSON output.
        """
        if not self.is_available():
            raise LocalModelUnavailableError(f"Ollama server is unreachable at {self.base_url}")

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        try:
            url = f"{self.base_url}/api/generate"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_response = result.get("response", "")
                parsed = json.loads(raw_response)
                return parsed
        except urllib.error.URLError as e:
            logger.warning(f"Local Ollama connection failed: {e}")
            raise LocalModelUnavailableError(f"Ollama server is unreachable at {self.base_url}")
        except json.JSONDecodeError as e:
            logger.warning(f"Ollama output was not valid JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error calling local Ollama model: {e}")
            raise LocalModelUnavailableError(f"Ollama inference error: {e}")

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None) -> str:
        """Sends a text completion prompt to Ollama."""
        if not self.is_available():
            raise LocalModelUnavailableError(f"Ollama server is unreachable at {self.base_url}")

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
            },
        }
        try:
            url = f"{self.base_url}/api/generate"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama text generation failed: {e}")
            raise LocalModelUnavailableError(f"Ollama generation error: {e}")
