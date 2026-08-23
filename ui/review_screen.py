"""
GmailAI Assistant - Smart Cleanup Review Screen for Flet
"""
import flet as ft
from typing import List, Tuple
from resources.styles.theme import (
    COLORS,
    get_category_color,
    border_all,
    padding_all,
    padding_symmetric,
)
from database.repository import repository
from database.models import CleanupSuggestion, EmailRecord
from gmail.actions import gmail_actions
from memory.learning import learning_engine
from app.constants import SuggestionStatus, ActionType


class ReviewScreenView(ft.Container):
    """Smart Cleanup review screen with batch selection, confidence indicators, and bulk execution."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.suggestion_items: List[Tuple[CleanupSuggestion, EmailRecord]] = []
        self.selected_suggestion_ids: set = set()

        # Batch Header Controls
        self.status_count_text = ft.Text("0 suggestions pending review", size=13, color=COLORS["text_secondary"])
        self.select_all_checkbox = ft.Checkbox(
            label="Select All",
            value=True,
            on_change=self._on_select_all_toggle,
        )

        self.bulk_approve_btn = ft.ElevatedButton(
            "Approve Selected (0)",
            icon=ft.Icons.CHECK,
            bgcolor=COLORS["success"],
            color=COLORS["text_primary"],
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self._bulk_approve(),
        )

        self.bulk_dismiss_btn = ft.OutlinedButton(
            "Dismiss Selected",
            icon=ft.Icons.CLOSE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["danger"]),
            on_click=lambda e: self._bulk_dismiss(),
        )

        # Suggestions Card Column
        self.suggestions_column = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header
                ft.Row([
                    ft.Column([
                        ft.Text("Smart Cleanup Suggestions", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        self.status_count_text,
                    ], spacing=2),
                ]),

                # Batch Action Control Bar
                ft.Container(
                    content=ft.Row([
                        self.select_all_checkbox,
                        ft.Container(expand=True),
                        self.bulk_dismiss_btn,
                        self.bulk_approve_btn,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=COLORS["bg_card"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                    padding=padding_symmetric(horizontal=16, vertical=10),
                ),

                # List Container
                ft.Container(
                    content=self.suggestions_column,
                    expand=True,
                ),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )

        self.load_suggestions()

    def refresh_data(self) -> None:
        """Called upon view activation."""
        self.load_suggestions()

    def load_suggestions(self) -> None:
        """Loads pending suggestions from repository."""
        self.suggestions_column.controls.clear()
        self.suggestion_items = repository.get_pending_suggestions()
        self.selected_suggestion_ids = {s.id for s, _ in self.suggestion_items}

        total = len(self.suggestion_items)
        self.status_count_text.value = f"{total} suggestions ready for safe review & cleanup."
        self.bulk_approve_btn.text = f"Approve Selected ({len(self.selected_suggestion_ids)})"

        if not self.suggestion_items:
            self.suggestions_column.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=54, color=COLORS["success"]),
                        ft.Text("Your Inbox is Clean!", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("No pending clutter suggestions at this time.", size=13, color=COLORS["text_secondary"]),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    alignment=ft.alignment.center,
                    padding=60,
                )
            )
            if self.page:
                self.page.update()
            return

        for sugg, email in self.suggestion_items:
            card = self._build_suggestion_row(sugg, email)
            self.suggestions_column.controls.append(card)

        if self.page:
            self.page.update()

    def _build_suggestion_row(self, sugg: CleanupSuggestion, email: EmailRecord) -> ft.Container:
        cat = email.category or "PROMOTION"
        cat_color = get_category_color(cat)
        confidence = int((sugg.confidence or 0.85) * 100)
        action_str = sugg.action_type or "ARCHIVE"

        chk = ft.Checkbox(
            value=sugg.id in self.selected_suggestion_ids,
            on_change=lambda e, sid=sugg.id: self._on_item_toggle(sid, e.control.value),
        )

        return ft.Container(
            content=ft.Row([
                chk,
                ft.Container(
                    content=ft.Text(cat[:8], size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=cat_color,
                    padding=padding_symmetric(horizontal=8, vertical=4),
                    border_radius=4,
                ),
                ft.Column([
                    ft.Text(email.sender_name or email.sender or "Unknown", size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    ft.Text(email.subject or "(No Subject)", size=12, color=COLORS["text_secondary"], no_wrap=True),
                ], expand=True, spacing=2),
                ft.Column([
                    ft.Text(f"Action: {action_str}", size=12, weight=ft.FontWeight.BOLD, color=COLORS["warning"]),
                    ft.Text(f"Confidence: {confidence}%", size=11, color=COLORS["text_muted"]),
                ], spacing=2),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.CHECK,
                        icon_color=COLORS["success"],
                        tooltip="Approve & Execute",
                        on_click=lambda e, s=sugg, em=email: self._approve_single(s, em),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_color=COLORS["danger"],
                        tooltip="Dismiss",
                        on_click=lambda e, s=sugg: self._dismiss_single(s),
                    ),
                ], spacing=4),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=10,
            padding=padding_symmetric(horizontal=14, vertical=10),
        )

    def _on_item_toggle(self, sid: int, is_checked: bool):
        if is_checked:
            self.selected_suggestion_ids.add(sid)
        else:
            self.selected_suggestion_ids.discard(sid)
        self.bulk_approve_btn.text = f"Approve Selected ({len(self.selected_suggestion_ids)})"
        if self.page:
            self.bulk_approve_btn.update()

    def _on_select_all_toggle(self, e):
        if e.control.value:
            self.selected_suggestion_ids = {s.id for s, _ in self.suggestion_items}
        else:
            self.selected_suggestion_ids.clear()
        self.load_suggestions()

    def _approve_single(self, sugg: CleanupSuggestion, email: EmailRecord):
        try:
            if sugg.action_type in (ActionType.MOVE_TRASH.value, ActionType.UNSUBSCRIBE_AND_TRASH.value, "MOVE_TRASH", "UNSUBSCRIBE_AND_TRASH"):
                gmail_actions.trash_message(email.message_id)
            else:
                gmail_actions.archive_message(email.message_id)

            repository.update_suggestion_status(sugg.id, SuggestionStatus.EXECUTED.value)
            learning_engine.on_user_approved_action(email.sender, sugg.action_type)
            if self.page:
                self.page.open(ft.SnackBar(ft.Text(f"Cleaned: {email.subject[:30]}..."), bgcolor=COLORS["success"]))
            self.load_suggestions()
        except Exception as ex:
            if self.page:
                self.page.open(ft.SnackBar(ft.Text(f"Error: {ex}"), bgcolor=COLORS["danger"]))

    def _dismiss_single(self, sugg: CleanupSuggestion):
        repository.update_suggestion_status(sugg.id, SuggestionStatus.REJECTED.value)
        if self.page:
            self.page.open(ft.SnackBar(ft.Text("Suggestion dismissed"), bgcolor=COLORS["text_secondary"]))
        self.load_suggestions()

    def _bulk_approve(self):
        if not self.selected_suggestion_ids:
            return

        approved_count = 0
        for sugg, email in self.suggestion_items:
            if sugg.id in self.selected_suggestion_ids:
                try:
                    if sugg.action_type in (ActionType.MOVE_TRASH.value, ActionType.UNSUBSCRIBE_AND_TRASH.value, "MOVE_TRASH", "UNSUBSCRIBE_AND_TRASH"):
                        gmail_actions.trash_message(email.message_id)
                    else:
                        gmail_actions.archive_message(email.message_id)
                    repository.update_suggestion_status(sugg.id, SuggestionStatus.EXECUTED.value)
                    approved_count += 1
                except Exception:
                    pass

        if self.page:
            self.page.open(ft.SnackBar(ft.Text(f"Successfully processed {approved_count} emails!"), bgcolor=COLORS["success"]))
        self.load_suggestions()

    def _bulk_dismiss(self):
        for sid in self.selected_suggestion_ids:
            repository.update_suggestion_status(sid, SuggestionStatus.REJECTED.value)
        if self.page:
            self.page.open(ft.SnackBar(ft.Text("Dismissed selected suggestions"), bgcolor=COLORS["text_secondary"]))
        self.load_suggestions()
