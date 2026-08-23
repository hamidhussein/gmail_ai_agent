"""
Unit Tests - SQLite Repository & Models
"""
import pytest
import datetime
from pathlib import Path
from database.repository import Repository
from app.constants import EmailCategory, ActionType, SuggestionStatus


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "test_gmailai.db"
    repo = Repository(db_path=db_file)
    return repo


def test_account_creation(test_repo):
    acc = test_repo.get_or_create_account(email="test@user.com", display_name="Test User")
    assert acc.id is not None
    assert acc.email == "test@user.com"

    active = test_repo.get_active_account()
    assert active.email == "test@user.com"


def test_email_crud_and_stats(test_repo):
    acc = test_repo.get_or_create_account(email="test@user.com")
    now = datetime.datetime.utcnow()

    email_data = {
        "message_id": "msg_test_101",
        "thread_id": "th_101",
        "account_id": acc.id,
        "sender": "client@enterprise.com",
        "sender_name": "Client Representative",
        "recipient": "test@user.com",
        "subject": "Q3 Contract Quotation",
        "snippet": "Please review quote.",
        "body_plain": "Please review quote.",
        "received_at": now,
        "is_unread": True,
        "category": EmailCategory.CLIENT.value,
        "importance_score": 90,
        "urgency_score": 80,
        "suggested_action": ActionType.DRAFT_REPLY.value,
    }

    saved = test_repo.save_or_update_email(email_data)
    assert saved.id is not None
    assert saved.message_id == "msg_test_101"

    # Query
    inbox = test_repo.get_inbox_emails(category=EmailCategory.CLIENT.value)
    assert len(inbox) == 1
    assert inbox[0].subject == "Q3 Contract Quotation"

    # Stats
    stats = test_repo.get_inbox_stats()
    assert stats["total_emails"] == 1
    assert stats["unread_emails"] == 1
    assert stats["important_emails"] == 1


def test_cleanup_suggestions(test_repo):
    acc = test_repo.get_or_create_account(email="test@user.com")
    saved = test_repo.save_or_update_email({
        "message_id": "msg_news_102",
        "account_id": acc.id,
        "sender": "newsletter@domain.com",
        "subject": "Daily Digest",
        "received_at": datetime.datetime.utcnow(),
        "is_unread": True,
        "category": EmailCategory.NEWSLETTER.value,
    })

    sugg = test_repo.create_suggestion(
        email_id=saved.id,
        action_type=ActionType.ARCHIVE.value,
        category=EmailCategory.NEWSLETTER.value,
        reason="Daily newsletter",
        confidence=0.95,
    )
    assert sugg.id is not None
    assert sugg.status == SuggestionStatus.PENDING.value

    pending = test_repo.get_pending_suggestions()
    assert len(pending) == 1
    assert pending[0][0].id == sugg.id
