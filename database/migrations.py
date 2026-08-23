"""
GmailAI Assistant - Database Migrations & Demo Seeder
"""
import datetime
import json
import logging
from typing import List, Dict, Any

from database.repository import repository
from database.models import Base
from app.constants import EmailCategory, ActionType, RiskLevel, AISource

logger = logging.getLogger("GmailAI.Migrations")


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def seed_demo_data() -> None:
    """Seeds the database with realistic sample emails and suggestions for demo & testing."""
    # Ensure active account
    account = repository.get_or_create_account(
        email="alex.mercer@gmail.com", display_name="Alex Mercer"
    )
    repository.set_active_account("alex.mercer@gmail.com")

    # Sample emails spanning different realistic categories
    now = _utcnow()
    sample_emails: List[Dict[str, Any]] = [
        {
            "message_id": "msg_001_client_quotation",
            "thread_id": "th_001",
            "account_id": account.id,
            "sender": "sarah.jenkins@acmecorp.com",
            "sender_name": "Sarah Jenkins",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Urgent: Project Titan Q3 Quotation & SOW Update",
            "snippet": "Hi Alex, we urgently need the updated Q3 Statement of Work and quotation for the enterprise AI integration before the board meeting tomorrow...",
            "body_plain": "Hi Alex,\n\nWe urgently need the updated Q3 Statement of Work and quotation for the enterprise AI integration before the board meeting tomorrow at 10 AM EST.\n\nCould you please review the attached milestones and confirm if the delivery timeline is still on track?\n\nBest regards,\nSarah Jenkins\nVP Operations, Acme Corp",
            "received_at": now - datetime.timedelta(hours=2),
            "is_unread": True,
            "is_starred": True,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.CLIENT.value,
            "importance_score": 95,
            "urgency_score": 92,
            "risk_level": RiskLevel.LOW.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.94,
            "ai_reasoning": "High-priority client requesting urgent quotation and SOW confirmation before tomorrow's board meeting.",
            "suggested_action": ActionType.DRAFT_REPLY.value,
            "action_items_json": json.dumps(["Review attached milestones", "Send updated Q3 quotation by 10 AM tomorrow"]),
            "has_attachments": True,
            "attachments_json": json.dumps([{"filename": "Project_Titan_SOW_Draft.pdf", "size_kb": 340}]),
        },
        {
            "message_id": "msg_002_bank_statement",
            "thread_id": "th_002",
            "account_id": account.id,
            "sender": "notifications@chase.com",
            "sender_name": "Chase Bank",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Your Monthly Commercial Checking Statement is Ready",
            "snippet": "Dear Alex Mercer, Your monthly statement ending in ...4821 for the period ending August 2026 is now available online...",
            "body_plain": "Dear Alex Mercer,\n\nYour monthly statement ending in ...4821 for the period ending August 2026 is now available to download in Chase Online.\n\nLog in securely to view full transactions.",
            "received_at": now - datetime.timedelta(hours=5),
            "is_unread": True,
            "is_starred": False,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.BANK.value,
            "importance_score": 85,
            "urgency_score": 30,
            "risk_level": RiskLevel.HIGH.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.98,
            "ai_reasoning": "Financial banking statement from verified banking domain chase.com. Protected domain.",
            "suggested_action": ActionType.LABEL.value,
            "action_items_json": json.dumps(["Review monthly transactions"]),
            "has_attachments": False,
            "attachments_json": json.dumps([]),
        },
        {
            "message_id": "msg_003_newsletter_cleanup",
            "thread_id": "th_003",
            "account_id": account.id,
            "sender": "digest@morningbrew.com",
            "sender_name": "Morning Brew",
            "recipient": "alex.mercer@gmail.com",
            "subject": "The latest in AI hardware wars & market breakdown",
            "snippet": "Grab your coffee. Today's top stories: Silicon giants reveal next-gen chip architectures and quarterly earnings...",
            "body_plain": "Grab your coffee. Today's top stories: Silicon giants reveal next-gen chip architectures, electric mobility trends, and our weekly markets wrap up.",
            "received_at": now - datetime.timedelta(days=2),
            "is_unread": True,
            "is_starred": False,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.NEWSLETTER.value,
            "importance_score": 25,
            "urgency_score": 10,
            "risk_level": RiskLevel.LOW.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.96,
            "ai_reasoning": "Recurring mass newsletter with no direct user action needed. Safe for automated archiving.",
            "suggested_action": ActionType.ARCHIVE.value,
            "action_items_json": json.dumps([]),
            "has_attachments": False,
            "attachments_json": json.dumps([]),
        },
        {
            "message_id": "msg_004_promo_cleanup",
            "thread_id": "th_004",
            "account_id": account.id,
            "sender": "offers@cloudservices-promo.com",
            "sender_name": "CloudServices Hub",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Limited 50% Cloud GPU Credit Sale Ends Tonight!",
            "snippet": "Upgrade your compute cluster today. Claim exclusive promotional discounts for high-performance clusters...",
            "body_plain": "Upgrade your compute cluster today! Claim exclusive promotional discounts for high-performance clusters before midnight.",
            "received_at": now - datetime.timedelta(days=5),
            "is_unread": True,
            "is_starred": False,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.PROMOTION.value,
            "importance_score": 15,
            "urgency_score": 20,
            "risk_level": RiskLevel.LOW.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.92,
            "ai_reasoning": "Promotional marketing advertisement with time-limited discount.",
            "suggested_action": ActionType.ARCHIVE.value,
            "action_items_json": json.dumps([]),
            "has_attachments": False,
            "attachments_json": json.dumps([]),
        },
        {
            "message_id": "msg_005_legal_nda",
            "thread_id": "th_005",
            "account_id": account.id,
            "sender": "counsel@techlawpartners.com",
            "sender_name": "Elena Vance, Esq.",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Confidentiality Agreement & Patent Assignment Review",
            "snippet": "Alex, please find attached the revised Mutual NDA and intellectual property assignment agreement for your signature...",
            "body_plain": "Alex,\n\nPlease find attached the revised Mutual Non-Disclosure Agreement and IP assignment contract. Please review Section 4 regarding indemnification and sign via DocuSign.",
            "received_at": now - datetime.timedelta(hours=14),
            "is_unread": True,
            "is_starred": True,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.LEGAL.value,
            "importance_score": 90,
            "urgency_score": 75,
            "risk_level": RiskLevel.MEDIUM.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.95,
            "ai_reasoning": "Confidential legal contract and NDA requiring signature. High importance and protected legal category.",
            "suggested_action": ActionType.KEEP.value,
            "action_items_json": json.dumps(["Review Section 4 indemnification clause", "Sign via DocuSign"]),
            "has_attachments": True,
            "attachments_json": json.dumps([{"filename": "Mutual_NDA_Revised.pdf", "size_kb": 512}]),
        },
        {
            "message_id": "msg_006_work_standup",
            "thread_id": "th_006",
            "account_id": account.id,
            "sender": "marcus.lead@mycompany.internal",
            "sender_name": "Marcus Vance",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Sprint 42 Architecture Review - Meeting Notes & Action Items",
            "snippet": "Team, here are the key takeaways from today's engineering sync: API latency benchmarks, database indexing, and rollout schedule...",
            "body_plain": "Team,\n\nHere are the key takeaways from today's sprint sync:\n1. Alex to finalize hybrid AI fallback pipeline\n2. Database indexing complete\n3. Release candidate testing begins Thursday.",
            "received_at": now - datetime.timedelta(hours=6),
            "is_unread": False,
            "is_starred": False,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.WORK.value,
            "importance_score": 82,
            "urgency_score": 60,
            "risk_level": RiskLevel.LOW.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.91,
            "ai_reasoning": "Internal work sprint notes with action items assigned to user.",
            "suggested_action": ActionType.KEEP.value,
            "action_items_json": json.dumps(["Finalize hybrid AI fallback pipeline", "Participate in RC testing Thursday"]),
            "has_attachments": False,
            "attachments_json": json.dumps([]),
        },
        {
            "message_id": "msg_007_spam_phishing",
            "thread_id": "th_007",
            "account_id": account.id,
            "sender": "security-alert@verify-account-urgent-now.xyz",
            "sender_name": "Account Security Team",
            "recipient": "alex.mercer@gmail.com",
            "subject": "Immediate Action Required: Your account has been suspended!",
            "snippet": "We detected unauthorized access to your portal. Click here to verify your identity immediately or your data will be deleted...",
            "body_plain": "We detected unauthorized access to your account. Click the link below to verify your password immediately or all services will be suspended within 24 hours.",
            "received_at": now - datetime.timedelta(days=1),
            "is_unread": True,
            "is_starred": False,
            "is_trash": False,
            "is_archived": False,
            "category": EmailCategory.SPAM.value,
            "importance_score": 5,
            "urgency_score": 10,
            "risk_level": RiskLevel.CRITICAL.value,
            "ai_source": AISource.LOCAL_OLLAMA.value,
            "ai_confidence": 0.99,
            "ai_reasoning": "High-risk suspicious phishing attempt. Suspicious sender domain and spoofed security warning.",
            "suggested_action": ActionType.MOVE_TRASH.value,
            "action_items_json": json.dumps([]),
            "has_attachments": False,
            "attachments_json": json.dumps([]),
        },
    ]

    for item in sample_emails:
        saved_rec = repository.save_or_update_email(item)
        # Create cleanup suggestions for promotional/newsletter/spam
        if saved_rec.category in [EmailCategory.NEWSLETTER.value, EmailCategory.PROMOTION.value, EmailCategory.SPAM.value]:
            action = ActionType.MOVE_TRASH.value if saved_rec.category == EmailCategory.SPAM.value else ActionType.ARCHIVE.value
            repository.create_suggestion(
                email_id=saved_rec.id,
                action_type=action,
                category=saved_rec.category,
                reason=saved_rec.ai_reasoning,
                confidence=saved_rec.ai_confidence,
            )

    # Seed sender profiles
    repository.record_sender_interaction("sarah.jenkins@acmecorp.com", name="Sarah Jenkins", opened=True, replied=True, is_vip=True)
    repository.record_sender_interaction("notifications@chase.com", name="Chase Bank", opened=True, is_vip=True)
    repository.record_sender_interaction("marcus.lead@mycompany.internal", name="Marcus Vance", opened=True, replied=True, is_vip=True)
    repository.record_sender_interaction("digest@morningbrew.com", name="Morning Brew", opened=False)

    # Seed an initial Daily Digest
    repository.save_daily_digest(
        digest_date=now.strftime("%Y-%m-%d"),
        total_emails=7,
        important_count=4,
        need_reply_count=1,
        meetings_count=2,
        cleanup_suggested_count=3,
        summary_markdown=(
            "### Good Morning Alex,\n\n"
            "Here is your AI Inbox Briefing:\n\n"
            "* **High Priority Client**: Sarah Jenkins sent an urgent request regarding the Q3 Statement of Work and quotation before tomorrow's 10 AM board meeting.\n"
            "* **Legal & Contracts**: Elena Vance delivered the revised Mutual NDA & IP assignment agreement for signature.\n"
            "* **Finance & Banking**: Chase Bank monthly commercial checking statement is ready for review.\n"
            "* **Cleanup Opportunities**: 3 low-priority promotional, newsletter, and suspicious messages detected and queued for one-click review."
        ),
        stats_json=json.dumps({"efficiency_score": 96, "noise_reduction": "43%"}),
    )

    logger.info("Demo data successfully seeded.")
