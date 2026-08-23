"""
GmailAI Assistant - Executive Dashboard View
"""
import customtkinter as ctk
from typing import Callable, Dict, Any
from resources.styles.theme import FONTS, THEME
from ui.components.stat_card import StatCard
from ui.components.loading_spinner import LoadingSpinner
from database.repository import repository
from app.config import config_manager
from automation.scheduler import scheduler
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient


class DashboardView(ctk.CTkFrame):
    """Main Dashboard screen displaying inbox health, AI engine status, and quick suggestions."""

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_navigate = on_navigate

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        # Top Header Bar
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=28, pady=(24, 16))

        # Title & Subtitle
        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.pack(side="left")

        self.title_lbl = ctk.CTkLabel(
            title_box,
            text="Executive Dashboard",
            font=FONTS["h1"],
            text_color="#F8FAFC",
            anchor="w",
        )
        self.title_lbl.pack(anchor="w")

        self.account_sub_lbl = ctk.CTkLabel(
            title_box,
            text="Connecting to Gmail...",
            font=FONTS["body_sm"],
            text_color=THEME["dark"]["text_secondary"],
            anchor="w",
        )
        self.account_sub_lbl.pack(anchor="w")

        # Top Right Actions & AI Status Badge
        top_right = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        top_right.pack(side="right")

        self.ai_badge = ctk.CTkLabel(
            top_right,
            text="\uE916  Hybrid AI Active", # Using fluent icon instead of emoji
            font=("Segoe Fluent Icons", 14), # Adjust font for fluent icon mixed with text, or use Segoe UI Symbol
            fg_color=THEME["dark"]["badge_bg"],
            text_color=THEME["dark"]["badge_text"],
            corner_radius=8,
            padx=14,
            pady=8,
        )
        # Fix font to handle icon and text nicely
        self.ai_badge.configure(font=("Segoe UI", 12, "bold"))
        self.ai_badge.pack(side="left", padx=(0, 16))

        # Sync btn + spinner container
        self._sync_container = ctk.CTkFrame(top_right, fg_color="transparent")
        self._sync_container.pack(side="left")

        self.sync_btn = ctk.CTkButton(
            self._sync_container,
            text="  Sync Now",
            font=("Segoe UI", 13, "bold"),
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            width=120,
            height=38,
            corner_radius=8,
            command=self._handle_sync_click,
        )
        self.sync_btn.pack(side="left")

        self._spinner = LoadingSpinner(self._sync_container, size=26, arc_color=THEME["dark"]["primary"])

        # Scrollable Content Area
        self.scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # --- Stat Cards Grid ---
        self.stats_grid = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.stats_grid.pack(fill="x", pady=(0, 16))
        self.stats_grid.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat_col")

        self.card_total = StatCard(self.stats_grid, title="Total Emails", value="0", icon="✉", trend="Managed safely")
        self.card_total.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        self.card_unread = StatCard(self.stats_grid, title="Unread", value="0", icon="●", trend="Needs triage", accent_color=THEME["dark"]["secondary"])
        self.card_unread.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        self.card_important = StatCard(self.stats_grid, title="Priority / VIP", value="0", icon="★", trend="High importance", accent_color=THEME["dark"]["success"])
        self.card_important.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")

        self.card_cleanup = StatCard(self.stats_grid, title="Cleanup Ready", value="0", icon="➡", trend="Promos & Newsletters", accent_color=THEME["dark"]["warning"])
        self.card_cleanup.grid(row=0, column=3, padx=6, pady=6, sticky="nsew")

        # --- AI Suggestions Hero Banner ---
        self.banner_frame = ctk.CTkFrame(
            self.scroll_container,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.banner_frame.pack(fill="x", pady=8)

        banner_inner = ctk.CTkFrame(self.banner_frame, fg_color="transparent")
        banner_inner.pack(fill="x", padx=20, pady=18)

        banner_text_box = ctk.CTkFrame(banner_inner, fg_color="transparent")
        banner_text_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            banner_text_box,
            text="\uE81C  AI Smart Cleanup Opportunities Detected",
            font=("Segoe UI", 20, "bold"),
            text_color=THEME["dark"]["text_primary"],
            anchor="w",
        ).pack(anchor="w")

        self.banner_sub_lbl = ctk.CTkLabel(
            banner_text_box,
            text="AI identified newsletter clutter and promotional emails ready for safe archiving with user review.",
            font=FONTS["body"],
            text_color=THEME["dark"]["text_secondary"],
            anchor="w",
        )
        self.banner_sub_lbl.pack(anchor="w", pady=(6, 0))

        self.review_action_btn = ctk.CTkButton(
            banner_inner,
            text="Review Suggestions \uE72A",
            font=("Segoe UI", 13, "bold"),
            fg_color=THEME["dark"]["success"],
            hover_color="#059669",
            height=40,
            corner_radius=8,
            command=lambda: self.on_navigate("review"),
        )
        self.review_action_btn.pack(side="right", padx=(16, 0))

        # --- Two Column Layout: Daily Executive Briefing & Quick Actions ---
        cols_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        cols_frame.pack(fill="both", expand=True, pady=8)
        cols_frame.grid_columnconfigure(0, weight=3)
        cols_frame.grid_columnconfigure(1, weight=2)

        # Left Column: Daily Briefing Card
        self.briefing_card = ctk.CTkFrame(
            cols_frame,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.briefing_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        brief_header = ctk.CTkFrame(self.briefing_card, fg_color="transparent")
        brief_header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            brief_header,
            text="\uE8EF  Today's AI Executive Briefing",
            font=("Segoe UI", 16, "bold"),
            text_color=THEME["dark"]["text_primary"],
        ).pack(side="left")

        self.briefing_text = ctk.CTkTextbox(
            self.briefing_card,
            fg_color="transparent",
            text_color="#CBD5E1",
            font=FONTS["body"],
            height=180,
            wrap="word",
        )
        self.briefing_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Right Column: Quick Action Center
        self.quick_actions_card = ctk.CTkFrame(
            cols_frame,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.quick_actions_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        qa_header = ctk.CTkFrame(self.quick_actions_card, fg_color="transparent")
        qa_header.pack(fill="x", padx=20, pady=(20, 14))

        ctk.CTkLabel(
            qa_header,
            text="\uE945  Quick Actions",
            font=("Segoe UI", 16, "bold"),
            text_color=THEME["dark"]["text_primary"],
        ).pack(side="left")

        actions_list = [
            ("\uE715  Open Intelligence Inbox", lambda: self.on_navigate("inbox"), THEME["dark"]["primary"]),
            ("\uE71C  Review Smart Cleanup", lambda: self.on_navigate("review"), THEME["dark"]["success"]),
            ("\uE8EF  View All Daily Digests", lambda: self.on_navigate("digests"), THEME["dark"]["secondary"]),
            ("\uE713  Configure AI & Safety", lambda: self.on_navigate("settings"), THEME["dark"]["border"]),
        ]

        for text, cmd, col in actions_list:
            btn = ctk.CTkButton(
                self.quick_actions_card,
                text=text,
                font=("Segoe UI", 13, "bold"),
                anchor="w",
                fg_color=col,
                hover_color=THEME["dark"]["bg_card_hover"],
                height=42,
                corner_radius=8,
                command=cmd,
            )
            btn.pack(fill="x", padx=20, pady=5)

        # Spacer at bottom
        ctk.CTkFrame(self.quick_actions_card, height=12, fg_color="transparent").pack()

        # --- Recent Activity Log Card ---
        self._activity_card = ctk.CTkFrame(
            self.scroll_container,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self._activity_card.pack(fill="x", pady=8)

        act_header = ctk.CTkFrame(self._activity_card, fg_color="transparent")
        act_header.pack(fill="x", padx=20, pady=(18, 10))

        ctk.CTkLabel(
            act_header,
            text="  Recent Activity",
            font=("Segoe UI", 16, "bold"),
            text_color=THEME["dark"]["text_primary"],
        ).pack(side="left")

        self._activity_list_frame = ctk.CTkFrame(self._activity_card, fg_color="transparent")
        self._activity_list_frame.pack(fill="x", padx=20, pady=(0, 16))

    def refresh_data(self) -> None:
        """Reloads stats, account status, and briefing from repository."""
        account = repository.get_active_account()
        if account:
            self.account_sub_lbl.configure(text=f"Connected: {account.email}  |  Last synced: {account.last_synced_at.strftime('%H:%M') if account.last_synced_at else 'Just now'}")
        else:
            self.account_sub_lbl.configure(text="No account connected (Demo Mode active)")

        stats = repository.get_inbox_stats()
        self.card_total.set_value(f"{stats['total_emails']:,}")
        self.card_unread.set_value(f"{stats['unread_emails']:,}")
        self.card_important.set_value(f"{stats['important_emails']:,}")
        self.card_cleanup.set_value(f"{stats['cleanup_suggested_emails']:,}")

        self.banner_sub_lbl.configure(
            text=f"{stats['cleanup_suggested_emails']} clutter items ready for safe review & archive."
        )

        # Refresh Briefing text
        digest = repository.get_latest_daily_digest()
        self.briefing_text.configure(state="normal")
        self.briefing_text.delete("1.0", "end")
        if digest:
            self.briefing_text.insert("1.0", digest.summary_markdown)
        else:
            self.briefing_text.insert("1.0", "Sync your inbox to generate today's AI executive briefing.")
        self.briefing_text.configure(state="disabled")

        # Update AI Engine Status
        ai_mode = config_manager.config.ai_mode
        ollama_ok = LocalOllamaClient(base_url=config_manager.config.ollama_url).is_available()
        openai_ok = CloudOpenAIClient().is_configured()

        if ai_mode == "HYBRID":
            status_text = "  Hybrid AI (Local + Cloud)" if (ollama_ok and openai_ok) else ("  Local Ollama Active" if ollama_ok else "  Cloud AI Active" if openai_ok else "  Heuristic Engine")
        elif ai_mode == "LOCAL_ONLY":
            status_text = "  Local Ollama Active" if ollama_ok else "  Local Offline"
        elif ai_mode == "CLOUD_ONLY":
            status_text = "  OpenAI Cloud Active" if openai_ok else "  Cloud Unset"
        else:
            status_text = "  Heuristic Rule Engine"

        self.ai_badge.configure(text=status_text)

        # Refresh recent activity feed
        self._refresh_activity_feed()

    def _refresh_activity_feed(self) -> None:
        """Updates the Recent Activity card with latest emails."""
        for w in self._activity_list_frame.winfo_children():
            w.destroy()

        recent = repository.get_inbox_emails(limit=5)
        if not recent:
            ctk.CTkLabel(
                self._activity_list_frame,
                text="No emails synced yet. Click Sync Now to fetch your inbox.",
                font=FONTS["body_sm"],
                text_color=THEME["dark"]["text_muted"],
            ).pack(anchor="w", pady=8)
            return

        from resources.styles.theme import get_category_color
        for email in recent:
            row = ctk.CTkFrame(self._activity_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)

            cat = email.category or "PERSONAL"
            cat_color = get_category_color(cat)

            ctk.CTkLabel(
                row,
                text=f" {cat[:4]} ",
                font=FONTS["body_sm_bold"],
                fg_color=cat_color,
                text_color="#FFFFFF",
                corner_radius=4,
                height=18,
            ).pack(side="left", padx=(0, 8))

            subject = (email.subject or "")[:52]
            ctk.CTkLabel(
                row,
                text=subject,
                font=FONTS["body_sm"],
                text_color=THEME["dark"]["text_secondary"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            source_color = THEME["dark"]["success"] if email.ai_source == "LOCAL_OLLAMA" else THEME["dark"]["text_muted"]
            ctk.CTkLabel(
                row,
                text=email.ai_source or "HEURISTIC",
                font=FONTS["body_sm"],
                text_color=source_color,
            ).pack(side="right")

    def _handle_sync_click(self) -> None:
        self.sync_btn.configure(text="  Syncing...", state="disabled")
        self._spinner.pack(side="left", padx=(8, 0))
        self._spinner.start()
        scheduler.run_sync_now_async(on_complete=lambda: self.after(0, self._on_sync_done))

    def _on_sync_done(self) -> None:
        self._spinner.stop()
        self._spinner.pack_forget()
        self.sync_btn.configure(text="  Sync Now", state="normal")
        self.refresh_data()
