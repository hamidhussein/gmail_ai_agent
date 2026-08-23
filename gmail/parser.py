"""
GmailAI Assistant - Email MIME & Content Parser
"""
import re
import html
import base64
import email.utils
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("GmailAI.Parser")


class EmailParser:
    """Robust parser for Gmail API raw payloads, MIME parts, and headers."""

    @staticmethod
    def parse_header(headers: List[Dict[str, str]], name: str) -> str:
        """Finds a header value by case-insensitive name."""
        target = name.lower()
        for h in headers:
            if h.get("name", "").lower() == target:
                return h.get("value", "")
        return ""

    @staticmethod
    def parse_sender(from_header: str) -> Tuple[str, str]:
        """
        Extracts display name and clean email address from 'From' header.
        Example: 'Sarah Jenkins <sarah@acme.com>' -> ('Sarah Jenkins', 'sarah@acme.com')
        """
        if not from_header:
            return "", ""
        name, address = email.utils.parseaddr(from_header)
        return name.strip(), address.strip().lower()

    @staticmethod
    def parse_date(date_header: str) -> datetime.datetime:
        """Parses RFC 2822 date header into datetime object."""
        if not date_header:
            return datetime.datetime.utcnow()
        try:
            parsed_tuple = email.utils.parsedate_tz(date_header)
            if parsed_tuple:
                timestamp = email.utils.mktime_tz(parsed_tuple)
                return datetime.datetime.utcfromtimestamp(timestamp)
        except Exception as e:
            logger.debug(f"Failed to parse date header '{date_header}': {e}")
        return datetime.datetime.utcnow()

    @classmethod
    def clean_html(cls, raw_html: str) -> str:
        """Converts HTML email body into clean readable plain text."""
        if not raw_html:
            return ""
        try:
            # Remove scripts and styles
            cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
            # Replace breaks and paragraphs with newlines
            cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"</p>", "\n\n", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"</div>", "\n", cleaned, flags=re.IGNORECASE)
            # Remove all other tags
            cleaned = re.sub(r"<[^>]+>", "", cleaned)
            # Decode HTML entities
            decoded = html.unescape(cleaned)
            # Normalize whitespace
            lines = [line.strip() for line in decoded.split("\n")]
            return "\n".join([line for line in lines if line])
        except Exception as e:
            logger.debug(f"Error cleaning HTML: {e}")
            return raw_html

    @classmethod
    def decode_payload_body(cls, payload: Dict[str, Any]) -> str:
        """Decodes base64url data from Gmail API part body."""
        body = payload.get("body", {})
        data = body.get("data", "")
        if not data:
            return ""
        try:
            # Base64url decode
            pad = len(data) % 4
            if pad > 0:
                data += "=" * (4 - pad)
            decoded_bytes = base64.urlsafe_b64decode(data)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"Error decoding base64 payload: {e}")
            return ""

    @classmethod
    def extract_body_and_attachments(
        cls, payload: Dict[str, Any]
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Recursively traverses MIME parts to extract plain body, HTML body,
        and attachment metadata.
        """
        plain_parts: List[str] = []
        html_parts: List[str] = []
        attachments: List[Dict[str, Any]] = []

        mime_type = payload.get("mimeType", "")
        filename = payload.get("filename", "")

        # Check if this part is an attachment
        if filename:
            body_info = payload.get("body", {})
            size_kb = int(body_info.get("size", 0) / 1024)
            attachments.append({
                "filename": filename,
                "mimeType": mime_type,
                "size_kb": size_kb,
                "attachment_id": body_info.get("attachmentId", ""),
            })

        # Process body content
        if mime_type == "text/plain":
            text = cls.decode_payload_body(payload)
            if text:
                plain_parts.append(text)
        elif mime_type == "text/html":
            raw_html = cls.decode_payload_body(payload)
            if raw_html:
                html_parts.append(raw_html)

        # Recurse into nested parts
        parts = payload.get("parts", [])
        for part in parts:
            p_text, p_html, p_att = cls.extract_body_and_attachments(part)
            if p_text:
                plain_parts.append(p_text)
            if p_html:
                html_parts.append(p_html)
            attachments.extend(p_att)

        full_plain = "\n".join(plain_parts).strip()
        full_html = "\n".join(html_parts).strip()

        # If no plain text was found but HTML was, derive plain text from HTML
        if not full_plain and full_html:
            full_plain = cls.clean_html(full_html)

        return full_plain, full_html, attachments

    @classmethod
    def parse_gmail_message(
        cls, msg: Dict[str, Any], account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Converts a raw Gmail API message dictionary into a normalized dictionary
        ready for database storage and AI processing.
        """
        msg_id = msg.get("id", "")
        thread_id = msg.get("threadId", "")
        label_ids = msg.get("labelIds", [])
        snippet = msg.get("snippet", "")
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        # Parse headers
        subject = cls.parse_header(headers, "Subject") or "(No Subject)"
        from_header = cls.parse_header(headers, "From")
        sender_name, sender_email = cls.parse_sender(from_header)
        to_header = cls.parse_header(headers, "To")
        date_header = cls.parse_header(headers, "Date")
        received_at = cls.parse_date(date_header)
        list_unsubscribe = cls.parse_header(headers, "List-Unsubscribe")

        # Parse body and attachments
        body_plain, body_html, attachments = cls.extract_body_and_attachments(payload)
        body_plain = html.unescape(body_plain) if body_plain else ""
        subject = html.unescape(subject)
        snippet = html.unescape(snippet)

        # State flags from Gmail labels
        is_unread = "UNREAD" in label_ids
        is_starred = "STARRED" in label_ids
        is_trash = "TRASH" in label_ids
        is_inbox = "INBOX" in label_ids
        is_archived = not is_inbox and not is_trash

        return {
            "message_id": msg_id,
            "thread_id": thread_id,
            "account_id": account_id,
            "sender": sender_email or from_header,
            "sender_name": sender_name,
            "recipient": to_header,
            "subject": subject,
            "snippet": snippet,
            "body_plain": body_plain or snippet,
            "body_html": body_html,
            "received_at": received_at,
            "is_unread": is_unread,
            "is_starred": is_starred,
            "is_trash": is_trash,
            "is_archived": is_archived,
            "labels_json": str(label_ids),
            "has_attachments": len(attachments) > 0,
            "attachments_json": str(attachments),
            "is_newsletter_header": bool(list_unsubscribe),
        }
