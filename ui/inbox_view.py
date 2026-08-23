"""
GmailAI Assistant - Polished Intelligence Inbox & Reader for Flet
"""
import re
import html
import json
import datetime
import flet as ft
from typing import Dict, Any, List, Optional
from resources.styles.theme import (
    COLORS,
    get_category_color,
    border_all,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
)
from ui.components.reply_modal import ReplyDialog
from database.repository import repository
from gmail.actions import gmail_actions
from memory.learning import learning_engine

AVATAR_PALETTE = [
    "#6366F1",  # Indigo
    "#0EA5E9",  # Sky Blue
    "#10B981",  # Emerald
    "#8B5CF6",  # Violet
    "#F59E0B",  # Amber
    "#EC4899",  # Pink
    "#14B8A6",  # Teal
]


def get_sender_initials(name: str, email: str) -> str:
    """Returns 1-2 uppercase initials from sender name or email."""
    cleaned = (name or "").strip()
    if not cleaned:
        cleaned = (email or "").split("@")[0].strip()
    if not cleaned:
        return "?"

    words = cleaned.split()
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    return cleaned[:2].upper()


def get_avatar_color(text: str) -> str:
    """Returns a deterministic accent color for the avatar."""
    val = sum(ord(c) for c in (text or "A"))
    return AVATAR_PALETTE[val % len(AVATAR_PALETTE)]


def clean_email_text(raw_text: str) -> str:
    """Decodes HTML entities, removes raw angle brackets from links, and cleans whitespace."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    # Remove angle brackets around standalone URLs: <https://...> -> https://...
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_date_display(dt: Any) -> str:
    """Formats datetime into human-friendly representation."""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except Exception:
            return dt

    now = datetime.datetime.utcnow()
    diff = now - dt

    if diff.days == 0:
        return dt.strftime("%I:%M %p").lstrip("0")
    elif diff.days == 1:
        return f"Yesterday {dt.strftime('%I:%M %p').lstrip('0')}"
    elif diff.days < 7:
        return dt.strftime("%a %I:%M %p")
    elif dt.year == now.year:
        return dt.strftime("%b %d")
    else:
        return dt.strftime("%b %d, %Y")


def format_full_date(dt: Any) -> str:
    """Returns full timestamp format (e.g. Wednesday, Jul 29, 2026 • 10:45 AM)."""
    if not dt:
        return "Unknown Date"
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except Exception:
            return dt
    return dt.strftime("%A, %b %d, %Y • %I:%M %p").lstrip("0")


class InboxIntelligenceView(ft.Container):
    """Polished Intelligence Inbox with clean markdown email reader, metadata cards, and AI analysis."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.current_category = "ALL"
        self.search_query = ""
        self.selected_email: Optional[Dict[str, Any]] = None
        self.emails_data: List[Any] = []

        # Top search field
        self.search_field = ft.TextField(
            hint_text="Search sender, subject, keywords...",
            prefix_icon=ft.Icons.SEARCH,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            content_padding=10,
            width=340,
            on_change=self._on_search_change,
        )

        categories = ["ALL", "CLIENT", "WORK", "BANK", "FINANCE", "LEGAL", "NEWSLETTER", "PROMOTION", "SOCIAL", "SPAM"]
        self.filter_chips_row = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Chip(
                    label=ft.Text(cat, size=12, weight=ft.FontWeight.W_600),
                    selected=cat == "ALL",
                    selected_color=COLORS["primary"],
                    bgcolor=COLORS["bg_card"],
                    border_side=ft.BorderSide(1, COLORS["border"]),
                    on_select=lambda e, c=cat: self._on_category_select(c),
                )
                for cat in categories
            ],
        )

        # Left Column: Email list
        self.email_list_column = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Right Column: Detail Reader Container
        self.detail_container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, size=56, color=COLORS["text_muted"]),
                ft.Text("Select an email to view full conversation and AI intelligence", size=15, color=COLORS["text_secondary"]),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=12,
            padding=20,
            expand=14,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Top Header Row
                ft.Row([
                    ft.Column([
                        ft.Text("Intelligence Inbox", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Categorized, analyzed, and action-ready email management.", size=13, color=COLORS["text_secondary"]),
                    ], spacing=2),
                    self.search_field,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Category Filter Chips Row
                self.filter_chips_row,

                # Split Master-Detail Layout
                ft.Row([
                    # Email List (10 parts)
                    ft.Container(
                        content=self.email_list_column,
                        expand=10,
                    ),
                    # Email Detail Reader (14 parts)
                    self.detail_container,
                ], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )

        self.load_emails()

    def refresh_data(self) -> None:
        self.load_emails()

    def _on_search_change(self, e):
        self.search_query = self.search_field.value.strip()
        self.load_emails()

    def _on_category_select(self, cat: str):
        self.current_category = cat
        for chip in self.filter_chips_row.controls:
            chip.selected = (chip.label.value == cat)
        safe_update(self.filter_chips_row)
        self.load_emails()

    def load_emails(self) -> None:
        """Loads emails from repository, cleans unescaped text, and populates cards."""
        self.email_list_column.controls.clear()
        emails = repository.get_inbox_emails(
            category=None if self.current_category == "ALL" else self.current_category,
            search_query=self.search_query if self.search_query else None,
            limit=60,
        )
        self.emails_data = emails

        if not emails:
            self.email_list_column.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.INBOX_OUTLINED, size=40, color=COLORS["text_muted"]),
                        ft.Text("No emails found in this category", size=14, color=COLORS["text_muted"]),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=50,
                    alignment=align_center(),
                )
            )
            safe_update(self.page_ref)
            return

        for record in emails:
            email_dict = {
                "id": record.id,
                "message_id": record.message_id,
                "thread_id": record.thread_id,
                "sender": record.sender,
                "sender_name": clean_email_text(record.sender_name or ""),
                "recipient": record.recipient,
                "subject": clean_email_text(record.subject or "(No Subject)"),
                "snippet": clean_email_text(record.snippet or ""),
                "body_plain": clean_email_text(record.body_plain or ""),
                "received_at": record.received_at,
                "is_unread": record.is_unread,
                "category": record.category,
                "importance_score": record.importance_score,
                "urgency_score": record.urgency_score,
                "risk_level": record.risk_level,
                "ai_reasoning": clean_email_text(record.ai_reasoning or ""),
                "suggested_action": record.suggested_action,
                "action_items_json": record.action_items_json,
                "attachments_json": record.attachments_json,
            }
            card = self._build_email_card(email_dict)
            self.email_list_column.controls.append(card)

        # Retain selection or select top email
        if not self.selected_email and emails:
            first = emails[0]
            first_dict = {
                "id": first.id,
                "message_id": first.message_id,
                "thread_id": first.thread_id,
                "sender": first.sender,
                "sender_name": clean_email_text(first.sender_name or ""),
                "recipient": first.recipient,
                "subject": clean_email_text(first.subject or "(No Subject)"),
                "snippet": clean_email_text(first.snippet or ""),
                "body_plain": clean_email_text(first.body_plain or ""),
                "received_at": first.received_at,
                "is_unread": first.is_unread,
                "category": first.category,
                "importance_score": first.importance_score,
                "urgency_score": first.urgency_score,
                "risk_level": first.risk_level,
                "ai_reasoning": clean_email_text(first.ai_reasoning or ""),
                "suggested_action": first.suggested_action,
                "action_items_json": first.action_items_json,
                "attachments_json": first.attachments_json,
            }
            self._select_email(first_dict)

        safe_update(self.page_ref)

    def _build_email_card(self, email_data: Dict[str, Any]) -> ft.Container:
        cat = email_data.get("category") or "PERSONAL"
        cat_color = get_category_color(cat)
        importance = email_data.get("importance_score") or 50
        is_selected = self.selected_email and self.selected_email.get("id") == email_data.get("id")
        sender_label = email_data.get("sender_name") or email_data.get("sender", "Unknown")
        initials = get_sender_initials(sender_label, email_data.get("sender", ""))
        avatar_bg = get_avatar_color(sender_label)
        date_str = format_date_display(email_data.get("received_at"))

        # Score badge styling
        score_color = COLORS["success"] if importance >= 75 else (COLORS["warning"] if importance >= 45 else COLORS["text_muted"])

        return ft.Container(
            content=ft.Row([
                # Sender Initials Avatar
                ft.Container(
                    content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=avatar_bg,
                    width=36,
                    height=36,
                    border_radius=18,
                    alignment=align_center(),
                ),

                # Text Content Area
                ft.Column([
                    # Row 1: Sender Name + Category Badge + Date
                    ft.Row([
                        ft.Text(sender_label, size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"], expand=True, no_wrap=True),
                        ft.Container(
                            content=ft.Text(cat[:8], size=9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            bgcolor=cat_color,
                            padding=padding_symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        ),
                        ft.Text(date_str, size=11, color=COLORS["text_muted"]),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),

                    # Row 2: Subject
                    ft.Text(
                        email_data.get("subject") or "(No Subject)",
                        size=13,
                        weight=ft.FontWeight.W_600 if email_data.get("is_unread") else ft.FontWeight.NORMAL,
                        color=COLORS["text_primary"] if is_selected or email_data.get("is_unread") else COLORS["text_secondary"],
                        no_wrap=True,
                    ),

                    # Row 3: Snippet + Score Chip
                    ft.Row([
                        ft.Text(
                            email_data.get("snippet") or "",
                            size=12,
                            color=COLORS["text_secondary"],
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(f"{importance}", size=10, weight=ft.FontWeight.BOLD, color=score_color),
                            bgcolor=COLORS["bg_main"],
                            border=border_all(1, score_color),
                            padding=padding_symmetric(horizontal=5, vertical=1),
                            border_radius=4,
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], expand=True, spacing=4),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, spacing=10),
            bgcolor=COLORS["bg_card_hover"] if is_selected else COLORS["bg_card"],
            border=border_all(1, COLORS["primary"] if is_selected else COLORS["border"]),
            border_radius=10,
            padding=padding_symmetric(horizontal=12, vertical=10),
            on_click=lambda e, d=email_data: self._select_email(d),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _select_email(self, email_data: Dict[str, Any]) -> None:
        self.selected_email = email_data
        learning_engine.on_user_email_opened(email_data.get("sender", ""))
        self._render_detail_drawer(email_data)
        safe_update(self.page_ref)

    def _render_detail_drawer(self, data: Dict[str, Any]) -> None:
        cat = data.get("category") or "PERSONAL"
        cat_color = get_category_color(cat)
        importance = data.get("importance_score") or 50
        urgency = data.get("urgency_score") or 50
        reasoning = data.get("ai_reasoning") or "Standard message analyzed."
        action = data.get("suggested_action") or "NONE"
        sender_name = data.get("sender_name") or data.get("sender", "Unknown")
        sender_email = data.get("sender", "")
        recipient = data.get("recipient", "me")
        date_full = format_full_date(data.get("received_at"))
        initials = get_sender_initials(sender_name, sender_email)
        avatar_bg = get_avatar_color(sender_name)

        # Action items parse
        action_items = []
        try:
            if data.get("action_items_json"):
                action_items = json.loads(data["action_items_json"])
        except Exception:
            pass

        action_chips = []
        for item in action_items:
            task_text = item if isinstance(item, str) else item.get("task", "")
            if task_text:
                action_chips.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=COLORS["primary"]),
                            ft.Text(task_text, size=12, color=COLORS["text_primary"]),
                        ], spacing=6, tight=True),
                        bgcolor=COLORS["bg_card"],
                        border=border_all(1, COLORS["border"]),
                        padding=padding_symmetric(horizontal=10, vertical=6),
                        border_radius=8,
                    )
                )

        body_content = data.get("body_plain") or data.get("snippet") or "(Empty message body)"

        self.detail_container.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                # Top Action Bar
                ft.Row([
                    ft.ElevatedButton(
                        "AI Reply Assistant",
                        icon=ft.Icons.AUTO_AWESOME,
                        bgcolor=COLORS["primary"],
                        color=COLORS["text_primary"],
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._open_reply_dialog(data),
                    ),
                    ft.OutlinedButton(
                        "Archive",
                        icon=ft.Icons.ARCHIVE_OUTLINED,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._archive_email(data),
                    ),
                    ft.OutlinedButton(
                        "Trash",
                        icon=ft.Icons.DELETE_OUTLINE,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["danger"]),
                        on_click=lambda e: self._trash_email(data),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY,
                        tooltip="Copy body to clipboard",
                        icon_color=COLORS["text_secondary"],
                        on_click=lambda e: self._copy_to_clipboard(body_content),
                    ),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),

                # Subject Line
                ft.Text(data.get("subject") or "(No Subject)", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),

                # Sender & Recipient Information Card
                ft.Container(
                    content=ft.Row([
                        # Avatar
                        ft.Container(
                            content=ft.Text(initials, size=15, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            bgcolor=avatar_bg,
                            width=44,
                            height=44,
                            border_radius=22,
                            alignment=align_center(),
                        ),

                        # Sender Info
                        ft.Column([
                            ft.Row([
                                ft.Text(sender_name, size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                                ft.Text(f"<{sender_email}>", size=12, color=COLORS["text_muted"]),
                            ], spacing=6),
                            ft.Row([
                                ft.Text(f"To: {recipient}", size=12, color=COLORS["text_secondary"]),
                                ft.Text("•", color=COLORS["text_muted"], size=12),
                                ft.Text(date_full, size=12, color=COLORS["text_secondary"]),
                            ], spacing=6),
                        ], expand=True, spacing=2),

                        # Category & Score Badges
                        ft.Column([
                            ft.Container(
                                content=ft.Text(cat, size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                bgcolor=cat_color,
                                padding=padding_symmetric(horizontal=8, vertical=3),
                                border_radius=4,
                            ),
                            ft.Text(f"Score: {importance}/100", size=11, weight=ft.FontWeight.BOLD, color=COLORS["success"] if importance >= 75 else COLORS["warning"]),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    bgcolor=COLORS["bg_card_hover"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                    padding=14,
                ),

                # AI Intelligence Insights Card
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=COLORS["badge_text"]),
                            ft.Text("AI Intelligence & Insights", size=13, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"]),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Text(f"Action: {action}", size=10, weight=ft.FontWeight.BOLD, color=COLORS["secondary"]),
                                bgcolor=COLORS["bg_main"],
                                border=border_all(1, COLORS["secondary"]),
                                padding=padding_symmetric(horizontal=8, vertical=2),
                                border_radius=6,
                            ),
                        ]),
                        ft.Divider(height=1, color="#312E81"),
                        ft.Text(reasoning, size=12, color=COLORS["text_primary"]),
                        ft.Row([
                            ft.Text(f"⚡ Urgency: {urgency}/100", size=11, color=COLORS["text_secondary"], weight=ft.FontWeight.W_500),
                            ft.Text("•", color=COLORS["text_muted"]),
                            ft.Text(f"🛡️ Safety: {data.get('risk_level', 'SAFE')}", size=11, color=COLORS["success"], weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        ft.Column([
                            ft.Text("Action Items Detected:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                            ft.Column(action_chips, spacing=6),
                        ], visible=len(action_chips) > 0, spacing=6),
                    ], spacing=10),
                    bgcolor="#0C1021",
                    border=border_all(1, "#312E81"),
                    border_radius=10,
                    padding=16,
                ),

                # Email Body Reader Container
                ft.Container(
                    content=ft.Markdown(
                        body_content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    ),
                    padding=20,
                    bgcolor="#070A14",
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                ),
            ],
        )

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.page_ref.set_clipboard(text)
            self.page_ref.open(ft.SnackBar(ft.Text("Email body copied to clipboard!"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _open_reply_dialog(self, email_data: Dict[str, Any]) -> None:
        dialog = ReplyDialog(page=self.page_ref, email_data=email_data)
        try:
            self.page_ref.open(dialog)
        except Exception:
            pass

    def _archive_email(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.archive_message(email_data["message_id"])
            self.page_ref.open(ft.SnackBar(ft.Text("Email archived"), bgcolor=COLORS["success"]))
            self.load_emails()
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Archive: {e}"), bgcolor=COLORS["warning"]))
            except Exception:
                pass

    def _trash_email(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.trash_message(email_data["message_id"])
            self.page_ref.open(ft.SnackBar(ft.Text("Email moved to trash"), bgcolor=COLORS["danger"]))
            self.load_emails()
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Trash: {e}"), bgcolor=COLORS["warning"]))
            except Exception:
                pass
