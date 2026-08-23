"""
GmailAI Assistant - Daily AI Intelligence Report Generator
"""
import json
import datetime
import logging
from typing import Dict, Any, Optional

from database.repository import repository
from database.models import DailyDigestRecord
from app.constants import ActionType, EmailCategory
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from app.config import config_manager
from memory.user_profile import user_profile_manager

logger = logging.getLogger("GmailAI.DailyDigest")


class DailyDigestGenerator:
    """Generates comprehensive daily inbox summary reports."""

    def __init__(self):
        self.local_client = LocalOllamaClient()
        self.cloud_client = CloudOpenAIClient()

    def generate_digest_for_today(self) -> DailyDigestRecord:
        """Compiles today's email intelligence report and persists to database."""
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        now = datetime.datetime.utcnow()
        yesterday = now - datetime.timedelta(days=1)

        # Query recent emails
        recent_emails = repository.get_inbox_emails(limit=100)
        today_emails = [e for e in recent_emails if e.received_at >= yesterday]

        total_count = len(today_emails)
        important_emails = [e for e in today_emails if e.importance_score >= 75]
        need_reply_emails = [e for e in today_emails if e.suggested_action == ActionType.DRAFT_REPLY.value and e.is_unread]
        cleanup_emails = [e for e in today_emails if e.suggested_action in [ActionType.ARCHIVE.value, ActionType.MOVE_TRASH.value]]
        meeting_emails = [e for e in today_emails if "meeting" in e.subject.lower() or "sync" in e.subject.lower()]

        # Generate summary content
        summary_markdown = self._compose_summary(
            today_emails, important_emails, need_reply_emails, cleanup_emails
        )

        stats = {
            "processed_at": now.isoformat(),
            "inbox_health": "Optimal" if len(need_reply_emails) < 3 else "Action Needed",
            "top_categories": {
                "Client": len([e for e in today_emails if e.category == EmailCategory.CLIENT.value]),
                "Work": len([e for e in today_emails if e.category == EmailCategory.WORK.value]),
                "Bank/Finance": len([e for e in today_emails if e.category in [EmailCategory.BANK.value, EmailCategory.FINANCE.value]]),
                "Newsletter/Promo": len(cleanup_emails),
            }
        }

        record = repository.save_daily_digest(
            digest_date=today_str,
            total_emails=total_count,
            important_count=len(important_emails),
            need_reply_count=len(need_reply_emails),
            meetings_count=len(meeting_emails),
            cleanup_suggested_count=len(cleanup_emails),
            summary_markdown=summary_markdown,
            stats_json=json.dumps(stats),
        )
        logger.info(f"Daily digest generated for {today_str}")
        return record

    def _compose_summary(
        self, all_emails, important_emails, need_reply_emails, cleanup_emails
    ) -> str:
        user_name = user_profile_manager.profile.name or "User"
        
        md_lines = [
            f"### Good Morning, {user_name} ☀️\n",
            f"Here is your AI Inbox Executive Briefing for today:\n",
        ]

        if important_emails:
            md_lines.append("#### 🌟 Top Priority Items:")
            for e in important_emails[:4]:
                md_lines.append(f"- **{e.sender_name or e.sender}**: {e.subject} *(Importance: {e.importance_score}/100)*")
            md_lines.append("")

        if need_reply_emails:
            md_lines.append("#### ✉️ Urgent Replies Needed:")
            for e in need_reply_emails[:3]:
                md_lines.append(f"- **{e.sender_name or e.sender}**: {e.subject}")
            md_lines.append("")

        if cleanup_emails:
            md_lines.append("#### 🧹 Suggested Cleanup:")
            md_lines.append(f"- **{len(cleanup_emails)} promotional & newsletter emails** ready for one-click archive.")
            md_lines.append("")

        if not important_emails and not need_reply_emails:
            md_lines.append("Your inbox is calm today. No urgent escalations require your attention!")

        return "\n".join(md_lines)


daily_digest_generator = DailyDigestGenerator()
