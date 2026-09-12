"""
GmailAI Assistant - Smart Cleanup Review Screen for Flet
"""
import flet as ft
import threading
from typing import Any, List, Tuple
from resources.styles.theme import (
    COLORS,
    get_category_color,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
    empty_state,
    pill_badge,
    icon_badge,
)
from database.repository import repository
from database.models import CleanupSuggestion, EmailRecord
from gmail.actions import gmail_actions
from memory.learning import learning_engine
from app.constants import SuggestionStatus, ActionType


from core.events import event_bus, EVT_SUGGESTION_ACTIONED
from core.error_reporter import sanitize_error, format_user_error, BulkOperationResult
import logging

logger = logging.getLogger("GmailAI.ReviewScreen")


class ReviewScreenView(ft.Container):
    """Smart Cleanup review screen with batch selection, confidence indicators, and bulk execution."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.suggestion_items: List[Tuple[CleanupSuggestion, EmailRecord]] = []
        self.selected_suggestion_ids: set = set()
        self._bulk_running = False

        # Batch Header Controls
        self.count_badge_text = ft.Text("0", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF")
        self.count_badge_container = ft.Container(
            content=self.count_badge_text,
            bgcolor=COLORS["primary"],
            padding=padding_symmetric(horizontal=8, vertical=3),
            border_radius=10,
        )
        self.status_count_text = ft.Text("0 suggestions pending review", size=13, color=COLORS["text_secondary"])
        self.select_all_checkbox = ft.Checkbox(
            label="Select All",
            value=False,
            on_change=self._on_select_all_toggle,
        )

        self.bulk_progress = ft.ProgressRing(
            width=18,
            height=18,
            stroke_width=2,
            color=COLORS["primary"],
            visible=False,
        )
        self.bulk_status_text = ft.Text(
            "",
            size=12,
            color=COLORS["text_secondary"],
            visible=False,
        )

        self.bulk_approve_btn = ft.ElevatedButton(
            "Approve Selected (0)",
            icon=ft.Icons.CHECK,
            bgcolor=COLORS["success"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
            on_click=lambda e: self._bulk_approve(),
        )

        self.bulk_dismiss_btn = ft.OutlinedButton(
            "Dismiss Selected",
            icon=ft.Icons.CLOSE,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["danger"]),
            on_click=lambda e: self._bulk_dismiss(),
        )

        # Suggestions List Container (content dynamically swapped between empty state and cards column)
        self.list_container = ft.Container(
            expand=True,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header
                ft.Row([
                    ft.Row([
                        icon_badge(ft.Icons.CLEANING_SERVICES, size=18, pad=8, radius=10),
                        ft.Column([
                            ft.Row([
                                ft.Text("Smart Cleanup Suggestions", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                                self.count_badge_container,
                            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            self.status_count_text,
                        ], spacing=2),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Batch Action Control Bar
                ft.Container(
                    content=ft.Row([
                        self.select_all_checkbox,
                        self.bulk_progress,
                        self.bulk_status_text,
                        ft.Container(expand=True),
                        self.bulk_dismiss_btn,
                        self.bulk_approve_btn,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=COLORS["surface_alt"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=8,
                    padding=padding_symmetric(horizontal=14, vertical=8),
                ),

                # List Container
                self.list_container,
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

    def load_suggestions(self, preserve_selection: bool = False) -> None:
        """Loads pending suggestions from repository."""
        account = repository.get_active_account()
        self.suggestion_items = (
            repository.get_pending_suggestions(limit=100, account_id=account.id)
            if account
            else []
        )
        eligible_ids = {
            s.id for s, _ in self.suggestion_items if self._is_supported_action(s.action_type)
        }
        if preserve_selection:
            self.selected_suggestion_ids.intersection_update(eligible_ids)
        else:
            self.selected_suggestion_ids.clear()
        self.select_all_checkbox.value = bool(eligible_ids) and self.selected_suggestion_ids == eligible_ids

        total = len(self.suggestion_items)
        self.count_badge_text.value = str(total)
        self.status_count_text.value = f"{total} suggestions ready for safe review & cleanup."
        self.bulk_approve_btn.text = f"Approve Selected ({len(self.selected_suggestion_ids)})"
        self.bulk_approve_btn.disabled = self._bulk_running or not self.selected_suggestion_ids
        self.bulk_dismiss_btn.disabled = self._bulk_running or not self.selected_suggestion_ids

        if not self.suggestion_items:
            self.list_container.content = empty_state(
                icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                title="Your Inbox is Clean!",
                subtitle="No pending clutter suggestions at this time. All emails are categorized and clean.",
            )
        else:
            cards = [self._build_suggestion_row(sugg, email) for sugg, email in self.suggestion_items]
            self.list_container.content = ft.Column(
                controls=cards,
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )

        safe_update(self.list_container)
        safe_update(self.count_badge_container)
        safe_update(self.status_count_text)
        safe_update(self.select_all_checkbox)
        safe_update(self.bulk_approve_btn)
        safe_update(self.bulk_dismiss_btn)
        safe_update(self.page_ref)

    def _build_suggestion_row(self, sugg: CleanupSuggestion, email: EmailRecord) -> ft.Container:
        cat = email.category or "PROMOTION"
        cat_color = get_category_color(cat)
        confidence = int((sugg.confidence or 0.85) * 100)
        action_str = sugg.action_type or "ARCHIVE"
        is_supported = self._is_supported_action(action_str)

        chk = ft.Checkbox(
            value=sugg.id in self.selected_suggestion_ids,
            disabled=not is_supported or self._bulk_running,
            on_change=lambda e, sid=sugg.id: self._on_item_toggle(sid, e.control.value),
        )

        confidence_bar = ft.ProgressBar(
            value=confidence / 100.0,
            width=64,
            height=4,
            color=COLORS["success"] if confidence >= 80 else COLORS["warning"],
            bgcolor=COLORS["border"],
            border_radius=2,
        )

        def on_row_hover(e):
            card.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
            safe_update(card)

        card = ft.Container(
            content=ft.Row([
                chk,
                ft.Container(
                    content=ft.Text(cat.upper(), size=9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=cat_color,
                    padding=padding_symmetric(horizontal=8, vertical=3),
                    border_radius=4,
                ),
                ft.Column([
                    ft.Text(email.sender_name or email.sender or "Unknown", size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    ft.Text(email.subject or "(No Subject)", size=12, color=COLORS["text_secondary"], no_wrap=True),
                ], expand=True, spacing=2),
                ft.Column([
                    ft.Text(
                        f"{action_str}" if is_supported else f"Review: {action_str}",
                        size=10,
                        weight=ft.FontWeight.W_600,
                        color=COLORS["success"] if is_supported else COLORS["text_muted"],
                    ),
                    ft.Row([
                        confidence_bar,
                        ft.Text(f"{confidence}%", size=10, color=COLORS["text_muted"]),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.END),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE,
                        icon_color=COLORS["success"],
                        icon_size=18,
                        tooltip="Approve & Execute" if is_supported else "Not available",
                        disabled=not is_supported or self._bulk_running,
                        on_click=lambda e, s=sugg, em=email: self._approve_single(s, em),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CANCEL_OUTLINED,
                        icon_color=COLORS["danger"],
                        icon_size=18,
                        tooltip="Dismiss",
                        on_click=lambda e, s=sugg: self._dismiss_single(s),
                    ),
                ], spacing=0),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, cat_color),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=8,
            padding=padding_symmetric(horizontal=12, vertical=8),
            on_hover=on_row_hover,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        return card

    def _on_item_toggle(self, sid: int, is_checked: bool):
        if is_checked:
            self.selected_suggestion_ids.add(sid)
        else:
            self.selected_suggestion_ids.discard(sid)
        self.select_all_checkbox.value = (len(self.selected_suggestion_ids) == len(self.suggestion_items) and len(self.suggestion_items) > 0)
        self.bulk_approve_btn.text = f"Approve Selected ({len(self.selected_suggestion_ids)})"
        self.bulk_approve_btn.disabled = self._bulk_running or not self.selected_suggestion_ids
        self.bulk_dismiss_btn.disabled = self._bulk_running or not self.selected_suggestion_ids
        safe_update(self.select_all_checkbox)
        safe_update(self.bulk_approve_btn)
        safe_update(self.bulk_dismiss_btn)

    def _on_select_all_toggle(self, e):
        if e.control.value:
            self.selected_suggestion_ids = {
                s.id for s, _ in self.suggestion_items if self._is_supported_action(s.action_type)
            }
        else:
            self.selected_suggestion_ids.clear()
        self.load_suggestions(preserve_selection=True)

    @classmethod
    def _is_supported_action(cls, action_type: Any) -> bool:
        value = cls._action_value(action_type)
        return value == ActionType.ARCHIVE.value or cls._is_trash_action(value)

    @staticmethod
    def _action_value(action_type: Any) -> str:
        return str(getattr(action_type, "value", action_type)).upper()

    @staticmethod
    def _is_trash_action(action_type: Any) -> bool:
        val = getattr(action_type, "value", action_type)
        return str(val).upper() in {"MOVE_TRASH", "UNSUBSCRIBE_AND_TRASH"}

    def _approve_single(self, sugg: CleanupSuggestion, email: EmailRecord):
        if not self._is_supported_action(sugg.action_type):
            self.page_ref.open(
                ft.SnackBar(
                    ft.Text("This suggestion requires manual review and cannot be run as cleanup."),
                    bgcolor=COLORS["warning"],
                )
            )
            return

        if self._is_trash_action(sugg.action_type):
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Move email to trash?"),
                content=ft.Text(
                    f'Confirm moving "{(email.subject or "No Subject")[:80]}" to Gmail Trash. '
                    "This is the required second confirmation."
                ),
            )

            def cancel(e):
                self.page_ref.close(dialog)

            def confirm(e):
                self.page_ref.close(dialog)
                self._execute_single(sugg, email)

            dialog.actions = [
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Move to Trash",
                    icon=ft.Icons.DELETE_OUTLINE,
                    bgcolor=COLORS["danger"],
                    color="#FFFFFF",
                    on_click=confirm,
                ),
            ]
            self.page_ref.open(dialog)
            return

        self._execute_single(sugg, email)

    def _execute_single(self, sugg: CleanupSuggestion, email: EmailRecord):
        try:
            if self._is_trash_action(sugg.action_type):
                gmail_actions.trash_message(
                    email.message_id,
                    category=email.category or "SPAM",
                    sender=email.sender,
                    subject=email.subject or "",
                    user_approved=True,
                    double_confirmed=True,
                )
            elif self._action_value(sugg.action_type) == ActionType.ARCHIVE.value:
                gmail_actions.archive_message(
                    email.message_id,
                    category=email.category or "NEWSLETTER",
                    sender=email.sender,
                    subject=email.subject or "",
                    user_approved=True,
                )
            else:
                raise ValueError(f"Unsupported cleanup action: {sugg.action_type}")

            repository.update_suggestion_status(sugg.id, SuggestionStatus.EXECUTED.value)
            learning_engine.on_user_approved_action(email.sender, sugg.action_type)
            event_bus.publish(EVT_SUGGESTION_ACTIONED, sugg.id)

            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Cleaned: {email.subject[:30]}..."), bgcolor=COLORS["success"]))
            except Exception:
                pass
            self.load_suggestions()
        except Exception as ex:
            logger.error(f"Error approving suggestion: {sanitize_error(ex, 'single_approve')}")
            try:
                msg = format_user_error(ex, "clean email")
                self.page_ref.open(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["danger"]))
            except Exception:
                pass

    def _dismiss_single(self, sugg: CleanupSuggestion):
        repository.update_suggestion_status(sugg.id, SuggestionStatus.REJECTED.value)
        event_bus.publish(EVT_SUGGESTION_ACTIONED, sugg.id)
        try:
            self.page_ref.open(ft.SnackBar(ft.Text("Suggestion dismissed"), bgcolor=COLORS["text_secondary"]))
        except Exception:
            pass
        self.load_suggestions()

    def _bulk_approve(self):
        if self._bulk_running:
            return

        if not self.selected_suggestion_ids and self.select_all_checkbox.value:
            self.selected_suggestion_ids = {
                s.id for s, _ in self.suggestion_items if self._is_supported_action(s.action_type)
            }

        if not self.selected_suggestion_ids:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text("Please select at least one suggestion."), bgcolor=COLORS["warning"]))
            except Exception:
                pass
            return

        selected_items = [
            (sugg, email)
            for sugg, email in self.suggestion_items
            if sugg.id in self.selected_suggestion_ids
        ]
        trash_count = sum(1 for sugg, _ in selected_items if self._is_trash_action(sugg.action_type))
        if trash_count:
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirm bulk cleanup"),
                content=ft.Text(
                    f"This cleanup will move {trash_count} selected email"
                    f"{'s' if trash_count != 1 else ''} to Gmail Trash. Confirm to continue."
                ),
            )

            def cancel(e):
                self.page_ref.close(dialog)

            def confirm(e):
                self.page_ref.close(dialog)
                self._execute_bulk_approve()

            dialog.actions = [
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Confirm Cleanup",
                    icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                    bgcolor=COLORS["danger"],
                    color="#FFFFFF",
                    on_click=confirm,
                ),
            ]
            self.page_ref.open(dialog)
            return

        self._execute_bulk_approve()

    def _execute_bulk_approve(self):
        selected_items = [
            (sugg, email)
            for sugg, email in self.suggestion_items
            if sugg.id in self.selected_suggestion_ids and self._is_supported_action(sugg.action_type)
        ]
        if not selected_items:
            return

        self._set_bulk_running(True, len(selected_items))
        threading.Thread(
            target=self._run_bulk_worker,
            args=(selected_items,),
            name="GmailAICleanupWorker",
            daemon=True,
        ).start()

    def _run_bulk_worker(self, selected_items) -> None:
        try:
            gmail_actions.ensure_authenticated()
        except Exception as ex:
            logger.warning(f"Bulk cleanup requires Gmail reconnection: {sanitize_error(ex, 'auth_check')}")
            try:
                self.page_ref.run_task(self._finish_bulk_auth_error)
            except Exception:
                logger.debug("Could not dispatch bulk authentication error to UI thread.")
            return

        result = BulkOperationResult()
        for sugg, email in selected_items:
            try:
                if self._is_trash_action(sugg.action_type):
                    gmail_actions.trash_message(
                        email.message_id,
                        category=email.category or "SPAM",
                        sender=email.sender,
                        subject=email.subject or "",
                        user_approved=True,
                        double_confirmed=True,
                    )
                elif self._action_value(sugg.action_type) == ActionType.ARCHIVE.value:
                    gmail_actions.archive_message(
                        email.message_id,
                        category=email.category or "NEWSLETTER",
                        sender=email.sender,
                        subject=email.subject or "",
                        user_approved=True,
                    )
                else:
                    raise ValueError(f"Unsupported cleanup action: {sugg.action_type}")
                repository.update_suggestion_status(sugg.id, SuggestionStatus.EXECUTED.value)
                learning_engine.on_user_approved_action(email.sender, sugg.action_type)
                result.record_success(sugg.id)
            except Exception as ex:
                logger.warning(f"Error bulk approving suggestion {sugg.id}: {sanitize_error(ex, 'bulk_approve')}")
                result.record_failure(sugg.id, ex)

        if result.success_count > 0:
            event_bus.publish(EVT_SUGGESTION_ACTIONED, result.success_count)

        try:
            self.page_ref.run_task(self._finish_bulk, result)
        except Exception:
            logger.debug("Could not dispatch bulk completion to UI thread.")

    def _set_bulk_running(self, running: bool, count: int = 0) -> None:
        self._bulk_running = running
        self.bulk_progress.visible = running
        self.bulk_status_text.visible = running
        self.bulk_status_text.value = f"Cleaning {count} email{'s' if count != 1 else ''}..." if running else ""
        self.select_all_checkbox.disabled = running
        self.bulk_approve_btn.disabled = running or not self.selected_suggestion_ids
        self.bulk_dismiss_btn.disabled = running or not self.selected_suggestion_ids
        safe_update(self.bulk_progress)
        safe_update(self.bulk_status_text)
        safe_update(self.select_all_checkbox)
        safe_update(self.bulk_approve_btn)
        safe_update(self.bulk_dismiss_btn)
        safe_update(self.page_ref)

    async def _finish_bulk_auth_error(self) -> None:
        self._set_bulk_running(False)
        self.page_ref.open(
            ft.SnackBar(
                ft.Text("Gmail authorization expired. Reconnect Google, then retry cleanup."),
                bgcolor=COLORS["danger"],
            )
        )

    async def _finish_bulk(self, result: BulkOperationResult) -> None:
        self._set_bulk_running(False)

        # Retain only failed suggestion IDs so user can easily retry
        if result.has_failures:
            self.selected_suggestion_ids = set(result.failed_ids)
            msg_color = COLORS["warning"] if result.success_count > 0 else COLORS["danger"]
        else:
            self.selected_suggestion_ids.clear()
            msg_color = COLORS["success"]

        try:
            self.page_ref.open(
                ft.SnackBar(
                    ft.Text(result.summary_message("cleaned")),
                    bgcolor=msg_color,
                )
            )
        except Exception:
            pass
        self.load_suggestions(preserve_selection=True)

    def _bulk_dismiss(self):
        if self._bulk_running or not self.selected_suggestion_ids:
            return
        dismissed_count = repository.update_suggestions_status(
            list(self.selected_suggestion_ids),
            SuggestionStatus.REJECTED.value,
        )
        event_bus.publish(EVT_SUGGESTION_ACTIONED, dismissed_count)
        try:
            self.page_ref.open(
                ft.SnackBar(
                    ft.Text(f"Dismissed {dismissed_count} suggestion{'s' if dismissed_count != 1 else ''}"),
                    bgcolor=COLORS["text_secondary"],
                )
            )
        except Exception:
            pass
        self.load_suggestions()
