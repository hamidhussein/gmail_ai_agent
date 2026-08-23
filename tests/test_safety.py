"""
Unit Tests - Safety Guardrails & Policy Enforcement
"""
import pytest
from core.security import SafetyGuard
from core.exceptions import SafetyViolationError
from app.constants import ActionType, EmailCategory


def test_protected_category_prevent_archive_without_approval():
    guard = SafetyGuard()
    
    # Banking category cannot be auto-archived without approval
    with pytest.raises(SafetyViolationError):
        guard.validate_action(
            action=ActionType.ARCHIVE,
            category=EmailCategory.BANK,
            sender_email="alerts@chase.com",
            user_explicit_approval=False,
        )

    # Approved archive passes
    allowed, _ = guard.validate_action(
        action=ActionType.ARCHIVE,
        category=EmailCategory.BANK,
        sender_email="alerts@chase.com",
        user_explicit_approval=True,
    )
    assert allowed is True


def test_legal_category_protection():
    guard = SafetyGuard()
    assert guard.is_category_protected(EmailCategory.LEGAL) is True
    assert guard.is_category_protected(EmailCategory.BANK) is True
    assert guard.is_category_protected(EmailCategory.NEWSLETTER) is False
