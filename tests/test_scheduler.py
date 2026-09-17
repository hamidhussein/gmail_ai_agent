"""
Unit Tests - Scheduler Sync Task & AI Output Validation
"""
import pytest
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from database.repository import Repository
from ai.schemas import EmailClassificationResult
from app.constants import EmailCategory, ActionType, RiskLevel, AISource
from app.config import config_manager
from automation.scheduler import BackgroundScheduler, should_create_cleanup_suggestion
from core.events import EVT_SYNC_COMPLETED, EVT_SYNC_ERROR


@pytest.fixture
def test_repo(tmp_path):
    return Repository(db_path=tmp_path / "test_scheduler.db")


# --- AI Output Schema Validation Tests ---

def test_valid_classification_passes():
    """A well-formed AI output should pass through unchanged."""
    result = EmailClassificationResult(
        category="WORK",
        importance_score=80,
        urgency_score=60,
        risk_level="LOW",
        suggested_action="KEEP",
        confidence=0.91,
        reasoning="Internal team message.",
        action_items=["Review sprint notes"],
    )
    assert result.category == "WORK"
    assert result.importance_score == 80
    assert result.confidence == 0.91


def test_invalid_category_falls_back_to_personal():
    """An unrecognised AI-hallucinated category should default to PERSONAL."""
    result = EmailClassificationResult(category="TOTALLY_MADE_UP_CATEGORY")
    assert result.category == EmailCategory.PERSONAL.value


def test_out_of_range_score_is_clamped():
    """Scores outside 0-100 must be clamped, not cause an error."""
    result = EmailClassificationResult(importance_score=250, urgency_score=-42)
    assert result.importance_score == 100
    assert result.urgency_score == 0


def test_invalid_confidence_is_clamped():
    """Confidence outside 0.0-1.0 should be clamped."""
    result = EmailClassificationResult(confidence=99.9)
    assert result.confidence == 1.0
    result2 = EmailClassificationResult(confidence=-5.0)
    assert result2.confidence == 0.0


def test_invalid_action_falls_back_to_keep():
    """An unrecognised suggested_action should fall back to KEEP."""
    result = EmailClassificationResult(suggested_action="DO_MAGIC")
    assert result.suggested_action == ActionType.KEEP.value


def test_invalid_risk_level_falls_back_to_low():
    """An unrecognised risk_level should fall back to LOW."""
    result = EmailClassificationResult(risk_level="EXTREME")
    assert result.risk_level == RiskLevel.LOW.value


def test_action_items_non_list_coerced_to_empty():
    """Non-list action_items should be coerced to an empty list."""
    result = EmailClassificationResult(action_items="not a list")
    assert result.action_items == []


def test_to_dict_returns_correct_keys():
    """to_dict() output must contain all DB-compatible keys."""
    result = EmailClassificationResult()
    d = result.to_dict()
    required_keys = {
        "category", "importance_score", "urgency_score",
        "risk_level", "suggested_action", "confidence", "reasoning", "action_items",
    }
    assert required_keys.issubset(set(d.keys()))


# --- Scheduler Repository Interaction Tests ---

def test_update_account_synced_at(test_repo):
    """update_account_synced_at should persist without errors."""
    test_repo.get_or_create_account("scheduler@test.com")
    # Should not raise — uses its own managed session
    test_repo.update_account_synced_at("scheduler@test.com")

    acc = test_repo.get_active_account()
    assert acc.last_synced_at is not None


def test_update_sender_importance_clamped(test_repo):
    """update_sender_importance should clamp to [10, 100] range."""
    test_repo.record_sender_interaction("sender@test.com")

    # Boost beyond max
    test_repo.update_sender_importance("sender@test.com", delta=1000)
    profile = test_repo.get_or_create_sender_profile("sender@test.com")
    assert profile.learned_importance <= 100

    # Drop below min
    test_repo.update_sender_importance("sender@test.com", delta=-1000)
    profile2 = test_repo.get_or_create_sender_profile("sender@test.com")
    assert profile2.learned_importance >= 10


def test_bulk_save_emails(test_repo):
    """save_emails_batch should persist all records in one shot."""
    acc = test_repo.get_or_create_account("bulk@test.com")
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    emails = [
        {
            "message_id": f"msg_bulk_{i:03d}",
            "account_id": acc.id,
            "sender": f"sender{i}@test.com",
            "subject": f"Bulk Email {i}",
            "received_at": now,
            "is_unread": True,
        }
        for i in range(10)
    ]

    saved = test_repo.save_emails_batch(emails)
    assert saved == 10

    inbox = test_repo.get_inbox_emails()
    assert len(inbox) == 10


def test_live_sync_failure_is_reported_without_false_success():
    scheduler = BackgroundScheduler()
    account = MagicMock(id=1, email="live@test.com")

    with (
        patch.object(config_manager.config, "demo_mode", False),
        patch("automation.scheduler.repository.get_active_account", return_value=account),
        patch("automation.scheduler.repository.update_account_synced_at") as update_synced,
        patch("automation.scheduler.GmailReader") as reader_class,
        patch("automation.scheduler.event_bus.publish") as publish,
    ):
        reader_class.return_value.fetch_and_parse_inbox.side_effect = RuntimeError("network down")
        scheduler._execute_sync_task()

    update_synced.assert_not_called()
    publish.assert_any_call(EVT_SYNC_ERROR, "network down")


def test_cleanup_suggestions_respect_confidence_threshold():
    assert should_create_cleanup_suggestion("ARCHIVE", 0.85, 0.85)
    assert should_create_cleanup_suggestion("MOVE_TRASH", 0.95, 0.85)
    assert not should_create_cleanup_suggestion("ARCHIVE", 0.84, 0.85)
    assert not should_create_cleanup_suggestion("LABEL", 0.99, 0.85)


def test_sync_refreshes_classified_email_without_repeating_ai():
    scheduler = BackgroundScheduler()
    account = MagicMock(id=7, email="existing@test.com")
    existing = MagicMock(account_id=7, category="WORK", ai_source="HEURISTIC")
    email_data = {"message_id": "existing-1", "sender": "sender@test.com"}

    with (
        patch("automation.scheduler.repository.get_active_account", return_value=account),
        patch("automation.scheduler.repository.get_email_by_message_id", return_value=existing),
        patch("automation.scheduler.repository.save_or_update_email") as save_email,
        patch("automation.scheduler.repository.update_account_synced_at") as update_synced,
        patch("automation.scheduler.GmailReader") as reader_class,
        patch("automation.scheduler.hybrid_router.classify_email") as classify,
        patch("automation.scheduler.event_bus.publish") as publish,
    ):
        reader_class.return_value.fetch_and_parse_inbox.return_value = [email_data]
        result = scheduler._execute_sync_task()

    assert result.success
    assert result.refreshed == 1
    assert result.processed == 0
    assert result.failed == 0
    classify.assert_not_called()
    save_email.assert_called_once_with(email_data)
    update_synced.assert_called_once_with("existing@test.com")
    assert any(call.args[0] == EVT_SYNC_COMPLETED for call in publish.call_args_list)


def test_sync_isolates_one_bad_message_and_completes_remaining_batch():
    scheduler = BackgroundScheduler()
    account = MagicMock(id=8, email="partial@test.com")
    emails = [
        {"message_id": "bad-1", "sender": "bad@test.com"},
        {"message_id": "good-1", "sender": "good@test.com"},
    ]
    classification = {
        "category": "WORK",
        "importance_score": 75,
        "urgency_score": 60,
        "risk_level": "LOW",
        "confidence": 0.9,
        "reasoning": "Work message",
        "suggested_action": "KEEP",
        "action_items": [],
    }
    saved = MagicMock(
        suggested_action="KEEP",
        ai_confidence=0.9,
        category="WORK",
        ai_reasoning="Work message",
    )

    with (
        patch("automation.scheduler.repository.get_active_account", return_value=account),
        patch("automation.scheduler.repository.get_email_by_message_id", return_value=None),
        patch("automation.scheduler.repository.save_or_update_email", return_value=saved),
        patch("automation.scheduler.repository.update_account_synced_at") as update_synced,
        patch("automation.scheduler.GmailReader") as reader_class,
        patch(
            "automation.scheduler.hybrid_router.classify_email",
            side_effect=[RuntimeError("bad message"), (classification, AISource.HEURISTIC_FALLBACK)],
        ),
        patch(
            "automation.scheduler.preference_engine.adjust_email_importance",
            return_value=(75, "WORK"),
        ),
    ):
        reader_class.return_value.fetch_and_parse_inbox.return_value = emails
        result = scheduler._execute_sync_task()

    assert result.success
    assert result.processed == 1
    assert result.failed == 1
    update_synced.assert_called_once_with("partial@test.com")


def test_overlapping_sync_is_skipped_and_callback_is_released():
    scheduler = BackgroundScheduler()
    callback = MagicMock()
    assert scheduler._sync_lock.acquire(blocking=False)
    try:
        result = scheduler._execute_sync_task(on_complete=callback)
    finally:
        scheduler._sync_lock.release()

    assert result.skipped
    assert not result.success
    callback.assert_called_once_with()
