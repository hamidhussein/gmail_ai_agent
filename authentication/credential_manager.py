"""
GmailAI Assistant - Credentials Manager
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import config_manager
from core.exceptions import ConfigurationError

logger = logging.getLogger("GmailAI.CredentialManager")


class CredentialManager:
    """Validates and manages Google Cloud OAuth client credentials."""

    def __init__(self):
        self.credentials_path = config_manager.config.credentials_path

    def get_client_config(self, custom_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Loads and validates client credentials JSON structure."""
        target_path = custom_path or self.credentials_path
        if not target_path:
            # Check default location in base dir
            default_path = config_manager.base_dir / "credentials.json"
            if default_path.exists():
                target_path = str(default_path)
            else:
                return None

        p = Path(target_path)
        if not p.exists():
            return None

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check standard Google OAuth 2.0 structure
            if "installed" in data or "web" in data:
                return data
            else:
                logger.warning(f"Invalid Google OAuth credentials JSON format at {target_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to read credentials file {target_path}: {e}")
            return None

    def set_credentials_file(self, file_path: str) -> bool:
        """Saves path to credentials file after validation."""
        config = self.get_client_config(file_path)
        if not config:
            raise ConfigurationError("Selected file is not a valid Google OAuth Client ID JSON file.")

        config_manager.config.credentials_path = file_path
        config_manager.save()
        self.credentials_path = file_path
        return True


credential_manager = CredentialManager()
