"""
GmailAI Assistant - Credentials Manager

Provides Google OAuth 2.0 client configuration with three resolution layers:
  1. User-supplied custom credentials file (via Settings or config.json path)
  2. Environment variable overrides (GMAILAI_GOOGLE_CLIENT_ID / GMAILAI_GOOGLE_CLIENT_SECRET)
  3. Built-in default Desktop OAuth client configuration (zero-config for end users)
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import config_manager
from core.exceptions import ConfigurationError

logger = logging.getLogger("GmailAI.CredentialManager")

# ---------------------------------------------------------------------------
# Built-in default Desktop OAuth Client ID
# This allows end users to connect Gmail without creating a Google Cloud
# project.  Replace these with your own published OAuth client credentials
# before distributing the app publicly.
# ---------------------------------------------------------------------------
_DEFAULT_CLIENT_ID = os.environ.get(
    "GMAILAI_GOOGLE_CLIENT_ID",
    "YOUR_DEFAULT_CLIENT_ID.apps.googleusercontent.com",
)
_DEFAULT_CLIENT_SECRET = os.environ.get(
    "GMAILAI_GOOGLE_CLIENT_SECRET",
    "YOUR_DEFAULT_CLIENT_SECRET",
)


def _build_default_client_config() -> Dict[str, Any]:
    """Constructs a Google OAuth Desktop client config dict from built-in defaults."""
    return {
        "installed": {
            "client_id": _DEFAULT_CLIENT_ID,
            "client_secret": _DEFAULT_CLIENT_SECRET,
            "project_id": "gmailai-assistant",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }


class CredentialManager:
    """Validates and manages Google Cloud OAuth client credentials.

    Resolution order for ``get_client_config()``:
      1. Explicit ``custom_path`` argument (caller-supplied file).
      2. ``credentials_path`` stored in app config (user browsed / pasted JSON).
      3. ``credentials.json`` located in the app data directory.
      4. Environment variable overrides (``GMAILAI_GOOGLE_CLIENT_ID`` / ``GMAILAI_GOOGLE_CLIENT_SECRET``).
      5. Built-in default Desktop client configuration.
    """

    def __init__(self):
        self.credentials_path = config_manager.config.credentials_path

    # ------------------------------------------------------------------
    # Primary accessor
    # ------------------------------------------------------------------
    def get_client_config(self, custom_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Loads and validates client credentials JSON structure.

        Falls back through user-supplied path → saved config path → default
        file location → env overrides → built-in defaults.
        """
        # 1. Explicit caller-supplied path
        target_path = custom_path or self.credentials_path
        if target_path:
            cfg = self._load_from_file(target_path)
            if cfg:
                return cfg

        # 2. Default file location in app data dir
        default_path = config_manager.base_dir / "credentials.json"
        if default_path.exists():
            cfg = self._load_from_file(str(default_path))
            if cfg:
                return cfg

        # 3. Built-in default / env-override configuration (zero-config)
        return _build_default_client_config()

    def has_custom_credentials(self) -> bool:
        """Returns True if the user has provided their own credentials file."""
        target_path = self.credentials_path
        if target_path and Path(target_path).exists():
            return True
        default_path = config_manager.base_dir / "credentials.json"
        return default_path.exists()

    def get_client_id(self) -> str:
        """Returns the active OAuth client ID string for display purposes."""
        cfg = self.get_client_config()
        if cfg:
            section = cfg.get("installed") or cfg.get("web") or {}
            return section.get("client_id", "")
        return ""

    def is_using_default_credentials(self) -> bool:
        """Returns True when the active config is the built-in default (not user-supplied)."""
        return not self.has_custom_credentials()

    # ------------------------------------------------------------------
    # User-supplied credential management (power users / enterprise)
    # ------------------------------------------------------------------
    def set_credentials_file(self, file_path: str) -> bool:
        """Saves path to credentials file after validation."""
        config = self._load_from_file(file_path)
        if not config:
            raise ConfigurationError("Selected file is not a valid Google OAuth Client ID JSON file.")

        config_manager.config.credentials_path = file_path
        config_manager.save()
        self.credentials_path = file_path
        return True

    def save_client_config_from_json(self, json_text: str) -> str:
        """
        Parses raw JSON text (pasted by user) and saves it as credentials.json.
        Returns the saved file path on success.
        Raises ConfigurationError on invalid JSON.
        """
        try:
            data = json.loads(json_text.strip())
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON: {e}")

        if "installed" not in data and "web" not in data:
            raise ConfigurationError(
                "Invalid format. The JSON must contain an 'installed' or 'web' key. "
                "Make sure you downloaded 'OAuth 2.0 Client ID' (Desktop app) credentials from Google Cloud Console."
            )

        save_path = config_manager.base_dir / "credentials.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        config_manager.config.credentials_path = str(save_path)
        config_manager.save()
        self.credentials_path = str(save_path)
        logger.info(f"Google OAuth credentials saved to {save_path}")
        return str(save_path)

    def clear_custom_credentials(self) -> None:
        """Removes user-supplied credentials and reverts to built-in defaults."""
        # Clear config reference
        config_manager.config.credentials_path = None
        config_manager.save()
        self.credentials_path = None

        # Remove file if present
        default_path = config_manager.base_dir / "credentials.json"
        if default_path.exists():
            try:
                default_path.unlink()
                logger.info("Custom credentials.json removed; reverting to built-in defaults.")
            except Exception as e:
                logger.warning(f"Could not remove credentials.json: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_from_file(file_path: str) -> Optional[Dict[str, Any]]:
        """Loads and validates a credentials JSON file."""
        p = Path(file_path)
        if not p.exists():
            return None

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "installed" in data or "web" in data:
                return data
            else:
                logger.warning(f"Invalid Google OAuth credentials JSON format at {file_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to read credentials file {file_path}: {e}")
            return None


credential_manager = CredentialManager()
