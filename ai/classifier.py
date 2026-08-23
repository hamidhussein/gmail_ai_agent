"""
GmailAI Assistant - Email Intelligence Classifier & Rule Engine
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional
from app.constants import (
    EmailCategory,
    ActionType,
    RiskLevel,
    DEFAULT_PROTECTED_DOMAINS,
)

logger = logging.getLogger("GmailAI.Classifier")

CLASSIFICATION_SYSTEM_PROMPT = """You are GmailAI Intelligence Engine, a commercial-grade email classification and analysis assistant.
Analyze the given email and return ONLY a valid JSON object with the following schema:
{
  "category": "PERSONAL | WORK | CLIENT | FINANCE | BANK | LEGAL | NEWSLETTER | PROMOTION | SOCIAL | ADVERTISEMENT | SPAM",
  "importance_score": <integer 0-100>,
  "urgency_score": <integer 0-100>,
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "suggested_action": "ARCHIVE | LABEL | MARK_READ | STAR | MOVE_TRASH | DRAFT_REPLY | KEEP",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<concise explanation of why this category and action were chosen>",
  "action_items": ["<to-do item 1>", "<to-do item 2>"]
}

Guidelines:
1. Category 'BANK'/'FINANCE': statements, banking notices, invoices, tax documents.
2. Category 'LEGAL': contracts, NDAs, patent docs, attorney communications, DocuSign requests.
3. Category 'CLIENT': client inquiries, proposals, deliverables, invoices to/from clients.
4. Category 'WORK': internal team communications, sprints, architecture, manager notes.
5. Category 'NEWSLETTER': recurring digest emails, blogs, industry news (suggest ARCHIVE if not actionable).
6. Category 'PROMOTION'/'ADVERTISEMENT': discounts, sales offers, marketing promos (suggest ARCHIVE).
7. Category 'SPAM': unsolicited junk, phishing, scam attempts (suggest MOVE_TRASH, risk HIGH/CRITICAL).
8. If an email explicitly requires a user reply or decision, suggest 'DRAFT_REPLY'.
"""


class EmailClassifier:
    """Classifies emails using AI prompts with a comprehensive rule-based heuristic fallback."""

    @staticmethod
    def build_classification_prompt(email_data: Dict[str, Any]) -> str:
        """Constructs prompt for AI models."""
        return f"""Analyze this email:
Sender: {email_data.get('sender_name', '')} <{email_data.get('sender', '')}>
Recipient: {email_data.get('recipient', '')}
Subject: {email_data.get('subject', '')}
Date: {email_data.get('received_at', '')}
Has Attachments: {email_data.get('has_attachments', False)}

Body:
{email_data.get('body_plain', '')[:3000]}
"""

    @classmethod
    def classify_with_heuristics(cls, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fast, offline rule-based heuristic classification.
        Guarantees resilient zero-crash fallback if no AI is available.
        """
        sender = (email_data.get("sender") or "").lower()
        sender_name = (email_data.get("sender_name") or "").lower()
        subject = (email_data.get("subject") or "").lower()
        body = (email_data.get("body_plain") or "").lower()
        is_newsletter_header = email_data.get("is_newsletter_header", False)
        text_corpus = f"{subject} {body} {sender}"

        # 1. SPAM / Phishing check
        spam_signals = [
            "verify your password", "account suspended", "unauthorized access detected",
            "confirm your identity immediately", "wire transfer urgently", "crypto giveaway",
            "winner of", "claim your prize", "click here to unlock"
        ]
        if any(sig in text_corpus for sig in spam_signals):
            return {
                "category": EmailCategory.SPAM.value,
                "importance_score": 5,
                "urgency_score": 10,
                "risk_level": RiskLevel.CRITICAL.value,
                "suggested_action": ActionType.MOVE_TRASH.value,
                "confidence": 0.95,
                "reasoning": "Suspicious phishing or security scam indicators detected.",
                "action_items": [],
            }

        # 2. BANK & FINANCE check
        bank_domains = ["chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com", "paypal.com", "stripe.com"]
        finance_keywords = ["bank statement", "checking statement", "wire received", "tax form", "1099", "w2", "invoice #", "payment confirmation", "receipt for order"]
        if any(bd in sender for bd in bank_domains) or any(fk in text_corpus for fk in ["chase", "bank", "checking account", "statement ready"]):
            return {
                "category": EmailCategory.BANK.value,
                "importance_score": 85,
                "urgency_score": 40,
                "risk_level": RiskLevel.HIGH.value,
                "suggested_action": ActionType.LABEL.value,
                "confidence": 0.92,
                "reasoning": "Banking statement or account notification from financial institution.",
                "action_items": ["Review banking statement"],
            }

        if any(fk in text_corpus for fk in finance_keywords):
            return {
                "category": EmailCategory.FINANCE.value,
                "importance_score": 80,
                "urgency_score": 50,
                "risk_level": RiskLevel.MEDIUM.value,
                "suggested_action": ActionType.LABEL.value,
                "confidence": 0.88,
                "reasoning": "Financial record, receipt, or invoice notification.",
                "action_items": ["Review financial document"],
            }

        # 3. LEGAL check
        legal_keywords = ["nda", "non-disclosure", "confidentiality agreement", "docusign", "patent", "trademark", "intellectual property", "court", "attorney", "settlement"]
        if any(lk in text_corpus for lk in legal_keywords):
            return {
                "category": EmailCategory.LEGAL.value,
                "importance_score": 90,
                "urgency_score": 75,
                "risk_level": RiskLevel.MEDIUM.value,
                "suggested_action": ActionType.KEEP.value,
                "confidence": 0.90,
                "reasoning": "Legal contract, NDA, or DocuSign agreement requiring review.",
                "action_items": ["Review and sign legal documents"],
            }

        # 4. CLIENT / WORK check
        client_keywords = ["sow", "statement of work", "quotation", "proposal", "deliverable", "client sync", "milestone update", "quote request"]
        if any(ck in text_corpus for ck in client_keywords) or "urgent" in subject:
            return {
                "category": EmailCategory.CLIENT.value,
                "importance_score": 92,
                "urgency_score": 85,
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": ActionType.DRAFT_REPLY.value,
                "confidence": 0.89,
                "reasoning": "Client communication requesting quotation, deliverable, or project response.",
                "action_items": ["Prepare reply for client"],
            }

        work_keywords = ["standup", "sprint", "pull request", "jira", "architecture review", "meeting notes", "roadmap", "sync tomorrow"]
        if any(wk in text_corpus for wk in work_keywords):
            return {
                "category": EmailCategory.WORK.value,
                "importance_score": 80,
                "urgency_score": 60,
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": ActionType.KEEP.value,
                "confidence": 0.86,
                "reasoning": "Internal work and team engineering discussion.",
                "action_items": ["Review sprint action items"],
            }

        # 5. NEWSLETTER check
        newsletter_keywords = ["newsletter", "digest", "weekly edition", "weekly roundup", "morning brew", "techcrunch", "substack", "medium daily"]
        if is_newsletter_header or any(nk in text_corpus for nk in newsletter_keywords):
            return {
                "category": EmailCategory.NEWSLETTER.value,
                "importance_score": 25,
                "urgency_score": 10,
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": ActionType.ARCHIVE.value,
                "confidence": 0.94,
                "reasoning": "Informational newsletter digest. Safe to archive.",
                "action_items": [],
            }

        # 6. PROMOTION / ADVERTISEMENT check
        promo_keywords = ["sale", "discount", "% off", "exclusive deal", "special offer", "coupon", "limited time only", "black friday", "save up to"]
        if any(pk in text_corpus for pk in promo_keywords):
            return {
                "category": EmailCategory.PROMOTION.value,
                "importance_score": 15,
                "urgency_score": 15,
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": ActionType.ARCHIVE.value,
                "confidence": 0.91,
                "reasoning": "Promotional marketing discount or sales advertisement.",
                "action_items": [],
            }

        # 7. SOCIAL check
        social_keywords = ["linkedin", "twitter", "x.com", "facebook", "instagram", "connection request", "new follower", "liked your post"]
        if any(sk in text_corpus for sk in social_keywords):
            return {
                "category": EmailCategory.SOCIAL.value,
                "importance_score": 20,
                "urgency_score": 10,
                "risk_level": RiskLevel.LOW.value,
                "suggested_action": ActionType.ARCHIVE.value,
                "confidence": 0.88,
                "reasoning": "Social network notification or connection alert.",
                "action_items": [],
            }

        # Default Personal/General
        return {
            "category": EmailCategory.PERSONAL.value,
            "importance_score": 50,
            "urgency_score": 40,
            "risk_level": RiskLevel.LOW.value,
            "suggested_action": ActionType.KEEP.value,
            "confidence": 0.70,
            "reasoning": "Standard personal message or general correspondence.",
            "action_items": [],
        }
