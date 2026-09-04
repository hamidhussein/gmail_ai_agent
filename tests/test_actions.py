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
from app.config import config_manager
from core.exceptions import GmailAPIError


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


def test_archive_failure_does_not_change_local_state(actions_demo):
    """Live-mode Gmail failures must not be reported as successful locally."""
    with (
        patch.object(config_manager.config, "demo_mode", False),
        patch.object(actions_demo, "_get_service", side_effect=GmailAPIError("offline")),
        patch("gmail.actions.repository.update_email_flags") as update_flags,
        patch("gmail.actions.repository.log_action") as log_action,
    ):
        with pytest.raises(GmailAPIError, match="offline"):
            actions_demo.archive("message-1")

    update_flags.assert_not_called()
    log_action.assert_not_called()


def test_demo_mode_allows_local_only_archive(actions_demo):
    """Explicit demo mode keeps the intentional local-only workflow available."""
    with (
        patch.object(config_manager.config, "demo_mode", True),
        patch.object(actions_demo, "_get_service", side_effect=GmailAPIError("offline")),
        patch("gmail.actions.repository.update_email_flags") as update_flags,
        patch("gmail.actions.repository.log_action") as log_action,
    ):
        assert actions_demo.archive("message-2") is True

    update_flags.assert_called_once_with("message-2", is_archived=True)
    log_action.assert_called_once()


def test_trash_alias_requires_explicit_confirmation(actions_demo):
    """The convenience API must never manufacture deletion approval."""
    with pytest.raises(SafetyViolationError):
        actions_demo.trash_message("message-3")
