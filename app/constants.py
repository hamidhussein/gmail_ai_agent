"""
GmailAI Assistant - Constants & Enums
"""
from enum import Enum


class EmailCategory(str, Enum):
    PERSONAL = "PERSONAL"
    WORK = "WORK"
    CLIENT = "CLIENT"
    FINANCE = "FINANCE"
    BANK = "BANK"
    LEGAL = "LEGAL"
    NEWSLETTER = "NEWSLETTER"
    PROMOTION = "PROMOTION"
    SOCIAL = "SOCIAL"
    ADVERTISEMENT = "ADVERTISEMENT"
    SPAM = "SPAM"


class ActionType(str, Enum):
    ARCHIVE = "ARCHIVE"
    LABEL = "LABEL"
    MARK_READ = "MARK_READ"
    STAR = "STAR"
    MOVE_TRASH = "MOVE_TRASH"
    DRAFT_REPLY = "DRAFT_REPLY"
    KEEP = "KEEP"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AISource(str, Enum):
    LOCAL_OLLAMA = "LOCAL_OLLAMA"
    CLOUD_OPENAI = "CLOUD_OPENAI"
    HEURISTIC_FALLBACK = "HEURISTIC_FALLBACK"


class ReplyTone(str, Enum):
    PROFESSIONAL = "PROFESSIONAL"
    FRIENDLY = "FRIENDLY"
    SHORT = "SHORT"
    DETAILED = "DETAILED"
    APOLOGY = "APOLOGY"
    FOLLOW_UP = "FOLLOW_UP"


class SuggestionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class ProtectedCategory(str, Enum):
    BANK = "BANK"
    FINANCE = "FINANCE"
    LEGAL = "LEGAL"
    GOVERNMENT = "GOVERNMENT"
    MEDICAL = "MEDICAL"
    WORK = "WORK"


# Standard Category Colors for UI
CATEGORY_COLORS = {
    EmailCategory.PERSONAL: "#3B82F6",       # Bright Blue
    EmailCategory.WORK: "#2563EB",           # Sapphire Blue
    EmailCategory.CLIENT: "#0D9488",         # Executive Teal
    EmailCategory.FINANCE: "#10B981",        # Emerald Green
    EmailCategory.BANK: "#059669",           # Dark Emerald Green
    EmailCategory.LEGAL: "#D97706",          # Amber
    EmailCategory.NEWSLETTER: "#06B6D4",     # Cyan
    EmailCategory.PROMOTION: "#F59E0B",      # Orange
    EmailCategory.SOCIAL: "#EC4899",         # Pink
    EmailCategory.ADVERTISEMENT: "#94A3B8",  # Slate
    EmailCategory.SPAM: "#EF4444",           # Red
}

# Protected Domains (Hardcoded default protection rules)
DEFAULT_PROTECTED_DOMAINS = [
    "chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com",
    "irs.gov", "ssa.gov", "gov", "mil", "docusign.net",
    "healthcare.gov", "mychart.com", "paypal.com", "stripe.com"
]
