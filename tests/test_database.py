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


def test_deactivate_account_persists(test_repo):
    test_repo.get_or_create_account("logout@test.com")
    assert test_repo.deactivate_account("logout@test.com") is True
    assert test_repo.get_active_account() is None


def test_fresh_database_has_latest_schema_version(test_repo):
    """Verify that newly initialized repository stamps schema_version table with latest version."""
    from database.migration_runner import _get_current_version, LATEST_VERSION
    current = _get_current_version(test_repo.engine)
    assert current == LATEST_VERSION


def test_migrations_are_idempotent(test_repo):
    """Verify that running migrations multiple times succeeds with no errors or duplicate changes."""
    from database.migration_runner import run_migrations, LATEST_VERSION
    v1 = run_migrations(test_repo.engine)
    v2 = run_migrations(test_repo.engine)
    assert v1 == LATEST_VERSION
    assert v2 == LATEST_VERSION


def test_unversioned_database_upgrades_cleanly(tmp_path):
    """Simulate a legacy database created before versioned migrations existed."""
    from sqlalchemy import create_engine, text
    from database.migration_runner import run_migrations, _get_current_version, LATEST_VERSION

    legacy_db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{legacy_db}")

    # Create unversioned legacy tables without schema_version
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255)
            )
        """))
        conn.execute(text("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id VARCHAR(255) UNIQUE NOT NULL,
                account_id INTEGER
            )
        """))
        conn.commit()

    # Prior to running migrations, schema_version is 0
    assert _get_current_version(engine) == 0

    # Run migrations
    result_version = run_migrations(engine)
    assert result_version == LATEST_VERSION
    assert _get_current_version(engine) == LATEST_VERSION

    # Verify column added by migration 001 exists
    from sqlalchemy import inspect
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("emails")}
    assert "risk_level" in cols
    assert "is_archived" in cols


def test_migration_preserves_existing_data(tmp_path):
    """Verify that rows existing prior to migration are not lost or altered."""
    from sqlalchemy import create_engine, text
    from database.migration_runner import run_migrations

    legacy_db = tmp_path / "preserve_data.db"
    engine = create_engine(f"sqlite:///{legacy_db}")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255)
            )
        """))
        conn.execute(text("""
            INSERT INTO accounts (email, display_name) VALUES ('existing@company.com', 'Existing User')
        """))
        conn.commit()

    # Run migrations
    run_migrations(engine)

    # Verify existing row remains intact
    with engine.connect() as conn:
        row = conn.execute(text("SELECT email, display_name FROM accounts WHERE email = 'existing@company.com'")).fetchone()
        assert row is not None
        assert row[0] == "existing@company.com"
        assert row[1] == "Existing User"


def test_pending_suggestions_are_scoped_to_account(test_repo):
    """Smart Cleanup must not mix suggestions from different Gmail accounts."""
    account_one = test_repo.get_or_create_account("one@test.com")
    account_two = test_repo.get_or_create_account("two@test.com")
    now = datetime.datetime.utcnow()

    email_one = test_repo.save_or_update_email({
        "message_id": "account-one-message",
        "account_id": account_one.id,
        "sender": "promo@one.test",
        "subject": "Account one promotion",
        "received_at": now,
    })
    email_two = test_repo.save_or_update_email({
        "message_id": "account-two-message",
        "account_id": account_two.id,
        "sender": "promo@two.test",
        "subject": "Account two promotion",
        "received_at": now,
    })
    test_repo.create_suggestion(email_one.id, "ARCHIVE", "PROMOTION", "Promo", 0.9)
    test_repo.create_suggestion(email_two.id, "ARCHIVE", "PROMOTION", "Promo", 0.9)

    account_one_items = test_repo.get_pending_suggestions(account_id=account_one.id)
    assert len(account_one_items) == 1
    assert account_one_items[0][1].message_id == "account-one-message"


def test_bulk_suggestion_status_update(test_repo):
    account = test_repo.get_or_create_account("bulk-cleanup@test.com")
    now = datetime.datetime.utcnow()
    suggestion_ids = []
    for index in range(3):
        email = test_repo.save_or_update_email({
            "message_id": f"bulk-cleanup-{index}",
            "account_id": account.id,
            "sender": "promo@test.com",
            "subject": f"Promotion {index}",
            "received_at": now,
        })
        suggestion = test_repo.create_suggestion(
            email.id, "ARCHIVE", "PROMOTION", "Promo", 0.9
        )
        suggestion_ids.append(suggestion.id)

    assert test_repo.update_suggestions_status(suggestion_ids, "REJECTED") == 3
    assert test_repo.get_pending_suggestions(account_id=account.id) == []


def test_daily_digests_are_isolated_per_account(test_repo):
    """Daily digests generated for two different accounts on the same day must not collide or overwrite."""
    account_a = test_repo.get_or_create_account("alice@corp.com")
    account_b = test_repo.get_or_create_account("bob@corp.com")
    digest_date = "2026-09-15"

    digest_a = test_repo.save_daily_digest(
        digest_date=digest_date,
        total_emails=10,
        important_count=4,
        need_reply_count=2,
        meetings_count=1,
        cleanup_suggested_count=3,
        summary_markdown="### Alice's Briefing",
        account_id=account_a.id,
    )
    digest_b = test_repo.save_daily_digest(
        digest_date=digest_date,
        total_emails=25,
        important_count=8,
        need_reply_count=5,
        meetings_count=4,
        cleanup_suggested_count=7,
        summary_markdown="### Bob's Briefing",
        account_id=account_b.id,
    )

    assert digest_a.id != digest_b.id
    assert digest_a.account_id == account_a.id
    assert digest_b.account_id == account_b.id

    fetched_a = test_repo.get_latest_daily_digest(account_id=account_a.id)
    fetched_b = test_repo.get_latest_daily_digest(account_id=account_b.id)

    assert fetched_a is not None
    assert fetched_b is not None
    assert fetched_a.total_emails == 10
    assert fetched_b.total_emails == 25
    assert "Alice" in fetched_a.summary_markdown
    assert "Bob" in fetched_b.summary_markdown


def test_audit_logs_can_filter_by_account(test_repo):
    """Audit logs can be queried globally or isolated to a specific account email."""
    test_repo.log_action(
        action_type="ARCHIVE",
        email_message_id="msg_1",
        account_email="user1@corp.com",
        subject="User 1 Newsletter",
        sender="news@test.com",
        reason="Auto-cleanup",
    )
    test_repo.log_action(
        action_type="MOVE_TRASH",
        email_message_id="msg_2",
        account_email="user2@corp.com",
        subject="User 2 Spam",
        sender="spam@test.com",
        reason="Phishing rule",
    )

    all_logs = test_repo.get_recent_audit_logs(limit=50)
    assert len(all_logs) >= 2

    user1_logs = test_repo.get_recent_audit_logs(account_email="user1@corp.com")
    assert len(user1_logs) == 1
    assert user1_logs[0].account_email == "user1@corp.com"
    assert user1_logs[0].action_type == "ARCHIVE"

    user2_logs = test_repo.get_recent_audit_logs(account_email="user2@corp.com")
    assert len(user2_logs) == 1
    assert user2_logs[0].account_email == "user2@corp.com"
    assert user2_logs[0].action_type == "MOVE_TRASH"
