"""
GmailAI Assistant - Gmail Actions Executor & Safety Dispatcher
"""
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

from gmail.client import GmailClientFactory
from core.security import safety_guard
from core.exceptions import SafetyViolationError, GmailAPIError
from database.repository import repository
from app.constants import ActionType, EmailCategory

logger = logging.getLogger("GmailAI.Actions")


class GmailActions:
    """Executes safe Gmail modifications with full audit logging and safety checks."""

    def __init__(self, account_email: Optional[str] = None):
        self.account_email = account_email

    def _get_service(self):
        service = GmailClientFactory.get_service(self.account_email)
        if not service:
            raise GmailAPIError("Gmail service is not available.")
        return service

    def archive(
        self,
        message_id: str,
        category: str = "NEWSLETTER",
        sender: str = "",
        subject: str = "",
        user_approved: bool = True,
    ) -> bool:
        """Removes the INBOX label to archive the message safely."""
        cat_enum = getattr(EmailCategory, category, EmailCategory.PROMOTION)
        safety_guard.validate_action(
            action=ActionType.ARCHIVE,
            category=cat_enum,
            sender_email=sender,
            user_explicit_approval=user_approved,
        )

        service = self._get_service()
        req = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        )
        GmailClientFactory.execute_with_retry(req)

        # Audit log & update local DB via proper session-managed method
        repository.log_action(
            action_type=ActionType.ARCHIVE.value,
            email_message_id=message_id,
            account_email=self.account_email,
            subject=subject,
            sender=sender,
            reason="User approved cleanup archive",
            user_approved=user_approved,
        )
        repository.update_email_flags(message_id, is_archived=True)

        logger.info(f"Archived message {message_id}")
        return True

    def mark_as_read(
        self,
        message_id: str,
        sender: str = "",
        subject: str = "",
        user_approved: bool = True,
    ) -> bool:
        """Removes the UNREAD label from message."""
        service = self._get_service()
        req = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        )
        GmailClientFactory.execute_with_retry(req)

        repository.log_action(
            action_type=ActionType.MARK_READ.value,
            email_message_id=message_id,
            account_email=self.account_email,
            subject=subject,
            sender=sender,
            reason="Marked as read",
            user_approved=user_approved,
        )
        repository.update_email_flags(message_id, is_unread=False)

        logger.info(f"Marked message {message_id} as read.")
        return True

    def star(self, message_id: str) -> bool:
        """Adds STARRED label."""
        service = self._get_service()
        req = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": ["STARRED"]},
        )
        GmailClientFactory.execute_with_retry(req)
        repository.update_email_flags(message_id, is_starred=True)
        return True

    def move_to_trash(
        self,
        message_id: str,
        category: str = "SPAM",
        sender: str = "",
        subject: str = "",
        user_approved: bool = False,
        double_confirmed: bool = False,
    ) -> bool:
        """
        Moves message to Trash.
        STRICT: Requires explicit user approval and double confirmation.
        """
        cat_enum = getattr(EmailCategory, category, EmailCategory.SPAM)
        # Verify strict safety policy
        safety_guard.validate_action(
            action=ActionType.MOVE_TRASH,
            category=cat_enum,
            sender_email=sender,
            user_explicit_approval=user_approved,
            double_confirmed=double_confirmed,
        )

        service = self._get_service()
        req = service.users().messages().trash(userId="me", id=message_id)
        GmailClientFactory.execute_with_retry(req)

        repository.log_action(
            action_type=ActionType.MOVE_TRASH.value,
            email_message_id=message_id,
            account_email=self.account_email,
            subject=subject,
            sender=sender,
            reason="User confirmed deletion to trash",
            user_approved=user_approved,
            double_confirmed=double_confirmed,
        )
        repository.update_email_flags(message_id, is_trash=True)

        logger.info(f"Moved message {message_id} to Trash.")
        return True

    def create_draft(
        self,
        recipient: str,
        subject: str,
        body_text: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a reply draft in Gmail."""
        service = self._get_service()

        message = MIMEText(body_text, "plain", "utf-8")
        message["to"] = recipient
        message["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft_body: Dict[str, Any] = {"message": {"raw": raw_message}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        req = service.users().drafts().create(userId="me", body=draft_body)
        result = GmailClientFactory.execute_with_retry(req)

        repository.log_action(
            action_type=ActionType.DRAFT_REPLY.value,
            email_message_id=thread_id or "",
            account_email=self.account_email,
            subject=subject,
            sender=recipient,
            reason="AI generated draft created in Gmail",
            user_approved=True,
        )
        logger.info(f"Created draft for {recipient} with subject '{subject}'")
        return result


gmail_actions = GmailActions()
