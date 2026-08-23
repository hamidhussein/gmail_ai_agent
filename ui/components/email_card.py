"""
GmailAI Assistant - Interactive Email Card Component
"""
import customtkinter as ctk
from typing import Callable, Dict, Any, Optional
from resources.styles.theme import FONTS, THEME, get_category_color


class EmailCard(ctk.CTkFrame):
    """Interactive email row card displaying AI intelligence badges and quick actions."""

    def __init__(
        self,
        master,
        email_data: Dict[str, Any],
        on_click: Callable[[Dict[str, Any]], None],
        on_quick_reply: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_quick_archive: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=THEME["dark"]["border"],
            **kwargs,
        )
        self.email_data = email_data
        self.on_click = on_click
        self.on_quick_reply = on_quick_reply
        self.on_quick_archive = on_quick_archive

        self._build_ui()
        self._bind_click_events()

    def _build_ui(self) -> None:
        category = self.email_data.get("category", "PERSONAL") or "PERSONAL"
        cat_color = get_category_color(category)
        importance = self.email_data.get("importance_score", 50)
        is_unread = self.email_data.get("is_unread", False)

        # Left status indicator bar
        self.indicator = ctk.CTkFrame(
            self,
            width=4,
            fg_color=cat_color if is_unread else "transparent",
            corner_radius=2,
        )
        self.indicator.pack(side="left", fill="y", padx=(4, 12), pady=8)

        # Main Info Area
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(side="left", fill="both", expand=True, padx=4, pady=8)

        # Top row: Sender & Category Badge + Date
        top_row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        top_row.pack(fill="x")

        sender_text = self.email_data.get("sender_name") or self.email_data.get("sender", "Unknown")
        self.sender_label = ctk.CTkLabel(
            top_row,
            text=sender_text,
            font=("Segoe UI", 13, "bold") if is_unread else ("Segoe UI", 13),
            text_color=THEME["dark"]["text_primary"] if is_unread else THEME["dark"]["text_secondary"],
            anchor="w",
        )
        self.sender_label.pack(side="left")

        # Category Badge
        self.cat_badge = ctk.CTkLabel(
            top_row,
            text=f" {category} ",
            font=FONTS["body_sm_bold"],
            fg_color=cat_color,
            text_color="#FFFFFF",
            corner_radius=6,
            height=20,
            padx=4,
        )
        self.cat_badge.pack(side="left", padx=(10, 0))

        # Importance score badge (Using star icon from Fluent/Unicode)
        imp_color = THEME["dark"]["success"] if importance >= 75 else (THEME["dark"]["warning"] if importance >= 40 else THEME["dark"]["text_muted"])
        self.imp_badge = ctk.CTkLabel(
            top_row,
            text=f"\uE734 {importance}/100 ", # \uE734 is star icon
            font=("Segoe UI", 11, "bold"),
            fg_color=THEME["dark"]["badge_bg"],
            text_color=imp_color,
            corner_radius=6,
            height=20,
            padx=4,
        )
        self.imp_badge.pack(side="left", padx=(6, 0))

        # Middle row: Subject
        self.subject_label = ctk.CTkLabel(
            self.info_frame,
            text=self.email_data.get("subject", "(No Subject)"),
            font=("Segoe UI", 14, "bold") if is_unread else ("Segoe UI", 14),
            text_color=THEME["dark"]["text_primary"] if is_unread else "#CBD5E1",
            anchor="w",
        )
        self.subject_label.pack(fill="x", pady=(4, 0))

        # Bottom row: Snippet
        snippet = self.email_data.get("snippet", "")
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        self.snippet_label = ctk.CTkLabel(
            self.info_frame,
            text=snippet,
            font=FONTS["body_sm"],
            text_color=THEME["dark"]["text_secondary"],
            anchor="w",
        )
        self.snippet_label.pack(fill="x")

        # Right Action Buttons
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="right", padx=16, pady=8)

        if self.on_quick_reply:
            self.reply_btn = ctk.CTkButton(
                self.action_frame,
                text="\uE8BD Reply", # Reply icon
                width=75,
                height=30,
                font=("Segoe UI", 12, "bold"),
                fg_color=THEME["dark"]["primary"],
                hover_color=THEME["dark"]["primary_hover"],
                command=lambda: self.on_quick_reply(self.email_data),
            )
            self.reply_btn.pack(side="top", pady=4)

        if self.on_quick_archive:
            self.archive_btn = ctk.CTkButton(
                self.action_frame,
                text="\uE7B8 Archive", # Archive box icon
                width=75,
                height=28,
                font=("Segoe UI", 12),
                fg_color="transparent",
                hover_color=THEME["dark"]["bg_card_hover"],
                text_color=THEME["dark"]["text_secondary"],
                command=lambda: self.on_quick_archive(self.email_data),
            )
            self.archive_btn.pack(side="top", pady=2)

    def _bind_click_events(self) -> None:
        widgets = [self, self.info_frame, self.sender_label, self.subject_label, self.snippet_label]
        for w in widgets:
            w.bind("<Button-1>", lambda e: self.on_click(self.email_data))
            w.bind("<Enter>", lambda e: self.configure(fg_color=THEME["dark"]["bg_card_hover"]))
            w.bind("<Leave>", lambda e: self.configure(fg_color=THEME["dark"]["bg_card"]))
