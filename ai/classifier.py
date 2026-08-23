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

# ---------------------------------------------------------------------------
# Sender-domain → category mapping (checked first, most reliable signal)
# ---------------------------------------------------------------------------
SENDER_DOMAIN_RULES: Dict[str, Dict[str, Any]] = {
    # Social Networks
    "facebookmail.com":    {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "Facebook/Meta notification"},
    "facebook.com":        {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "Facebook notification"},
    "instagram.com":       {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "Instagram notification"},
    "linkedin.com":        {"cat": "SOCIAL",   "imp": 30, "urg": 15, "reason": "LinkedIn notification"},
    "twitter.com":         {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "Twitter/X notification"},
    "x.com":               {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "X (Twitter) notification"},
    "tiktok.com":          {"cat": "SOCIAL",   "imp": 15, "urg": 10, "reason": "TikTok notification"},
    "pinterest.com":       {"cat": "SOCIAL",   "imp": 15, "urg": 10, "reason": "Pinterest notification"},
    "reddit.com":          {"cat": "SOCIAL",   "imp": 20, "urg": 10, "reason": "Reddit notification"},

    # Banking & Finance
    "chase.com":           {"cat": "BANK",     "imp": 85, "urg": 40, "reason": "Chase Bank notification"},
    "bankofamerica.com":   {"cat": "BANK",     "imp": 85, "urg": 40, "reason": "Bank of America notification"},
    "wellsfargo.com":      {"cat": "BANK",     "imp": 85, "urg": 40, "reason": "Wells Fargo notification"},
    "citi.com":            {"cat": "BANK",     "imp": 85, "urg": 40, "reason": "Citi Bank notification"},
    "paypal.com":          {"cat": "FINANCE",  "imp": 80, "urg": 50, "reason": "PayPal transaction notification"},
    "stripe.com":          {"cat": "FINANCE",  "imp": 80, "urg": 50, "reason": "Stripe payment notification"},
    "wise.com":            {"cat": "FINANCE",  "imp": 80, "urg": 50, "reason": "Wise money transfer"},
    "venmo.com":           {"cat": "FINANCE",  "imp": 75, "urg": 40, "reason": "Venmo payment notification"},
    "square.com":          {"cat": "FINANCE",  "imp": 75, "urg": 40, "reason": "Square payment notification"},

    # Newsletters & Content Platforms
    "substack.com":        {"cat": "NEWSLETTER", "imp": 25, "urg": 10, "reason": "Substack newsletter"},
    "medium.com":          {"cat": "NEWSLETTER", "imp": 25, "urg": 10, "reason": "Medium digest"},
    "morningbrew.com":     {"cat": "NEWSLETTER", "imp": 25, "urg": 10, "reason": "Morning Brew newsletter"},
    "analyticsvidhya.com": {"cat": "NEWSLETTER", "imp": 25, "urg": 10, "reason": "Analytics Vidhya newsletter"},
    "tilda.cc":            {"cat": "NEWSLETTER", "imp": 20, "urg": 10, "reason": "Tilda Publishing newsletter"},
    "beehiiv.com":         {"cat": "NEWSLETTER", "imp": 25, "urg": 10, "reason": "Beehiiv newsletter"},
    "mailchimp.com":       {"cat": "NEWSLETTER", "imp": 20, "urg": 10, "reason": "Mailchimp newsletter"},

    # Tech Platforms (account/product updates)
    "email.openai.com":    {"cat": "PERSONAL", "imp": 55, "urg": 30, "reason": "OpenAI account notification"},
    "openai.com":          {"cat": "PERSONAL", "imp": 55, "urg": 30, "reason": "OpenAI account notification"},
    "github.com":          {"cat": "WORK",     "imp": 60, "urg": 35, "reason": "GitHub repository notification"},
    "gitlab.com":          {"cat": "WORK",     "imp": 60, "urg": 35, "reason": "GitLab notification"},
    "atlassian.net":       {"cat": "WORK",     "imp": 65, "urg": 40, "reason": "Jira/Confluence notification"},
    "slack.com":           {"cat": "WORK",     "imp": 55, "urg": 30, "reason": "Slack notification"},
    "notion.so":           {"cat": "WORK",     "imp": 50, "urg": 25, "reason": "Notion notification"},
    "figma.com":           {"cat": "WORK",     "imp": 50, "urg": 25, "reason": "Figma design notification"},
    "vercel.com":          {"cat": "WORK",     "imp": 50, "urg": 25, "reason": "Vercel deployment notification"},
    "lovable.dev":         {"cat": "NEWSLETTER", "imp": 20, "urg": 10, "reason": "Lovable.dev product update"},

    # E-commerce / Booking / Receipts
    "amazon.com":          {"cat": "FINANCE",  "imp": 60, "urg": 30, "reason": "Amazon order/receipt"},
    "ebay.com":            {"cat": "FINANCE",  "imp": 55, "urg": 25, "reason": "eBay transaction"},
    "bookmepk.com":        {"cat": "FINANCE",  "imp": 65, "urg": 30, "reason": "Bookme booking/ticket confirmation"},
    "bookme.pk":           {"cat": "FINANCE",  "imp": 65, "urg": 30, "reason": "Bookme booking/ticket confirmation"},

    # Cloud Providers
    "cloud.google.com":    {"cat": "WORK",     "imp": 60, "urg": 30, "reason": "Google Cloud notification"},
    "aws.amazon.com":      {"cat": "WORK",     "imp": 60, "urg": 30, "reason": "AWS notification"},
    "azure.microsoft.com": {"cat": "WORK",     "imp": 60, "urg": 30, "reason": "Azure notification"},

    # Legal / DocuSign
    "docusign.net":        {"cat": "LEGAL",    "imp": 90, "urg": 75, "reason": "DocuSign document awaiting signature"},
    "docusign.com":        {"cat": "LEGAL",    "imp": 90, "urg": 75, "reason": "DocuSign document awaiting signature"},
}


def _match_sender_domain(sender: str) -> Optional[Dict[str, Any]]:
    """Check if sender email matches any known domain rule."""
    for domain, rule in SENDER_DOMAIN_RULES.items():
        if domain in sender:
            return rule
    return None


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
        Multi-pass rule engine with domain lookup, keyword scoring, and sender pattern matching.
        Guarantees resilient zero-crash fallback if no AI is available.
        """
        sender = (email_data.get("sender") or "").lower()
        sender_name = (email_data.get("sender_name") or "").lower()
        subject = (email_data.get("subject") or "").lower()
        body = (email_data.get("body_plain") or "").lower()[:4000]
        snippet = (email_data.get("snippet") or "").lower()
        is_newsletter_header = email_data.get("is_newsletter_header", False)
        list_unsubscribe = email_data.get("list_unsubscribe", "")

        text_corpus = f"{subject} {snippet} {body}"
        full_text = f"{subject} {snippet} {body} {sender} {sender_name}"

        # =====================================================================
        # PASS 0: Spam / Phishing (highest priority — override everything)
        # =====================================================================
        spam_signals = [
            "verify your password", "account suspended", "unauthorized access detected",
            "confirm your identity immediately", "wire transfer urgently", "crypto giveaway",
            "winner of", "claim your prize", "click here to unlock", "act now or lose",
            "your account has been suspended", "verify account immediately",
            "nigerian prince", "million dollars", "lottery winner",
            "bitcoin doubler", "investment opportunity guaranteed",
        ]
        if any(sig in text_corpus for sig in spam_signals):
            return cls._result(EmailCategory.SPAM, 5, 10, RiskLevel.CRITICAL,
                               ActionType.MOVE_TRASH, 0.95,
                               "Suspicious phishing or security scam indicators detected.")

        # =====================================================================
        # PASS 1: Sender domain lookup (most reliable signal)
        # =====================================================================
        domain_match = _match_sender_domain(sender)
        if domain_match:
            cat_enum = EmailCategory(domain_match["cat"])
            # Refine: if domain says NEWSLETTER but subject looks like account security, override
            if cat_enum in (EmailCategory.NEWSLETTER, EmailCategory.SOCIAL):
                security_keywords = ["security alert", "sign-in", "password", "recovered",
                                     "account data", "verification", "suspicious activity"]
                if any(sk in text_corpus for sk in security_keywords):
                    return cls._result(EmailCategory.PERSONAL, 70, 55, RiskLevel.MEDIUM,
                                       ActionType.KEEP, 0.88,
                                       "Account security notification from platform.")
            return cls._result(
                cat_enum,
                domain_match["imp"],
                domain_match["urg"],
                RiskLevel.LOW if domain_match["imp"] < 70 else RiskLevel.MEDIUM,
                ActionType.ARCHIVE if domain_match["imp"] < 40 else ActionType.LABEL,
                0.92,
                domain_match["reason"],
            )

        # =====================================================================
        # PASS 2: Google-specific routing (very common sender)
        # =====================================================================
        if "google" in sender or sender_name.startswith("google"):
            # Google security alerts
            security_words = ["security alert", "sign-in", "recovered", "password",
                              "suspicious", "account data", "2-step", "verification"]
            if any(sw in text_corpus for sw in security_words):
                return cls._result(EmailCategory.PERSONAL, 75, 60, RiskLevel.MEDIUM,
                                   ActionType.KEEP, 0.90,
                                   "Google account security notification.")

            # Google Play / Terms of Service
            if "terms of service" in text_corpus or "privacy policy" in text_corpus:
                return cls._result(EmailCategory.LEGAL, 90, 70, RiskLevel.MEDIUM,
                                   ActionType.KEEP, 0.91,
                                   "Terms of Service or Privacy Policy update from Google.")

            # Google Workspace / Cloud
            if any(w in text_corpus for w in ["workspace", "cloud console", "billing", "gcp"]):
                return cls._result(EmailCategory.WORK, 65, 40, RiskLevel.LOW,
                                   ActionType.LABEL, 0.86,
                                   "Google Workspace or Cloud Platform notification.")

            # General Google notification
            return cls._result(EmailCategory.PERSONAL, 50, 30, RiskLevel.LOW,
                               ActionType.KEEP, 0.80,
                               "General Google account notification.")

        # =====================================================================
        # PASS 3: Banking & Finance keywords
        # =====================================================================
        bank_domains = ["chase.com", "bankofamerica.com", "wellsfargo.com", "citi.com",
                        "hsbc.com", "barclays.com", "capitalone.com"]
        if any(bd in sender for bd in bank_domains):
            return cls._result(EmailCategory.BANK, 85, 40, RiskLevel.HIGH,
                               ActionType.LABEL, 0.92,
                               "Banking statement or account notification from financial institution.")

        finance_keywords = [
            "bank statement", "checking statement", "wire received", "tax form",
            "1099", "w-2", "w2", "invoice #", "payment confirmation", "receipt for order",
            "payment received", "transaction alert", "direct deposit", "refund processed",
            "billing statement", "credit card statement", "loan payment",
            "booking confirmation", "e-ticket", "reservation confirmed", "order confirmed",
            "your order", "order receipt", "purchase confirmation",
        ]
        if any(fk in text_corpus for fk in finance_keywords):
            return cls._result(EmailCategory.FINANCE, 75, 45, RiskLevel.MEDIUM,
                               ActionType.LABEL, 0.88,
                               "Financial transaction, booking, receipt, or invoice notification.")

        # =====================================================================
        # PASS 4: Legal keywords
        # =====================================================================
        legal_keywords = [
            "nda", "non-disclosure", "confidentiality agreement", "docusign",
            "patent", "trademark", "intellectual property", "court", "attorney",
            "settlement", "terms of service", "privacy policy", "legal notice",
            "compliance", "regulatory", "subpoena", "arbitration",
        ]
        if any(lk in text_corpus for lk in legal_keywords):
            return cls._result(EmailCategory.LEGAL, 90, 75, RiskLevel.MEDIUM,
                               ActionType.KEEP, 0.90,
                               "Legal contract, policy update, or regulatory notice.")

        # =====================================================================
        # PASS 5: Client / Work keywords
        # =====================================================================
        client_keywords = [
            "sow", "statement of work", "quotation", "proposal", "deliverable",
            "client sync", "milestone update", "quote request", "rfp", "rfq",
            "project update", "project proposal", "scope of work",
        ]
        if any(ck in text_corpus for ck in client_keywords) or (
            "urgent" in subject and not any(s in sender for s in ["facebook", "twitter", "linkedin"])
        ):
            return cls._result(EmailCategory.CLIENT, 92, 85, RiskLevel.LOW,
                               ActionType.DRAFT_REPLY, 0.89,
                               "Client communication requesting quotation, deliverable, or project response.")

        work_keywords = [
            "standup", "sprint", "pull request", "jira", "architecture review",
            "meeting notes", "roadmap", "sync tomorrow", "code review",
            "deployment", "ci/cd", "pipeline", "merge request", "release notes",
            "kanban", "retrospective", "design review", "1:1", "one-on-one",
        ]
        if any(wk in text_corpus for wk in work_keywords):
            return cls._result(EmailCategory.WORK, 80, 60, RiskLevel.LOW,
                               ActionType.KEEP, 0.86,
                               "Internal work and team engineering discussion.")

        # =====================================================================
        # PASS 6: Newsletter detection (List-Unsubscribe header is strong signal)
        # =====================================================================
        newsletter_keywords = [
            "newsletter", "digest", "weekly edition", "weekly roundup",
            "morning brew", "techcrunch", "substack", "medium daily",
            "unsubscribe", "view in browser", "email preferences",
            "this week in", "daily brief", "news update",
        ]
        has_unsubscribe = bool(list_unsubscribe) or "unsubscribe" in body[:2000]
        if is_newsletter_header or any(nk in text_corpus for nk in newsletter_keywords):
            # If it has strong newsletter signals, classify as newsletter
            return cls._result(EmailCategory.NEWSLETTER, 25, 10, RiskLevel.LOW,
                               ActionType.ARCHIVE, 0.94,
                               "Informational newsletter digest. Safe to archive.")

        # =====================================================================
        # PASS 7: Promotion / Advertisement
        # =====================================================================
        promo_keywords = [
            "sale", "discount", "% off", "exclusive deal", "special offer",
            "coupon", "limited time only", "black friday", "save up to",
            "promo code", "flash sale", "clearance", "shop now", "buy now",
            "free trial", "upgrade now", "premium plan", "unlock features",
        ]
        if any(pk in text_corpus for pk in promo_keywords):
            return cls._result(EmailCategory.PROMOTION, 15, 15, RiskLevel.LOW,
                               ActionType.ARCHIVE, 0.91,
                               "Promotional marketing discount or sales advertisement.")

        # =====================================================================
        # PASS 8: Social (catch-all for social-sounding content)
        # =====================================================================
        social_keywords = [
            "connection request", "new follower", "liked your post",
            "commented on your", "mentioned you", "sent you a message",
            "friend request", "tagged you", "shared a post",
            "messenger", "via messenger",
        ]
        social_domains = ["facebookmail", "linkedin", "twitter", "instagram",
                          "tiktok", "pinterest", "reddit"]
        if any(sk in text_corpus for sk in social_keywords) or any(sd in sender for sd in social_domains):
            return cls._result(EmailCategory.SOCIAL, 20, 10, RiskLevel.LOW,
                               ActionType.ARCHIVE, 0.88,
                               "Social network notification or connection alert.")

        # =====================================================================
        # PASS 9: Emails with unsubscribe but no other match → Newsletter
        # =====================================================================
        if has_unsubscribe:
            return cls._result(EmailCategory.NEWSLETTER, 20, 10, RiskLevel.LOW,
                               ActionType.ARCHIVE, 0.82,
                               "Mass email with unsubscribe link. Likely newsletter or marketing.")

        # =====================================================================
        # DEFAULT: Personal / General
        # =====================================================================
        return cls._result(EmailCategory.PERSONAL, 50, 40, RiskLevel.LOW,
                           ActionType.KEEP, 0.70,
                           "Standard personal message or general correspondence.")

    @staticmethod
    def _result(category: EmailCategory, importance: int, urgency: int,
                risk: RiskLevel, action: ActionType, confidence: float,
                reasoning: str, action_items: List[str] = None) -> Dict[str, Any]:
        """Helper to build a consistent classification result dict."""
        return {
            "category": category.value,
            "importance_score": importance,
            "urgency_score": urgency,
            "risk_level": risk.value,
            "suggested_action": action.value,
            "confidence": confidence,
            "reasoning": reasoning,
            "action_items": action_items or [],
        }
