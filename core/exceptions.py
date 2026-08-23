"""
GmailAI Assistant - Custom Exception Hierarchy
"""


class GmailAIException(Exception):
    """Base exception for all GmailAI Assistant errors."""
    pass


class AuthenticationError(GmailAIException):
    """Raised when authentication or OAuth flow fails."""
    pass


class TokenEncryptionError(GmailAIException):
    """Raised when encrypting or decrypting tokens fails."""
    pass


class GmailAPIError(GmailAIException):
    """Raised when Gmail API requests fail or exceed quota."""
    pass


class AIModelError(GmailAIException):
    """Base exception for AI reasoning / routing failures."""
    pass


class LocalModelUnavailableError(AIModelError):
    """Raised when local Ollama service is unreachable or model is missing."""
    pass


class CloudModelError(AIModelError):
    """Raised when cloud OpenAI API calls fail."""
    pass


class SafetyViolationError(GmailAIException):
    """Raised when an operation violates mandatory safety rules."""
    pass


class DatabaseError(GmailAIException):
    """Raised on database query or connection failure."""
    pass


class ConfigurationError(GmailAIException):
    """Raised on missing or invalid configuration."""
    pass
