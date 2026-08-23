"""
GmailAI Assistant - Follow-Up Reminders & Deadlines Detector
"""
import datetime
import logging
from typing import List, Dict, Any

from database.repository import repository
from database.models import EmailRecord

logger = logging.getLogger("GmailAI.Reminders")


class ReminderEngine:
    """Detects pending follow-ups, unanswered questions, and impending deadlines."""

    @staticmethod
    def get_pending_follow_ups() -> List[EmailRecord]:
        """Finds important unread or unreplied emails older than 24 hours."""
        now = datetime.datetime.utcnow()
        one_day_ago = now - datetime.timedelta(days=1)
        seven_days_ago = now - datetime.timedelta(days=7)

        session = repository.get_session()
        try:
            emails = (
                session.query(EmailRecord)
                .filter(
                    EmailRecord.is_unread == True,
                    EmailRecord.is_trash == False,
                    EmailRecord.importance_score >= 70,
                    EmailRecord.received_at.between(seven_days_ago, one_day_ago),
                )
                .order_by(EmailRecord.received_at.asc())
                .limit(20)
                .all()
            )
            return emails
        finally:
            session.close()


reminder_engine = ReminderEngine()
