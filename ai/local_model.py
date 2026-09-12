"""
GmailAI Assistant - Local Ollama AI Engine Client
"""
import json
import logging
import urllib.request
import urllib.error
import time
from typing import Dict, Any, Optional, List, Tuple
from core.exceptions import LocalModelUnavailableError

logger = logging.getLogger("GmailAI.LocalModel")


class LocalOllamaClient:
    """Communicates directly with the local Ollama daemon via REST API."""

    _cached_availability: Dict[str, Tuple[float, bool]] = {}

    def __init__(self, base_url: str = "http://localhost:11434", default_model: str = "qwen2.5:latest"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = 90  # seconds (allows model cold start and complex parsing)

    def is_available(self, force_check: bool = False) -> bool:
        """Checks if the Ollama local daemon is running with TTL caching."""
        now = time.time()
        cache_entry = self._cached_availability.get(self.base_url)
        if not force_check and cache_entry is not None:
            cached_time, is_ok = cache_entry
            if now - cached_time < 15.0:  # 15-second TTL cache
                return is_ok

        try:
            # Bypass Windows IPv6 resolution latency for localhost
            check_url = self.base_url
            if "://localhost" in check_url:
                check_url = check_url.replace("://localhost", "://127.0.0.1")
            url = f"{check_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                is_ok = (resp.status == 200)
                self._cached_availability[self.base_url] = (now, is_ok)
                return is_ok
        except Exception:
            self._cached_availability[self.base_url] = (now, False)
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
