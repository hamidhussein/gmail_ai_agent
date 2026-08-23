"""
GmailAI Assistant - Smart Cleanup Review Screen
"""
import customtkinter as ctk
from typing import Dict, Any, List, Tuple
from resources.styles.theme import FONTS, THEME, get_category_color
from ui.components.action_dialog import ActionConfirmDialog
from ui.components.toast import ToastNotification
from database.repository import repository
from database.models import CleanupSuggestion, EmailRecord
from gmail.actions import gmail_actions
from memory.learning import learning_engine
from core.security import safety_guard
from app.constants import ActionType, SuggestionStatus
from core.logger import get_logger

logger = get_logger("ReviewScreen")


class ReviewScreenView(ctk.CTkFrame):
    """Safe cleanup suggestion review and batch approval screen."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.suggestion_items: List[Tuple[CleanupSuggestion, EmailRecord]] = []
        self.checkbox_vars: Dict[int, ctk.BooleanVar] = {}

        self._build_ui()
        self.load_suggestions()

    def _build_ui(self) -> None:
        # Header Area
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=28, pady=(24, 16))

        title_box = ctk.CTkFrame(self.header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="\uE71C  Smart Cleanup Suggestions", # Broom/Review icon
            font=("Segoe UI", 24, "bold"),
            text_color=THEME["dark"]["text_primary"],
        ).pack(anchor="w")

        self.subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Review and approve AI-recommended inbox cleanup operations. No emails are modified without your approval.",
            font=FONTS["body"],
            text_color=THEME["dark"]["text_secondary"],
        ).pack(anchor="w", pady=(2, 0))

        # Top Control & Batch Actions Bar
        self.control_bar = ctk.CTkFrame(self, fg_color=THEME["dark"]["bg_card"], corner_radius=10)
        self.control_bar.pack(fill="x", padx=28, pady=(0, 14))

        cb_inner = ctk.CTkFrame(self.control_bar, fg_color="transparent")
        cb_inner.pack(fill="x", padx=16, pady=10)

        self.select_all_btn = ctk.CTkButton(
            cb_inner,
            text="\uE73A Select All", # Checkmark box
            font=("Segoe UI", 12, "bold"),
            fg_color=THEME["dark"]["border"],
            hover_color=THEME["dark"]["bg_card_hover"],
            width=110,
            command=self._toggle_select_all,
        )
        self.select_all_btn.pack(side="left", padx=(0, 8))

        self.reject_btn = ctk.CTkButton(
            cb_inner,
            text="\uE711 Reject Selected", # X icon
            font=("Segoe UI", 12),
            fg_color="transparent",
            hover_color=THEME["dark"]["danger_hover"],
            text_color=THEME["dark"]["danger"],
            border_width=1,
            border_color=THEME["dark"]["danger"],
            width=130,
            command=self._handle_reject_selected,
        )
        self.reject_btn.pack(side="left", padx=(0, 8))

        self.approve_btn = ctk.CTkButton(
            cb_inner,
            text="\uE73E Approve & Execute Selected", # Check icon
            font=("Segoe UI", 13, "bold"),
            fg_color=THEME["dark"]["success"],
            hover_color="#059669",
            width=230,
            command=self._handle_approve_selected,
        )
        self.approve_btn.pack(side="right")

        # Scrollable Suggestions List Container
        self.list_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True, padx=28, pady=(0, 16))

    def refresh_data(self) -> None:
        """Called by view caching."""
        self.load_suggestions()

    def load_suggestions(self) -> None:
        """Loads all pending cleanup suggestions."""
        for w in self.list_container.winfo_children():
            w.destroy()

        self.checkbox_vars.clear()
        self.suggestion_items = repository.get_pending_suggestions(limit=100)

        if not self.suggestion_items:
            empty_box = ctk.CTkFrame(self.list_container, fg_color=THEME["dark"]["bg_card"], corner_radius=12)
            empty_box.pack(fill="x", pady=40, padx=20)

            ctk.CTkLabel(
                empty_box,
                text="\uE73E", # Checkmark icon
                font=("Segoe Fluent Icons", 48),
                text_color=THEME["dark"]["success"],
            ).pack(pady=(24, 6))

            ctk.CTkLabel(
                empty_box,
                text="Your Inbox is Clean!",
                font=("Segoe UI", 20, "bold"),
                text_color=THEME["dark"]["text_primary"],
            ).pack()

            ctk.CTkLabel(
                empty_box,
                text="No pending cleanup suggestions at this time. Great job maintaining inbox zero!",
                font=FONTS["body"],
                text_color=THEME["dark"]["text_secondary"],
            ).pack(pady=(4, 24))
            return

        for sugg, email in self.suggestion_items:
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars[sugg.id] = var

            # Row Card
            row = ctk.CTkFrame(
                self.list_container,
                fg_color=THEME["dark"]["bg_card"],
                corner_radius=12,
                border_width=1,
                border_color=THEME["dark"]["border"],
            )
            row.pack(fill="x", pady=6)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=12)

            # Checkbox
            chk = ctk.CTkCheckBox(
                inner,
                text="",
                variable=var,
                width=24,
                checkbox_width=20,
                checkbox_height=20,
            )
            chk.pack(side="left", padx=(0, 10))

            # Action Badge & Category
            action_color = "#EF4444" if sugg.action_type == "MOVE_TRASH" else "#06B6D4"
            ctk.CTkLabel(
                inner,
                text=f" {sugg.action_type} ",
                font=FONTS["body_sm_bold"],
                fg_color=action_color,
                text_color="#FFFFFF",
                corner_radius=4,
                height=20,
            ).pack(side="left", padx=(0, 8))

            cat_col = get_category_color(sugg.category)
            ctk.CTkLabel(
                inner,
                text=f" {sugg.category} ",
                font=FONTS["body_sm_bold"],
                fg_color=cat_col,
                text_color="#FFFFFF",
                corner_radius=4,
                height=20,
            ).pack(side="left", padx=(0, 12))

            # Email Summary Details
            info_frame = ctk.CTkFrame(inner, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True)

            sender_name = email.sender_name or email.sender
            ctk.CTkLabel(
                info_frame,
                text=f"{sender_name}  •  {email.subject}",
                font=("Segoe UI", 13, "bold"),
                text_color=THEME["dark"]["text_primary"],
                anchor="w",
            ).pack(fill="x")

            ctk.CTkLabel(
                info_frame,
                text=f"Rationale: {sugg.reason or 'Safe cleanup suggested'}",
                font=("Segoe UI", 12),
                text_color=THEME["dark"]["text_secondary"],
                anchor="w",
            ).pack(fill="x")

            # Confidence Badge
            conf_pct = int(sugg.confidence * 100) if sugg.confidence <= 1.0 else int(sugg.confidence)
            ctk.CTkLabel(
                inner,
                text=f"\uE734 {conf_pct}% Confidence", # Star icon
                font=("Segoe UI", 11, "bold"),
                fg_color=THEME["dark"]["badge_bg"],
                text_color=THEME["dark"]["success"] if conf_pct >= 85 else THEME["dark"]["warning"],
                corner_radius=6,
                padx=8,
                pady=6,
            ).pack(side="right", padx=(8, 0))

    def _toggle_select_all(self) -> None:
        all_selected = all(v.get() for v in self.checkbox_vars.values())
        new_state = not all_selected
        for v in self.checkbox_vars.values():
            v.set(new_state)

    def _handle_reject_selected(self) -> None:
        selected_ids = [s_id for s_id, var in self.checkbox_vars.items() if var.get()]
        if not selected_ids:
            ToastNotification.show(self.winfo_toplevel(), "No items selected.", "info")
            return

        for s_id in selected_ids:
            repository.update_suggestion_status(s_id, SuggestionStatus.REJECTED.value)
            # Find sender to train memory
            for sugg, email in self.suggestion_items:
                if sugg.id == s_id:
                    learning_engine.on_user_suggestion_decision(email.sender, was_approved=False)

        ToastNotification.show(self.winfo_toplevel(), f"Rejected {len(selected_ids)} suggestions. AI memory updated.", "success")
        self.load_suggestions()

    def _handle_approve_selected(self) -> None:
        selected_ids = [s_id for s_id, var in self.checkbox_vars.items() if var.get()]
        if not selected_ids:
            ToastNotification.show(self.winfo_toplevel(), "No suggestions selected to approve.", "info")
            return

        # Check if any selected item is destructive (MOVE_TRASH)
        has_destructive = False
        for s_id in selected_ids:
            for sugg, _ in self.suggestion_items:
                if sugg.id == s_id and sugg.action_type == ActionType.MOVE_TRASH.value:
                    has_destructive = True
                    break

        def do_execution(double_confirmed: bool):
            executed_count = 0
            for s_id in selected_ids:
                for sugg, email in self.suggestion_items:
                    if sugg.id == s_id:
                        try:
                            if sugg.action_type == ActionType.MOVE_TRASH.value:
                                gmail_actions.move_to_trash(
                                    message_id=email.message_id,
                                    category=email.category,
                                    sender=email.sender,
                                    subject=email.subject,
                                    user_approved=True,
                                    double_confirmed=double_confirmed,
                                )
                            elif sugg.action_type == ActionType.ARCHIVE.value:
                                gmail_actions.archive(
                                    message_id=email.message_id,
                                    category=email.category,
                                    sender=email.sender,
                                    subject=email.subject,
                                    user_approved=True,
                                )
                            elif sugg.action_type == ActionType.MARK_READ.value:
                                gmail_actions.mark_as_read(
                                    message_id=email.message_id,
                                    sender=email.sender,
                                    subject=email.subject,
                                    user_approved=True,
                                )

                            repository.update_suggestion_status(s_id, SuggestionStatus.EXECUTED.value)
                            learning_engine.on_user_suggestion_decision(email.sender, was_approved=True)
                            executed_count += 1
                        except Exception as e:
                            logger.error(f"Error executing suggestion {s_id}: {e}")

            ToastNotification.show(
                self.winfo_toplevel(),
                f"Successfully executed {executed_count} cleanup actions!",
                "success",
            )
            self.load_suggestions()

        ActionConfirmDialog(
            parent=self.winfo_toplevel(),
            title="Approve Cleanup Batch" if not has_destructive else "Double Confirmation: Cleanup & Deletion",
            message=f"You are about to execute {len(selected_ids)} approved cleanup actions across your Gmail inbox.",
            is_destructive=has_destructive,
            on_confirm=do_execution,
        )
