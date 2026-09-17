"""
Test suite for polished Inbox View and AI Reply Assistant components.
"""
import pytest
from unittest.mock import MagicMock, patch
import flet as ft
from ui.components.reply_modal import ReplyDialog
from ui.inbox_view import InboxIntelligenceView
from database.models import EmailRecord


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.set_clipboard = MagicMock()
    return page


@pytest.fixture
def sample_email_dict():
    return {
        "id": 101,
        "message_id": "msg_test_101",
        "thread_id": "thread_test_101",
        "sender": "sarah.connor@cyberdyne.io",
        "sender_name": "Sarah Connor",
        "recipient": "me@example.com",
        "subject": "Q4 Enterprise Security Review and Timeline",
        "snippet": "Can we confirm the deployment schedule by Friday?",
        "body_plain": "Hi team, please review the security checklist and confirm if we are still on track for Friday.",
        "received_at": "2026-09-16 10:00:00",
        "is_unread": True,
        "is_starred": False,
        "is_archived": False,
        "category": "WORK",
        "importance_score": 88,
        "urgency_score": 85,
        "risk_level": "LOW",
        "suggested_action": "REPLY",
        "reasoning": "High-priority work request with Friday deadline.",
        "action_items": '["Confirm deployment schedule", "Review security checklist"]',
        "has_attachments": True,
    }


def test_reply_dialog_initialization(mock_page, sample_email_dict):
    dialog = ReplyDialog(page=mock_page, email_data=sample_email_dict)
    assert dialog.selected_tone == "PROFESSIONAL"
    assert len(dialog.tone_chip_controls) == 6
    assert isinstance(dialog.reply_editor, ft.TextField)


def test_reply_dialog_tone_change(mock_page, sample_email_dict):
    dialog = ReplyDialog(page=mock_page, email_data=sample_email_dict)
    with patch("ai.reply_generator.reply_generator.generate_reply_with_source") as mock_gen:
        mock_gen.return_value = ("Friendly response draft", "local")
        dialog._set_tone_from_pill("friendly")
        assert dialog.selected_tone == "friendly"


def test_reply_dialog_preset_chip(mock_page, sample_email_dict):
    dialog = ReplyDialog(page=mock_page, email_data=sample_email_dict)
    with patch("ai.reply_generator.reply_generator.generate_reply_with_source") as mock_gen:
        mock_gen.return_value = ("Agreed on timeline", "heuristic")
        dialog._apply_quick_prompt("Confirm agreement & next steps")
        assert "Confirm agreement" in dialog.custom_prompt.value


def test_inbox_card_urgency_and_task_badges(mock_page):
    inbox = InboxIntelligenceView(page=mock_page)
    
    email = EmailRecord(
        id=202,
        account_id=1,
        message_id="msg_urgent_202",
        thread_id="th_202",
        sender="boss@corp.com",
        sender_name="Executive Boss",
        recipient="me@example.com",
        subject="URGENT: Contract Approval Needed",
        snippet="Please sign by end of day.",
        body_plain="Need approval ASAP.",
        received_at="2026-09-17 08:00:00",
        is_unread=True,
        is_starred=True,
        category="WORK",
        importance_score=95,
        urgency_score=90,
        risk_level="HIGH",
        suggested_action="REPLY",
        ai_reasoning="Critical high-risk item",
        action_items_json='["Sign document", "Notify legal"]',
    )
    
    card = inbox._build_email_card(email)
    assert isinstance(card, ft.Container)
    assert email.id in inbox.card_refs
    assert email.id in inbox.unread_dot_refs
    assert email.id in inbox.star_btn_refs


def test_inbox_quick_reply_section_build(mock_page, sample_email_dict):
    inbox = InboxIntelligenceView(page=mock_page)
    quick_section = inbox._build_quick_reply_section(sample_email_dict)
    assert isinstance(quick_section, ft.Container)
    assert isinstance(quick_section.content, ft.Column)
