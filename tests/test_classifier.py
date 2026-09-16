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


def test_known_bank_security_alert_is_kept_not_trashed():
    email = {
        "sender": "Chase Alerts <security@alerts.chase.com>",
        "subject": "Security alert: unrecognized sign-in",
        "body_plain": "We detected a new login. Please review your account activity.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.BANK.value
    assert result["suggested_action"] == ActionType.KEEP.value
    assert result["risk_level"] == RiskLevel.HIGH.value


def test_lookalike_bank_domain_does_not_match_trusted_domain():
    email = {
        "sender": "security@chase.com.attacker.example",
        "subject": "Verify your password immediately",
        "body_plain": "Your account has been suspended. Click here to unlock it.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.SPAM.value
    assert result["suggested_action"] == ActionType.MOVE_TRASH.value


def test_urgent_personal_request_is_not_assumed_to_be_client_work():
    email = {
        "sender": "friend@example.com",
        "subject": "Urgent: are you available tomorrow?",
        "body_plain": "Let me know whether you can join us tomorrow.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.PERSONAL.value
    assert result["suggested_action"] == ActionType.DRAFT_REPLY.value
    assert result["urgency_score"] >= 70


def test_work_request_extracts_action_item_and_requests_reply():
    email = {
        "sender": "lead@company.example",
        "subject": "Sprint planning",
        "body_plain": "Please review the sprint backlog before tomorrow. We will discuss it in standup.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.WORK.value
    assert result["suggested_action"] == ActionType.DRAFT_REPLY.value
    assert result["action_items"] == ["Please review the sprint backlog before tomorrow."]


def test_commerce_sale_is_promotion_not_receipt():
    email = {
        "sender": "Amazon Deals <offers@amazon.com>",
        "subject": "Limited time: 40% off",
        "body_plain": "Shop now and use this promo code.",
    }
    result = EmailClassifier.classify_with_heuristics(email)
    assert result["category"] == EmailCategory.PROMOTION.value
    assert result["suggested_action"] == ActionType.ARCHIVE.value
