"""
GmailAI Assistant - Gmail Message Reader & Synchronizer
"""
import logging
from typing import List, Dict, Any, Optional

from gmail.client import GmailClientFactory
from gmail.parser import EmailParser
from core.exceptions import GmailAPIError

logger = logging.getLogger("GmailAI.Reader")


class GmailReader:
    """Reads messages and threads from Gmail using batching and queries."""

    def __init__(self, email: Optional[str] = None):
        self.email = email

    def fetch_message_list(
        self,
        query: str = "in:inbox",
        max_results: int = 50,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lists message IDs matching the Gmail search query."""
        service = GmailClientFactory.get_service(self.email)
        if not service:
            raise GmailAPIError("Gmail API service not initialized or authenticated.")

        req = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
            pageToken=page_token,
        )
        return GmailClientFactory.execute_with_retry(req)

    def get_message_detail(self, message_id: str, format_type: str = "full") -> Dict[str, Any]:
        """Fetches full payload for a single message."""
        service = GmailClientFactory.get_service(self.email)
        if not service:
            raise GmailAPIError("Gmail API service not initialized.")

        req = service.users().messages().get(
            userId="me",
            id=message_id,
            format=format_type,
        )
        return GmailClientFactory.execute_with_retry(req)

    def fetch_and_parse_inbox(
        self,
        account_id: int,
        query: str = "in:inbox",
        max_count: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Fetches the latest messages and parses them into standardized dicts.
        """
        res = self.fetch_message_list(query=query, max_results=max_count)
        messages_meta = res.get("messages", [])
        parsed_emails: List[Dict[str, Any]] = []

        for item in messages_meta:
            msg_id = item.get("id")
            if not msg_id:
                continue
            try:
                raw_msg = self.get_message_detail(msg_id)
                parsed = EmailParser.parse_gmail_message(raw_msg, account_id=account_id)
                parsed_emails.append(parsed)
            except Exception as e:
                logger.error(f"Error fetching/parsing message {msg_id}: {e}")

        logger.info(f"Fetched and parsed {len(parsed_emails)} emails from Gmail.")
        return parsed_emails
