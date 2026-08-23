"""
Unit Tests - Memory & Preference Learning
"""
import pytest
from database.repository import Repository
from memory.preference_engine import PreferenceEngine
from memory.learning import ActiveLearningEngine


@pytest.fixture
def memory_repo(tmp_path):
    db_file = tmp_path / "mem_test.db"
    return Repository(db_path=db_file)


def test_sender_profile_learning(memory_repo, monkeypatch):
    monkeypatch.setattr("database.repository.repository", memory_repo)

    # Record interactions
    memory_repo.record_sender_interaction(
        email="colleague@importantcorp.com",
        name="Key Colleague",
        opened=True,
        replied=True,
        is_vip=True,
    )

    prof = memory_repo.get_or_create_sender_profile("colleague@importantcorp.com")
    assert prof.is_vip is True
    assert prof.learned_importance >= 90

    # Adjust importance via preference engine
    adj_imp, adj_cat = PreferenceEngine.adjust_email_importance(
        sender_email="colleague@importantcorp.com",
        initial_importance=60,
        initial_category="WORK",
    )
    assert adj_imp >= 90
