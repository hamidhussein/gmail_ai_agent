"""
GmailAI Assistant - Application Configuration Manager

Environment variable overrides (useful for CI/CD and Docker deployments):
  GMAILAI_OPENAI_API_KEY   - plaintext OpenAI API key (bypasses encrypted storage)
  GMAILAI_OLLAMA_URL       - override Ollama base URL
  GMAILAI_OLLAMA_MODEL     - override Ollama model name
  GMAILAI_OPENAI_MODEL     - override OpenAI model name
  GMAILAI_AI_MODE          - HYBRID | LOCAL_ONLY | CLOUD_ONLY | HEURISTIC
  GMAILAI_DEMO_MODE        - 1 | 0
  GMAILAI_UI_THEME         - dark | light | system
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.constants import DEFAULT_PROTECTED_DOMAINS
from core.security import security_manager

logger = logging.getLogger("GmailAI.Config")

# Load .env file if present (no-op if python-dotenv is not installed or file missing)
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(dotenv_path=_env_file, override=False)
        logger.info(f"Loaded environment variables from {_env_file}")
except ImportError:
    pass  # python-dotenv not installed — silent fallback


class AppConfigModel(BaseModel):
    """Pydantic model for configuration validation and defaults."""
    app_name: str = "GmailAI Assistant"
    version: str = "1.0.0"
    demo_mode: bool = False

    # AI Router Settings
    ai_mode: str = "HYBRID"  # HYBRID, LOCAL_ONLY, CLOUD_ONLY, HEURISTIC
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:latest"
    openai_model: str = "gpt-4o-mini"
    openai_api_key_encrypted: Optional[str] = None
    hybrid_confidence_threshold: float = 0.85

    # Sync & Automation
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 15
    daily_digest_enabled: bool = True
    daily_digest_time: str = "08:00"
    max_emails_per_sync: int = 50

    # Safety & Protection
    protected_domains: List[str] = Field(default_factory=lambda: list(DEFAULT_PROTECTED_DOMAINS))
    require_double_confirmation_for_delete: bool = True

    # UI Appearance
    ui_theme: str = "light"
    accent_color: str = "#2563EB"

    # Paths
    credentials_path: Optional[str] = None


class ConfigManager:
    """Manages reading and writing application configurations."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Prefer Windows APPDATA, fallback to user home
            app_data = os.environ.get("APPDATA")
            if app_data:
                self.base_dir = Path(app_data) / "GmailAIAssistant"
            else:
                self.base_dir = Path.home() / ".gmailai"
        else:
            self.base_dir = config_dir

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.base_dir / "config.json"
        self.db_path = self.base_dir / "gmailai.db"
        self.log_dir = self.base_dir / "logs"
        self.tokens_dir = self.base_dir / "tokens"
        self.backups_dir = self.base_dir / "backups"

        # Ensure subdirectories exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self._config = self.load()
        self._apply_env_overrides()

    @property
    def config(self) -> AppConfigModel:
        return self._config

    def load(self) -> AppConfigModel:
        """Loads configuration from JSON file or initializes defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AppConfigModel(**data)
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_file}, using defaults: {e}")
                return AppConfigModel()
        else:
            cfg = AppConfigModel()
            self._save_raw(cfg.model_dump())
            return cfg

    def _apply_env_overrides(self) -> None:
        """
        Applies environment variable overrides to the loaded config.
        Env vars take precedence over config.json values but do NOT persist to disk.
        """
        overrides: Dict[str, Any] = {}

        if val := os.environ.get("GMAILAI_OLLAMA_URL"):
            overrides["ollama_url"] = val
        if val := os.environ.get("GMAILAI_OLLAMA_MODEL"):
            overrides["ollama_model"] = val
        if val := os.environ.get("GMAILAI_OPENAI_MODEL"):
            overrides["openai_model"] = val
        if val := os.environ.get("GMAILAI_AI_MODE"):
            overrides["ai_mode"] = val.upper()
        if val := os.environ.get("GMAILAI_DEMO_MODE"):
            overrides["demo_mode"] = val.strip() in ("1", "true", "yes")
        if val := os.environ.get("GMAILAI_UI_THEME"):
            overrides["ui_theme"] = val.lower()

        if overrides:
            updated = self._config.model_dump()
            updated.update(overrides)
            self._config = AppConfigModel(**updated)
            logger.info(f"Applied {len(overrides)} env var override(s): {list(overrides.keys())}")

    def save(self) -> None:
        """Persists current configuration to disk."""
        self._save_raw(self._config.model_dump())

    def _save_raw(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")

    def get_openai_api_key(self) -> Optional[str]:
        """
        Returns the OpenAI API key.
        Priority: GMAILAI_OPENAI_API_KEY env var > encrypted config storage.
        """
        # Env var takes top priority (useful for CI/CD, Docker)
        env_key = os.environ.get("GMAILAI_OPENAI_API_KEY", "").strip()
        if env_key:
            return env_key

        if not self._config.openai_api_key_encrypted:
            return None
        try:
            return security_manager.decrypt_data(self._config.openai_api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt OpenAI API key: {e}")
            return None

    def set_openai_api_key(self, api_key: str) -> None:
        """Encrypts and stores the OpenAI API key."""
        if not api_key:
            self._config.openai_api_key_encrypted = None
        else:
            self._config.openai_api_key_encrypted = security_manager.encrypt_data(api_key.strip())
        self.save()


# Global Config Singleton
config_manager = ConfigManager()
