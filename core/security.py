"""
GmailAI Assistant - Security & Safety Engine
"""
import os
import base64
import hashlib
import platform
import logging
import secrets
from pathlib import Path
from typing import Optional, List, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.constants import (
    EmailCategory,
    ActionType,
    ProtectedCategory,
    DEFAULT_PROTECTED_DOMAINS,
)
from core.exceptions import SafetyViolationError, TokenEncryptionError

logger = logging.getLogger("GmailAI.Security")

# Location for the persistent random salt file
_SALT_FILENAME = ".salt"


def _get_config_base_dir() -> Path:
    """Resolves the application config base directory without circular imports."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "GmailAIAssistant"
    return Path.home() / ".gmailai"


class SecurityManager:
    """
    Handles token encryption/decryption using a persistent random salt.

    Key derivation strategy (priority order):
    1. Load a random 32-byte salt from ``<config_dir>/.salt`` (generated on first run).
       This ensures tokens survive machine renames, user account renames, etc.
    2. Fall back to machine-based deterministic salt only if the salt file is missing
       and cannot be created (e.g., read-only filesystem). This maintains backward
       compatibility for existing installations.

    NOTE: If the salt file is lost, all encrypted tokens become unrecoverable and
    users must re-authenticate. Keep the config directory backed up.
    """

    def __init__(self, custom_salt: Optional[bytes] = None, config_dir: Optional[Path] = None):
        if custom_salt is not None:
            # Explicit salt (for tests)
            self._salt = custom_salt
        else:
            base_dir = config_dir or _get_config_base_dir()
            self._salt = self._load_or_create_persistent_salt(base_dir)
        self._cipher = self._init_cipher()

    def _load_or_create_persistent_salt(self, base_dir: Path) -> bytes:
        """
        Loads the persistent random salt from disk.
        Creates a new 32-byte cryptographically secure salt on first run.
        Falls back to machine-based salt if the file cannot be created.
        """
        salt_path = base_dir / _SALT_FILENAME
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            if salt_path.exists():
                raw = salt_path.read_bytes()
                if len(raw) == 32:
                    logger.debug("Loaded persistent encryption salt from disk.")
                    return raw
                else:
                    logger.warning("Salt file has unexpected length; regenerating.")

            # Generate and persist a new random salt
            new_salt = secrets.token_bytes(32)
            salt_path.write_bytes(new_salt)
            # Restrict permissions on non-Windows platforms
            if os.name != "nt":
                salt_path.chmod(0o600)
            logger.info("Generated and persisted new encryption salt.")
            return new_salt

        except Exception as e:
            logger.warning(
                f"Could not load/create persistent salt file ({e}). "
                "Falling back to machine-based salt. Tokens may break if the machine changes."
            )
            return self._machine_based_salt()

    def _machine_based_salt(self) -> bytes:
        """Legacy fallback: deterministic salt derived from machine identifiers."""
        system_info = f"{platform.node()}-{platform.processor()}-{os.environ.get('USERNAME', 'user')}"
        return hashlib.sha256(system_info.encode("utf-8")).digest()

    def _init_cipher(self) -> Fernet:
        """Derives a Fernet key from the loaded salt."""
        secret_seed = f"GmailAI-Secret-{platform.machine()}-{os.environ.get('COMPUTERNAME', 'host')}"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_seed.encode("utf-8")))
        return Fernet(key)

    def encrypt_data(self, plain_text: str) -> str:
        """Encrypts a string into a base64 ciphertext string."""
        try:
            encrypted = self._cipher.encrypt(plain_text.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise TokenEncryptionError(f"Failed to encrypt data: {e}")

    def decrypt_data(self, cipher_text: str) -> str:
        """Decrypts a base64 ciphertext string back to plain text."""
        try:
            decrypted = self._cipher.decrypt(cipher_text.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise TokenEncryptionError(f"Failed to decrypt data: {e}")


class SafetyGuard:
    """Mandatory safety policy verification and guardrail enforcement."""

    def __init__(self, protected_domains: Optional[List[str]] = None):
        self.protected_domains = protected_domains or list(DEFAULT_PROTECTED_DOMAINS)

    def add_protected_domain(self, domain: str) -> None:
        """Adds a domain to the protected list."""
        clean = domain.strip().lower()
        if clean and clean not in self.protected_domains:
            self.protected_domains.append(clean)

    def is_domain_protected(self, sender_email: str) -> bool:
        """Checks if the sender email domain matches any protected domain."""
        if not sender_email or "@" not in sender_email:
            return False
        sender_domain = sender_email.split("@")[-1].strip().lower()
        for p_domain in self.protected_domains:
            if sender_domain == p_domain or sender_domain.endswith("." + p_domain):
                return True
        return False

    def is_category_protected(self, category: EmailCategory) -> bool:
        """Checks if the email category is under sensitive safety lockdown."""
        try:
            return category in [
                EmailCategory.BANK,
                EmailCategory.FINANCE,
                EmailCategory.LEGAL,
                EmailCategory.WORK,
            ]
        except Exception:
            return False

    def validate_action(
        self,
        action: ActionType,
        category: EmailCategory,
        sender_email: str,
        user_explicit_approval: bool,
        double_confirmed: bool = False,
    ) -> Tuple[bool, str]:
        """
        Validates if an action is allowed according to the safety rules.
        Returns (is_allowed, reason).
        Raises SafetyViolationError if strict violation.
        """
        # Rule 1: Permanent deletion / Trash is NEVER automatic
        if action == ActionType.MOVE_TRASH:
            if not user_explicit_approval:
                raise SafetyViolationError(
                    "Safety Rule: Deletion/Trash is NEVER automatic and requires user approval."
                )
            if not double_confirmed:
                raise SafetyViolationError(
                    "Safety Rule: Deletion requires double verification confirmation."
                )

        # Rule 2: Protected domains (Banking, Legal, Medical, Gov) cannot be deleted or auto-archived
        is_prot_domain = self.is_domain_protected(sender_email)
        is_prot_cat = self.is_category_protected(category)

        if is_prot_domain or is_prot_cat:
            if action == ActionType.MOVE_TRASH:
                if not (user_explicit_approval and double_confirmed):
                    raise SafetyViolationError(
                        f"Safety Rule: Protected entity ({sender_email} / {category}) cannot be moved to trash without double confirmation."
                    )
            elif action == ActionType.ARCHIVE and not user_explicit_approval:
                raise SafetyViolationError(
                    f"Safety Rule: Protected entity ({sender_email} / {category}) cannot be auto-archived without approval."
                )

        return True, "Action approved by safety policy."


# Global security instances
security_manager = SecurityManager()
safety_guard = SafetyGuard()
