"""
GmailAI Assistant - Daily AI Briefings Viewer
"""
import customtkinter as ctk
from typing import List
from resources.styles.theme import FONTS, THEME
from database.repository import repository
from database.models import DailyDigestRecord
from automation.daily_digest import daily_digest_generator
from ui.components.toast import ToastNotification


class DigestCard(ctk.CTkFrame):
    """A single collapsible digest card."""

    def __init__(self, master, digest: DailyDigestRecord, **kwargs):
        super().__init__(
            master,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["dark"]["border"],
            **kwargs,
        )
        self._expanded = False
        self._digest = digest
        self._build(digest)

    def _build(self, d: DailyDigestRecord) -> None:
        # Header row (always visible)
        header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        header.pack(fill="x", padx=20, pady=14)

        # Date label
        ctk.CTkLabel(
            header,
            text=f"\u2139  Briefing — {d.digest_date}",
            font=FONTS["h3"],
            text_color=THEME["dark"]["text_primary"],
        ).pack(side="left")

        # Stats badges row
        stats_frame = ctk.CTkFrame(header, fg_color="transparent")
        stats_frame.pack(side="right", padx=(8, 0))

        badge_data = [
            (f"{d.total_emails} emails", THEME["dark"]["secondary"]),
            (f"{d.important_count} VIP", THEME["dark"]["success"]),
            (f"{d.need_reply_count} replies", THEME["dark"]["warning"]),
            (f"{d.cleanup_suggested_count} cleanup", THEME["dark"]["danger"]),
        ]
        for label_text, color in badge_data:
            ctk.CTkLabel(
                stats_frame,
                text=f" {label_text} ",
                font=FONTS["body_sm_bold"],
                fg_color=color,
                text_color="#FFFFFF",
                corner_radius=6,
                padx=4,
            ).pack(side="left", padx=3)

        # Expand toggle button
        self._toggle_btn = ctk.CTkButton(
            header,
            text="\u25bc",
            width=28,
            height=28,
            font=("Segoe UI", 12),
            fg_color=THEME["dark"]["border"],
            hover_color=THEME["dark"]["bg_card_hover"],
            text_color=THEME["dark"]["text_secondary"],
            command=self._toggle,
        )
        self._toggle_btn.pack(side="right", padx=(12, 0))

        # Bind click on header row too
        header.bind("<Button-1>", lambda e: self._toggle())

        # Separator
        sep = ctk.CTkFrame(self, height=1, fg_color=THEME["dark"]["border"])
        sep.pack(fill="x", padx=16)
        self._sep = sep

        # Content textbox (hidden by default)
        self._txt = ctk.CTkTextbox(
            self,
            fg_color="transparent",
            text_color="#CBD5E1",
            font=FONTS["body"],
            height=160,
            wrap="word",
        )
        self._txt.insert("1.0", d.summary_markdown)
        self._txt.configure(state="disabled")
        # Don't pack yet (collapsed by default)
        self._sep.pack_forget()

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._toggle_btn.configure(text="\u25b2")
            self._sep.pack(fill="x", padx=16)
            self._txt.pack(fill="both", expand=True, padx=20, pady=(8, 16))
        else:
            self._toggle_btn.configure(text="\u25bc")
            self._txt.pack_forget()
            self._sep.pack_forget()


class DailyDigestsView(ctk.CTkFrame):
    """Displays historical daily executive briefings with collapsible cards."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build_ui()
        self.load_digests()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 16))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="\u2606  Daily AI Intelligence Briefings",
            font=FONTS["h1"],
            text_color=THEME["dark"]["text_primary"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Executive morning briefings — click any card to expand the full summary.",
            font=FONTS["body"],
            text_color=THEME["dark"]["text_secondary"],
        ).pack(anchor="w", pady=(2, 0))

        gen_btn = ctk.CTkButton(
            header,
            text="\u2728 Generate Today's Briefing",
            font=FONTS["body_bold"],
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            height=38,
            corner_radius=8,
            command=self._generate_now,
        )
        gen_btn.pack(side="right")

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=28, pady=(0, 16))

    def load_digests(self) -> None:
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        session = repository.get_session()
        try:
            digests = session.query(DailyDigestRecord).order_by(DailyDigestRecord.digest_date.desc()).limit(15).all()
        finally:
            session.close()

        if not digests:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No briefings yet. Click 'Generate Today's Briefing' to create one.",
                font=FONTS["body"],
                text_color=THEME["dark"]["text_muted"],
            ).pack(pady=40)
            return

        for d in digests:
            card = DigestCard(self.scroll_frame, digest=d)
            card.pack(fill="x", pady=6)

    def _generate_now(self) -> None:
        try:
            daily_digest_generator.generate_digest_for_today()
            ToastNotification.show(self.winfo_toplevel(), "Today's briefing generated!", "success")
            self.load_digests()
        except Exception as e:
            ToastNotification.show(self.winfo_toplevel(), f"Failed to generate briefing: {e}", "error")

