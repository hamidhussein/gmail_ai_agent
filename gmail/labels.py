"""
GmailAI Assistant - Gmail Labels Management
"""
import logging
from typing import Dict, List, Optional, Any
from gmail.client import GmailClientFactory

logger = logging.getLogger("GmailAI.Labels")


class GmailLabelManager:
    """Manages Gmail labels and custom GmailAI label namespaces."""

    SYSTEM_LABELS = {
        "AI_WORK": "GmailAI/Work",
        "AI_CLIENT": "GmailAI/Client",
        "AI_FINANCE": "GmailAI/Finance",
        "AI_LEGAL": "GmailAI/Legal",
        "AI_NEWSLETTER": "GmailAI/Newsletter",
        "AI_ACTION_REQUIRED": "GmailAI/Action Required",
    }

    def __init__(self, email: Optional[str] = None):
        self.email = email
        self._cached_labels: Dict[str, str] = {}  # name -> id

    def list_labels(self) -> Dict[str, str]:
        """Fetches all Gmail labels for the account."""
        service = GmailClientFactory.get_service(self.email)
        if not service:
            return {}

        req = service.users().labels().list(userId="me")
        res = GmailClientFactory.execute_with_retry(req)
        labels = res.get("labels", [])
        self._cached_labels = {l["name"]: l["id"] for l in labels}
        return self._cached_labels

    def get_or_create_label(self, label_name: str) -> Optional[str]:
        """Returns existing label ID or creates the label in Gmail."""
        if not self._cached_labels:
            self.list_labels()

        if label_name in self._cached_labels:
            return self._cached_labels[label_name]

        service = GmailClientFactory.get_service(self.email)
        if not service:
            return None

        try:
            body = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            req = service.users().labels().create(userId="me", body=body)
            created = GmailClientFactory.execute_with_retry(req)
            label_id = created.get("id")
            if label_id:
                self._cached_labels[label_name] = label_id
                logger.info(f"Created Gmail label '{label_name}' (ID: {label_id})")
            return label_id
        except Exception as e:
            logger.error(f"Failed to create label '{label_name}': {e}")
            return None

    def apply_label(self, message_id: str, label_name: str) -> bool:
        """Applies a label to a Gmail message."""
        label_id = self.get_or_create_label(label_name)
        if not label_id:
            return False

        service = GmailClientFactory.get_service(self.email)
        if not service:
            return False

        req = service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        )
        GmailClientFactory.execute_with_retry(req)
        logger.info(f"Applied label '{label_name}' to message {message_id}")
        return True


gmail_label_manager = GmailLabelManager()
