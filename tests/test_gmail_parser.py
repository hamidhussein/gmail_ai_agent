"""
Unit Tests - Gmail MIME Parser
"""
import pytest
import base64
import json
from gmail.parser import EmailParser


def test_parse_sender():
    name, email_addr = EmailParser.parse_sender("Sarah Jenkins <sarah@acme.com>")
    assert name == "Sarah Jenkins"
    assert email_addr == "sarah@acme.com"

    name2, email_addr2 = EmailParser.parse_sender("plain@domain.com")
    assert email_addr2 == "plain@domain.com"


def test_clean_html():
    raw_html = "<html><body><h1>Hello World</h1><p>This is a <b>test</b> email.<br>Line 2</p></body></html>"
    cleaned = EmailParser.clean_html(raw_html)
    assert "Hello World" in cleaned
    assert "This is a test email." in cleaned
    assert "Line 2" in cleaned
    assert "<" not in cleaned


def test_parse_gmail_message_payload():
    body_text = "Important project update notes."
    encoded_body = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("utf-8")

    sample_msg = {
        "id": "18f92a3bc4d5",
        "threadId": "18f92a3bc4d5",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "Important project update...",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "Project Kickoff"},
                {"name": "From", "value": "Alex Lead <alex@work.com>"},
                {"name": "To", "value": "team@work.com"},
                {"name": "Date", "value": "Thu, 20 Aug 2026 14:00:00 +0000"},
            ],
            "body": {"data": encoded_body},
            "parts": [],
        },
    }

    parsed = EmailParser.parse_gmail_message(sample_msg, account_id=1)
    assert parsed["message_id"] == "18f92a3bc4d5"
    assert parsed["subject"] == "Project Kickoff"
    assert parsed["sender"] == "alex@work.com"
    assert parsed["sender_name"] == "Alex Lead"
    assert parsed["is_unread"] is True
    assert parsed["is_archived"] is False
    assert "Important project update notes." in parsed["body_plain"]
    assert json.loads(parsed["labels_json"]) == ["INBOX", "UNREAD"]
    assert json.loads(parsed["attachments_json"]) == []
