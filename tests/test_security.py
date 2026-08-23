"""
Unit Tests - Security & Encryption Manager
"""
import pytest
from core.security import SecurityManager, SafetyGuard
from core.exceptions import SafetyViolationError
from app.constants import ActionType, EmailCategory


def test_encryption_decryption():
    manager = SecurityManager()
    plain_token = "ya29.a0AfH6SMB_secret_oauth_token_123456789"
    encrypted = manager.encrypt_data(plain_token)
    assert encrypted != plain_token
    decrypted = manager.decrypt_data(encrypted)
    assert decrypted == plain_token


def test_safety_guard_protected_domains():
    guard = SafetyGuard(protected_domains=["chase.com", "gov", "bank.com"])
    assert guard.is_domain_protected("alerts@chase.com") is True
    assert guard.is_domain_protected("support@sub.bank.com") is True
    assert guard.is_domain_protected("newsletter@morningbrew.com") is False


def test_safety_guard_delete_requires_double_confirmation():
    guard = SafetyGuard()

    # Deletion without user approval raises SafetyViolationError
    with pytest.raises(SafetyViolationError):
        guard.validate_action(
            action=ActionType.MOVE_TRASH,
            category=EmailCategory.SPAM,
            sender_email="spam@random.com",
            user_explicit_approval=False,
            double_confirmed=False,
        )

    # Deletion without double confirmation raises SafetyViolationError
    with pytest.raises(SafetyViolationError):
        guard.validate_action(
            action=ActionType.MOVE_TRASH,
            category=EmailCategory.SPAM,
            sender_email="spam@random.com",
            user_explicit_approval=True,
            double_confirmed=False,
        )

    # Deletion with both approvals passes
    allowed, _ = guard.validate_action(
        action=ActionType.MOVE_TRASH,
        category=EmailCategory.SPAM,
        sender_email="spam@random.com",
        user_explicit_approval=True,
        double_confirmed=True,
    )
    assert allowed is True
