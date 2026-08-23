"""
GmailAI Assistant - Intelligence Inbox Viewer for Flet
"""
import json
import flet as ft
from typing import Dict, Any, List, Optional
from resources.styles.theme import COLORS, get_category_color, glass_container
from ui.components.reply_modal import ReplyDialog
from database.repository import repository
from gmail.actions import gmail_actions
from memory.learning import learning_engine


class InboxIntelligenceView(ft.Container):
    """Modern Intelligence Inbox with instant category filtering, virtual list, and live AI detail drawer."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.current_category = "ALL"
        self.search_query = ""
        self.selected_email: Optional[Dict[str, Any]] = None
        self.emails_data: List[Any] = []

        # Top search & filter bar
        self.search_field = ft.TextField(
            hint_text="Search sender, subject, content...",
            prefix_icon=ft.Icons.SEARCH,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            content_padding=10,
            width=320,
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

        # Right Column: Detail Card Container
        self.detail_container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, size=48, color=COLORS["text_muted"]),
                ft.Text("Select an email to view AI analysis", size=15, color=COLORS["text_secondary"]),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            border_radius=12,
            padding=24,
            expand=13,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Top Header Row
                ft.Row([
                    ft.Text("Intelligence Inbox", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    self.search_field,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Category Filter Chips Row
                self.filter_chips_row,

                # Split Master-Detail Layout
                ft.Row([
                    # Email List (11 parts)
                    ft.Container(
                        content=self.email_list_column,
                        expand=11,
                    ),
                    # Email Detail Drawer (13 parts)
                    self.detail_container,
                ], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=ft.padding.all(24),
            **kwargs,
        )

        self.load_emails()

    def refresh_data(self) -> None:
        """Called upon view activation or after sync."""
        self.load_emails()

    def _on_search_change(self, e):
        self.search_query = self.search_field.value.strip()
        self.load_emails()

    def _on_category_select(self, cat: str):
        self.current_category = cat
        for chip in self.filter_chips_row.controls:
            chip.selected = (chip.label.value == cat)
        if self.page:
            self.filter_chips_row.update()
        self.load_emails()

    def load_emails(self) -> None:
        """Loads matching emails from repository and populates cards."""
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
                    content=ft.Text("No emails found matching your filter.", size=14, color=COLORS["text_muted"]),
                    padding=40,
                    alignment=ft.alignment.center,
                )
            )
            if self.page:
                self.page.update()
            return

        for record in emails:
            email_dict = {
                "id": record.id,
                "message_id": record.message_id,
                "thread_id": record.thread_id,
                "sender": record.sender,
                "sender_name": record.sender_name,
                "recipient": record.recipient,
                "subject": record.subject,
                "snippet": record.snippet,
                "body_plain": record.body_plain,
                "received_at": record.received_at,
                "is_unread": record.is_unread,
                "category": record.category,
                "importance_score": record.importance_score,
                "urgency_score": record.urgency_score,
                "risk_level": record.risk_level,
                "ai_reasoning": record.ai_reasoning,
                "suggested_action": record.suggested_action,
                "action_items_json": record.action_items_json,
                "attachments_json": record.attachments_json,
            }
            card = self._build_email_card(email_dict)
            self.email_list_column.controls.append(card)

        # Select first email if nothing selected
        if not self.selected_email and emails:
            first = emails[0]
            first_dict = {
                "id": first.id,
                "message_id": first.message_id,
                "thread_id": first.thread_id,
                "sender": first.sender,
                "sender_name": first.sender_name,
                "recipient": first.recipient,
                "subject": first.subject,
                "snippet": first.snippet,
                "body_plain": first.body_plain,
                "received_at": first.received_at,
                "is_unread": first.is_unread,
                "category": first.category,
                "importance_score": first.importance_score,
                "urgency_score": first.urgency_score,
                "risk_level": first.risk_level,
                "ai_reasoning": first.ai_reasoning,
                "suggested_action": first.suggested_action,
                "action_items_json": first.action_items_json,
                "attachments_json": first.attachments_json,
            }
            self._select_email(first_dict)

        if self.page:
            self.page.update()

    def _build_email_card(self, email_data: Dict[str, Any]) -> ft.Container:
        cat = email_data.get("category") or "PERSONAL"
        cat_color = get_category_color(cat)
        importance = email_data.get("importance_score") or 50
        is_selected = self.selected_email and self.selected_email.get("id") == email_data.get("id")

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(cat[:8], size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        bgcolor=cat_color,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    ),
                    ft.Text(email_data.get("sender_name") or email_data.get("sender", "Unknown"), size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"], expand=True, no_wrap=True),
                    ft.Text(f"{importance}/100", size=11, weight=ft.FontWeight.BOLD, color=COLORS["success"] if importance >= 75 else (COLORS["warning"] if importance >= 40 else COLORS["text_muted"])),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(email_data.get("subject") or "(No Subject)", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"], no_wrap=True),
                ft.Text(email_data.get("snippet") or "", size=11, color=COLORS["text_secondary"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=6),
            bgcolor=COLORS["bg_card_hover"] if is_selected else COLORS["bg_card"],
            border=ft.border.all(1, COLORS["primary"] if is_selected else COLORS["border"]),
            border_radius=10,
            padding=12,
            on_click=lambda e, d=email_data: self._select_email(d),
            animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _select_email(self, email_data: Dict[str, Any]) -> None:
        self.selected_email = email_data
        learning_engine.on_user_email_opened(email_data.get("sender", ""))
        self._render_detail_drawer(email_data)
        if self.page:
            self.page.update()

    def _render_detail_drawer(self, data: Dict[str, Any]) -> None:
        cat = data.get("category") or "PERSONAL"
        cat_color = get_category_color(cat)
        importance = data.get("importance_score") or 50
        urgency = data.get("urgency_score") or 50
        reasoning = data.get("ai_reasoning") or "Standard email analyzed."
        action = data.get("suggested_action") or "NONE"

        # Action items parse
        action_items = []
        try:
            if data.get("action_items_json"):
                action_items = json.loads(data["action_items_json"])
        except Exception:
            pass

        actions_column = ft.Column(
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=COLORS["primary"]),
                    ft.Text(item if isinstance(item, str) else item.get("task", ""), size=12, color=COLORS["text_secondary"]),
                ], spacing=6)
                for item in action_items
            ],
            spacing=4,
        )

        self.detail_container.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=14,
            controls=[
                # Header Row
                ft.Row([
                    ft.Container(
                        content=ft.Text(f" {cat} ", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        bgcolor=cat_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                    ),
                    ft.Text(f"From: {data.get('sender_name') or data.get('sender', '')}", size=13, color=COLORS["text_secondary"], expand=True, no_wrap=True),
                ], spacing=10),

                # Subject
                ft.Text(data.get("subject") or "(No Subject)", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),

                # AI Intelligence Box
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=COLORS["primary"]),
                            ft.Text("AI Intelligence Analysis", size=13, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                            ft.Container(expand=True),
                            ft.Text(f"Importance: {importance}/100", size=12, weight=ft.FontWeight.BOLD, color=COLORS["success"] if importance >= 75 else COLORS["warning"]),
                        ]),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Text(f"Rationale: {reasoning}", size=12, color=COLORS["text_primary"]),
                        ft.Row([
                            ft.Text(f"Urgency: {urgency}/100", size=11, color=COLORS["text_secondary"]),
                            ft.Text("•", color=COLORS["text_muted"]),
                            ft.Text(f"Suggested Action: {action}", size=11, color=COLORS["secondary"], weight=ft.FontWeight.BOLD),
                        ], spacing=6),
                        ft.Column([
                            ft.Text("Detected Action Items:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                            actions_column,
                        ], visible=len(action_items) > 0, spacing=4),
                    ], spacing=8),
                    bgcolor=COLORS["bg_main"],
                    border=ft.border.all(1, COLORS["border"]),
                    border_radius=10,
                    padding=14,
                ),

                # Email Body
                ft.Container(
                    content=ft.Text(
                        data.get("body_plain") or data.get("snippet") or "(Empty body)",
                        size=13,
                        color=COLORS["text_secondary"],
                        selectable=True,
                    ),
                    padding=10,
                    bgcolor=COLORS["bg_card_hover"],
                    border_radius=8,
                ),

                # Bottom Action Bar
                ft.Row([
                    ft.ElevatedButton(
                        "AI Reply Assistant",
                        icon=ft.Icons.AUTO_AWESOME,
                        bgcolor=COLORS["primary"],
                        color=COLORS["text_primary"],
                        on_click=lambda e: self._open_reply_dialog(data),
                    ),
                    ft.OutlinedButton(
                        "Archive",
                        icon=ft.Icons.ARCHIVE_OUTLINED,
                        on_click=lambda e: self._archive_email(data),
                    ),
                    ft.OutlinedButton(
                        "Trash",
                        icon=ft.Icons.DELETE_OUTLINE,
                        style=ft.ButtonStyle(color=COLORS["danger"]),
                        on_click=lambda e: self._trash_email(data),
                    ),
                ], spacing=10),
            ],
        )

    def _open_reply_dialog(self, email_data: Dict[str, Any]) -> None:
        dialog = ReplyDialog(page=self.page_ref, email_data=email_data)
        self.page_ref.open(dialog)

    def _archive_email(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.archive_message(email_data["message_id"])
            self.page_ref.open(ft.SnackBar(ft.Text("Email archived"), bgcolor=COLORS["success"]))
            self.load_emails()
        except Exception as e:
            self.page_ref.open(ft.SnackBar(ft.Text(f"Archive: {e}"), bgcolor=COLORS["warning"]))

    def _trash_email(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.trash_message(email_data["message_id"])
            self.page_ref.open(ft.SnackBar(ft.Text("Email moved to trash"), bgcolor=COLORS["danger"]))
            self.load_emails()
        except Exception as e:
            self.page_ref.open(ft.SnackBar(ft.Text(f"Trash: {e}"), bgcolor=COLORS["warning"]))
