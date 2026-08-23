"""
Unit Tests - Email Classifier & Heuristic Rule Engine
"""
import pytest
from ai.classifier import EmailClassifier
from app.constants import EmailCategory, ActionType, RiskLevel


def test_classify_phishing_spam():
    email = {
        "sender": "security@unauthorized-bank-now.xyz",
        "subject": "Immediate action required: verify your password immediately",
        "body_plain": "Your account was compromised. Click here to confirm your identity immediately.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.SPAM.value
    assert result["risk_level"] == RiskLevel.CRITICAL.value
    assert result["suggested_action"] == ActionType.MOVE_TRASH.value


def test_classify_bank_statement():
    email = {
        "sender": "alerts@chase.com",
        "subject": "Your monthly checking statement is ready",
        "body_plain": "Your statement for August 2026 is now available online.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.BANK.value
    assert result["importance_score"] >= 80


def test_classify_newsletter():
    email = {
        "sender": "digest@morningbrew.com",
        "subject": "Daily Newsletter Roundup",
        "body_plain": "Today's top tech stories and stock market digest. Unsubscribe here.",
        "is_newsletter_header": True,
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.NEWSLETTER.value
    assert result["suggested_action"] == ActionType.ARCHIVE.value


def test_classify_client_quotation():
    email = {
        "sender": "sarah@acme.com",
        "subject": "Urgent: Project quotation and SOW needed",
        "body_plain": "Please send the updated statement of work and quotation before tomorrow.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.CLIENT.value
    assert result["importance_score"] >= 90
    assert result["suggested_action"] == ActionType.DRAFT_REPLY.value
