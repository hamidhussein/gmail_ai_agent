"""
Unit Tests - Gmail Actions Safety Guard Integration
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from database.repository import Repository
from gmail.actions import GmailActions
from core.exceptions import SafetyViolationError
from app.constants import ActionType, EmailCategory


@pytest.fixture
def test_repo(tmp_path):
    return Repository(db_path=tmp_path / "test_actions.db")


@pytest.fixture
def actions_demo():
    """GmailActions instance with no real Gmail service (demo/offline mode)."""
    return GmailActions(account_email="test@demo.com")


def test_archive_protected_domain_without_approval_raises(actions_demo):
    """Archiving from a protected domain without explicit approval raises SafetyViolationError."""
    from core.security import SafetyGuard
    guard = SafetyGuard(protected_domains=["chase.com"])

    with pytest.raises(SafetyViolationError):
        guard.validate_action(
            action=ActionType.ARCHIVE,
            category=EmailCategory.BANK,
            sender_email="notifications@chase.com",
            user_explicit_approval=False,
        )


def test_trash_without_double_confirmation_raises():
    """Moving to trash requires both user_explicit_approval=True and double_confirmed=True."""
    from core.security import SafetyGuard
    guard = SafetyGuard()

    # Only user_approved=True but not double_confirmed -> raises
    with pytest.raises(SafetyViolationError, match="double verification"):
        guard.validate_action(
            action=ActionType.MOVE_TRASH,
            category=EmailCategory.SPAM,
            sender_email="spam@evil.xyz",
            user_explicit_approval=True,
            double_confirmed=False,
        )


def test_trash_with_full_confirmation_passes():
    """Both approvals provided -> action is allowed."""
    from core.security import SafetyGuard
    guard = SafetyGuard()
    allowed, reason = guard.validate_action(
        action=ActionType.MOVE_TRASH,
        category=EmailCategory.SPAM,
        sender_email="spam@evil.xyz",
        user_explicit_approval=True,
        double_confirmed=True,
    )
    assert allowed is True
    assert "approved" in reason.lower()


def test_update_email_flags_safe_session(test_repo):
    """update_email_flags should update DB flags without leaking sessions."""
    import datetime
    acc = test_repo.get_or_create_account(email="flag@test.com")
    test_repo.save_or_update_email({
        "message_id": "msg_flag_01",
        "account_id": acc.id,
        "sender": "sender@test.com",
        "subject": "Flag Test",
        "received_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        "is_unread": True,
    })

    test_repo.update_email_flags("msg_flag_01", is_unread=False, is_archived=True)

    record = test_repo.get_email_by_message_id("msg_flag_01")
    assert record.is_unread is False
    assert record.is_archived is True
