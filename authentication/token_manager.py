"""
GmailAI Assistant - Secure Encrypted Token Manager
"""
import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import config_manager
from core.security import security_manager
from core.exceptions import TokenEncryptionError

logger = logging.getLogger("GmailAI.TokenManager")


class TokenManager:
    """Manages encrypted on-disk storage and retrieval of OAuth token dictionaries."""

    def __init__(self, tokens_dir: Optional[Path] = None):
        self.tokens_dir = tokens_dir or config_manager.tokens_dir
        self.tokens_dir.mkdir(parents=True, exist_ok=True)

    def _get_token_path(self, email: str) -> Path:
        """Derives a safe encrypted filename from the user's email."""
        email_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
        return self.tokens_dir / f"token_{email_hash}.enc"

    def save_token(self, email: str, token_data: Dict[str, Any]) -> None:
        """Encrypts and persists token data to disk."""
        token_path = self._get_token_path(email)
        try:
            raw_json = json.dumps(token_data)
            encrypted_payload = security_manager.encrypt_data(raw_json)
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(encrypted_payload)
            logger.info(f"Encrypted token saved for {email}")
        except Exception as e:
            logger.error(f"Failed to save encrypted token for {email}: {e}")
            raise TokenEncryptionError(f"Could not persist token: {e}")

    def load_token(self, email: str) -> Optional[Dict[str, Any]]:
        """Reads and decrypts token data from disk."""
        token_path = self._get_token_path(email)
        if not token_path.exists():
            return None

        try:
            with open(token_path, "r", encoding="utf-8") as f:
                encrypted_payload = f.read().strip()
            decrypted_json = security_manager.decrypt_data(encrypted_payload)
            return json.loads(decrypted_json)
        except Exception as e:
            logger.error(f"Failed to load/decrypt token for {email}: {e}")
            return None

    def delete_token(self, email: str) -> bool:
        """Deletes encrypted token on logout."""
        token_path = self._get_token_path(email)
        if token_path.exists():
            try:
                token_path.unlink()
                logger.info(f"Deleted token for {email}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete token file: {e}")
                return False
        return False


token_manager = TokenManager()
