"""
GmailAI Assistant - Inbox Intelligence Viewer
"""
import json
import customtkinter as ctk
from typing import Dict, Any, List, Optional
from resources.styles.theme import FONTS, THEME, get_category_color
from ui.components.email_card import EmailCard
from ui.components.reply_modal import ReplyModal
from ui.components.action_dialog import ActionConfirmDialog
from ui.components.toast import ToastNotification
from database.repository import repository
from gmail.actions import gmail_actions
from memory.learning import learning_engine
from app.constants import EmailCategory, ActionType


class InboxIntelligenceView(ctk.CTkFrame):
    """Interactive inbox explorer with multi-category filters, AI reports, and reply drawer."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.current_category = "ALL"
        self.search_query = ""
        self.selected_email: Optional[Dict[str, Any]] = None
        self._email_list: List[Any] = []   # current visible email records
        self._selected_index: int = 0       # keyboard nav index

        self._build_ui()
        self.load_emails()
        self._bind_keyboard()

    def _build_ui(self) -> None:
        # Top Filter & Search Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=24, pady=(20, 10))

        # Title
        ctk.CTkLabel(
            self.header_frame,
            text="Inbox Intelligence",
            font=FONTS["h1"],
            text_color="#F8FAFC",
        ).pack(side="left")

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            self.header_frame,
            placeholder_text="\uE721 Search subject, sender, content...", # Fluent search icon
            font=("Segoe UI", 13),
            width=300,
            height=38,
            corner_radius=8,
            fg_color=THEME["dark"]["bg_card"],
            border_color=THEME["dark"]["border"],
        )
        self.search_entry.pack(side="right", padx=(10, 0))
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        # Category Filter Tabs Bar
        self.categories_bar = ctk.CTkScrollableFrame(
            self,
            orientation="horizontal",
            height=42,
            fg_color="transparent",
        )
        self.categories_bar.pack(fill="x", padx=24, pady=(0, 12))

        categories = [
            "ALL", "CLIENT", "WORK", "BANK", "FINANCE", "LEGAL",
            "NEWSLETTER", "PROMOTION", "SOCIAL", "SPAM"
        ]
        self.cat_buttons: Dict[str, ctk.CTkButton] = {}

        for cat in categories:
            is_active = cat == "ALL"
            btn = ctk.CTkButton(
                self.categories_bar,
                text=cat,
                font=FONTS["body_sm_bold"],
                height=28,
                fg_color=THEME["dark"]["primary"] if is_active else THEME["dark"]["bg_card"],
                hover_color=THEME["dark"]["bg_card_hover"],
                text_color="#FFFFFF" if is_active else "#94A3B8",
                corner_radius=6,
                command=lambda c=cat: self._select_category(c),
            )
            btn.pack(side="left", padx=3)
            self.cat_buttons[cat] = btn

        # Main Split Content Area
        self.split_container = ctk.CTkFrame(self, fg_color="transparent")
        self.split_container.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self.split_container.grid_columnconfigure(0, weight=11)
        self.split_container.grid_columnconfigure(1, weight=13)
        self.split_container.grid_rowconfigure(0, weight=1)

        # Left: Email List Scrollable Container
        self.email_list_frame = ctk.CTkScrollableFrame(
            self.split_container,
            fg_color="transparent",
        )
        self.email_list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Right: Email Detail Drawer
        self.detail_card = ctk.CTkFrame(
            self.split_container,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.detail_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_detail_placeholder()

    def _build_detail_placeholder(self) -> None:
        """Initial state when no email is selected."""
        for w in self.detail_card.winfo_children():
            w.destroy()

        center_frame = ctk.CTkFrame(self.detail_card, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            center_frame,
            text="\uE715", # Fluent Mailbox
            font=("Segoe Fluent Icons", 48),
            text_color=THEME["dark"]["text_muted"],
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            center_frame,
            text="Select an email to view AI Analysis",
            font=FONTS["h3"],
            text_color="#94A3B8",
        ).pack()

    def load_emails(self) -> None:
        """Queries repository for emails matching current filters and populates list."""
        for w in self.email_list_frame.winfo_children():
            w.destroy()

        emails = repository.get_inbox_emails(
            category=None if self.current_category == "ALL" else self.current_category,
            search_query=self.search_query if self.search_query else None,
            limit=50,
        )

        if not emails:
            ctk.CTkLabel(
                self.email_list_frame,
                text="No emails match your filter.",
                font=FONTS["body"],
                text_color="#64748B",
            ).pack(pady=40)
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

            card = EmailCard(
                self.email_list_frame,
                email_data=email_dict,
                on_click=self._on_email_selected,
                on_quick_reply=self._open_reply_modal,
                on_quick_archive=self._quick_archive,
            )
            card.pack(fill="x", pady=4)

        self._email_list = emails

        # Select first email automatically if none selected
        if not self.selected_email and emails:
            self._select_email_at_index(0)

    def _bind_keyboard(self) -> None:
        """Bind Up/Down arrow and Enter/Delete for keyboard navigation safely."""
        try:
            top = self.winfo_toplevel()
            if top:
                top.bind("<Up>", lambda e: self._nav_email(-1), add="+")
                top.bind("<Down>", lambda e: self._nav_email(1), add="+")
                top.bind("<Return>", lambda e: self._open_selected_keyboard(), add="+")
                top.bind("<Delete>", lambda e: self._archive_selected_keyboard(), add="+")
        except Exception:
            pass

    def _nav_email(self, direction: int) -> None:
        """Move selection up or down in the email list."""
        try:
            if not self.winfo_ismapped():
                return
        except Exception:
            return
        if not self._email_list:
            return
        new_idx = max(0, min(len(self._email_list) - 1, self._selected_index + direction))
        if new_idx != self._selected_index:
            self._select_email_at_index(new_idx)

    def _select_email_at_index(self, idx: int) -> None:
        """Programmatically selects an email by its list index."""
        if not self._email_list or idx >= len(self._email_list):
            return
        self._selected_index = idx
        record = self._email_list[idx]
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
        self._on_email_selected(email_dict)

    def _open_selected_keyboard(self) -> None:
        """Open reply modal for selected email via Enter key."""
        try:
            if not self.winfo_ismapped():
                return
        except Exception:
            return
        if self.selected_email:
            self._open_reply_modal(self.selected_email)

    def _archive_selected_keyboard(self) -> None:
        """Archive focused email via Delete key."""
        try:
            if not self.winfo_ismapped():
                return
        except Exception:
            return
        if self.selected_email:
            self._quick_archive(self.selected_email)

    def refresh_data(self) -> None:
        """Called by view caching to refresh without full rebuild."""
        self.load_emails()

    def _select_category(self, cat: str) -> None:
        self.current_category = cat
        for c, btn in self.cat_buttons.items():
            if c == cat:
                btn.configure(fg_color=THEME["dark"]["primary"], text_color="#FFFFFF")
            else:
                btn.configure(fg_color=THEME["dark"]["bg_card"], text_color="#94A3B8")
        self.load_emails()

    def _on_search_change(self, event=None) -> None:
        self.search_query = self.search_entry.get().strip()
        self.load_emails()

    def _on_email_selected(self, email_data: Dict[str, Any]) -> None:
        self.selected_email = email_data
        learning_engine.on_user_email_opened(email_data.get("sender", ""))
        self._render_detail_drawer(email_data)

    def _render_detail_drawer(self, data: Dict[str, Any]) -> None:
        """Renders full email details and AI intelligence report on the right."""
        for w in self.detail_card.winfo_children():
            w.destroy()

        scroll_detail = ctk.CTkScrollableFrame(self.detail_card, fg_color="transparent")
        scroll_detail.pack(fill="both", expand=True, padx=16, pady=16)

        # Category and Subject Header
        category = data.get("category", "PERSONAL") or "PERSONAL"
        cat_color = get_category_color(category)

        header_row = ctk.CTkFrame(scroll_detail, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            header_row,
            text=f" {category} ",
            font=FONTS["body_sm_bold"],
            fg_color=cat_color,
            text_color="#FFFFFF",
            corner_radius=4,
            height=20,
        ).pack(side="left")

        sender_text = data.get("sender_name") or data.get("sender", "Unknown")
        ctk.CTkLabel(
            header_row,
            text=f"  From: {sender_text} <{data.get('sender', '')}>",
            font=FONTS["body_sm"],
            text_color=THEME["dark"]["text_secondary"],
        ).pack(side="left")

        ctk.CTkLabel(
            scroll_detail,
            text=data.get("subject", "(No Subject)"),
            font=FONTS["h2"],
            text_color="#F8FAFC",
            anchor="w",
            wraplength=420,
            justify="left",
        ).pack(fill="x", pady=(4, 10))

        # --- AI Intelligence Report Box ---
        report_frame = ctk.CTkFrame(
            scroll_detail,
            fg_color=THEME["dark"]["bg_main"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        report_frame.pack(fill="x", pady=(0, 18))

        rep_header = ctk.CTkFrame(report_frame, fg_color="transparent")
        rep_header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            rep_header,
            text="\uE916  AI Intelligence Report",
            font=("Segoe UI", 13, "bold"),
            text_color=THEME["dark"]["primary"],
        ).pack(side="left")

        importance = data.get("importance_score", 50)
        imp_color = THEME["dark"]["success"] if importance >= 75 else (THEME["dark"]["warning"] if importance >= 40 else THEME["dark"]["text_muted"])
        ctk.CTkLabel(
            rep_header,
            text=f"Importance: {importance}/100",
            font=("Segoe UI", 12, "bold"),
            text_color=imp_color,
        ).pack(side="right")

        # Rationale
        reasoning = data.get("ai_reasoning", "Standard message analyzed.")
        ctk.CTkLabel(
            report_frame,
            text=f"AI Rationale: {reasoning}",
            font=("Segoe UI", 12),
            text_color=THEME["dark"]["text_secondary"],
            wraplength=400,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 12))

        # Extracted Action Items if any
        raw_actions = data.get("action_items_json", "[]")
        try:
            items = json.loads(raw_actions) if isinstance(raw_actions, str) else raw_actions
        except Exception:
            items = []

            ctk.CTkLabel(
                report_frame,
                text="Action Items:",
                font=("Segoe UI", 12, "bold"),
                text_color=THEME["dark"]["text_primary"],
                anchor="w",
            ).pack(fill="x", padx=16, pady=(4, 4))
            for item in items:
                ctk.CTkLabel(
                    report_frame,
                    text=f"  \uE73E {item}", # Small dot icon
                    font=("Segoe UI", 12),
                    text_color=THEME["dark"]["secondary"],
                    anchor="w",
                ).pack(fill="x", padx=16, pady=2)
            ctk.CTkFrame(report_frame, height=12, fg_color="transparent").pack()

        # Action Buttons Toolbar
        action_bar = ctk.CTkFrame(scroll_detail, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 16))

        reply_btn = ctk.CTkButton(
            action_bar,
            text="\uE8BD  Reply Assistant",
            font=("Segoe UI", 13, "bold"),
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            height=36,
            corner_radius=8,
            command=lambda: self._open_reply_modal(data),
        )
        reply_btn.pack(side="left", padx=(0, 8))

        archive_btn = ctk.CTkButton(
            action_bar,
            text="\uE7B8  Archive",
            font=("Segoe UI", 13),
            fg_color=THEME["dark"]["bg_card_hover"],
            hover_color=THEME["dark"]["border"],
            height=36,
            width=90,
            corner_radius=8,
            command=lambda: self._quick_archive(data),
        )
        archive_btn.pack(side="left", padx=(0, 8))

        trash_btn = ctk.CTkButton(
            action_bar,
            text="\uE74D  Move Trash", # Delete icon
            font=("Segoe UI", 13),
            fg_color=THEME["dark"]["danger"],
            hover_color=THEME["dark"]["danger_hover"],
            height=36,
            width=110,
            corner_radius=8,
            command=lambda: self._confirm_trash(data),
        )
        trash_btn.pack(side="left")

        # Full Body Content View
        ctk.CTkLabel(
            scroll_detail,
            text="Email Message:",
            font=FONTS["body_bold"],
            text_color="#F8FAFC",
            anchor="w",
        ).pack(fill="x", pady=(8, 4))

        body_box = ctk.CTkTextbox(
            scroll_detail,
            fg_color=THEME["dark"]["bg_main"],
            text_color=THEME["dark"]["text_primary"],
            font=("Segoe UI", 12),
            height=280,
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        body_box.insert("1.0", data.get("body_plain", ""))
        body_box.configure(state="disabled")
        body_box.pack(fill="both", expand=True)

    def _open_reply_modal(self, email_data: Dict[str, Any]) -> None:
        ReplyModal(self.winfo_toplevel(), email_data=email_data, on_draft_created=lambda msg_id: ToastNotification.show(self.winfo_toplevel(), "Draft created successfully!", "success"))

    def _quick_archive(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.archive(
                message_id=email_data["message_id"],
                category=email_data.get("category", "PROMOTION"),
                sender=email_data.get("sender", ""),
                subject=email_data.get("subject", ""),
                user_approved=True,
            )
            ToastNotification.show(self.winfo_toplevel(), "Email archived safely.", "success")
            self.load_emails()
        except Exception as e:
            ToastNotification.show(self.winfo_toplevel(), f"Archive failed: {e}", "error")

    def _confirm_trash(self, email_data: Dict[str, Any]) -> None:
        def on_confirmed(double_checked: bool):
            try:
                gmail_actions.move_to_trash(
                    message_id=email_data["message_id"],
                    category=email_data.get("category", "SPAM"),
                    sender=email_data.get("sender", ""),
                    subject=email_data.get("subject", ""),
                    user_approved=True,
                    double_confirmed=double_checked,
                )
                ToastNotification.show(self.winfo_toplevel(), "Email moved to Trash.", "success")
                self.load_emails()
                self._build_detail_placeholder()
            except Exception as e:
                ToastNotification.show(self.winfo_toplevel(), f"Action blocked: {e}", "error")

        ActionConfirmDialog(
            parent=self.winfo_toplevel(),
            title="Confirm Move to Trash",
            message=f"Are you sure you want to move '{email_data.get('subject')}' from {email_data.get('sender')} to Trash?",
            is_destructive=True,
            on_confirm=on_confirmed,
        )
