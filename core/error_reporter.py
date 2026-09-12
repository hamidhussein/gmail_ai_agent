"""
GmailAI Assistant - Structured Error Reporting

Sanitises exception messages before they reach the UI or general log files,
stripping email bodies, sender addresses, credential paths, and OAuth tokens.
The full-detail messages are preserved only in the audit log.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger("GmailAI.ErrorReporter")

# Patterns that should be redacted from user-facing error messages
_REDACT_PATTERNS = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "<email>"),
    # File paths (Windows and Unix)
    (re.compile(r"[A-Za-z]:\\[^\s\"']+|/(?:home|tmp|Users|var|etc)/[^\s\"']+"), "<path>"),
    # OAuth tokens and API keys (long base64-ish strings)
    (re.compile(r"(ya29\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,})"), "<token>"),
    # Quoted email subjects or bodies (anything in single or double quotes over 40 chars)
    (re.compile(r"['\"][^'\"]{40,}['\"]"), "'<content>'"),
]


def sanitize_error(error: Exception, context: str = "") -> str:
    """
    Returns a redacted version of an exception message safe for
    user-facing display and general log files.

    Args:
        error: The exception to sanitise.
        context: Optional context string (e.g. 'archive', 'bulk_approve').

    Returns:
        A string with sensitive data replaced by placeholder tokens.
    """
    raw = str(error)
    sanitized = raw
    for pattern, replacement in _REDACT_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    if context:
        return f"[{context}] {sanitized}"
    return sanitized


def format_user_error(error: Exception, action: str = "operation") -> str:
    """
    Returns a concise, user-friendly error message suitable for
    SnackBars and toast notifications.

    Does not expose internal details — just the action that failed
    and a generic suggestion.
    """
    err_type = type(error).__name__

    # Map known exception types to friendly messages
    friendly_map = {
        "GmailAPIError": f"Gmail could not complete the {action}. Check your connection and try again.",
        "SafetyViolationError": f"The {action} was blocked by a safety rule. Review the safety settings.",
        "AuthenticationError": f"Authentication required. Please sign in again.",
        "TokenEncryptionError": f"There was a security error. Please re-authenticate.",
        "ConnectionError": f"Could not reach the server for {action}. Check your internet connection.",
        "TimeoutError": f"The {action} timed out. Please try again.",
    }

    if err_type in friendly_map:
        return friendly_map[err_type]

    # Generic fallback — still no raw content
    return f"Could not complete {action}. Please try again or check logs for details."


class BulkOperationResult:
    """Tracks partial progress for bulk operations like batch approve/dismiss."""

    def __init__(self):
        self.succeeded_ids: list = []
        self.failed_ids: list = []
        self.errors: list = []  # list of (id, sanitized_error_string)

    @property
    def total(self) -> int:
        return len(self.succeeded_ids) + len(self.failed_ids)

    @property
    def success_count(self) -> int:
        return len(self.succeeded_ids)

    @property
    def failure_count(self) -> int:
        return len(self.failed_ids)

    @property
    def has_failures(self) -> bool:
        return len(self.failed_ids) > 0

    @property
    def all_succeeded(self) -> bool:
        return len(self.failed_ids) == 0 and len(self.succeeded_ids) > 0

    def record_success(self, item_id) -> None:
        self.succeeded_ids.append(item_id)

    def record_failure(self, item_id, error: Exception) -> None:
        self.failed_ids.append(item_id)
        self.errors.append((item_id, sanitize_error(error, "bulk_operation")))

    def summary_message(self, action: str = "cleaned") -> str:
        """Returns a user-friendly summary string for SnackBar display."""
        if self.all_succeeded:
            return f"Successfully {action} {self.success_count} email{'s' if self.success_count != 1 else ''}!"
        elif self.success_count == 0:
            return f"Could not {action.rstrip('ed').rstrip('d')} any emails. Check your connection."
        else:
            return (
                f"{action.capitalize()} {self.success_count}/{self.total} emails. "
                f"{self.failure_count} failed — you can retry."
            )
