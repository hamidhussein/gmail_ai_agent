"""
GmailAI Assistant - Executive Dashboard View for Flet
"""
import flet as ft
from typing import Callable
from resources.styles.theme import (
    COLORS,
    get_category_color,
    glass_container,
    border_all,
    padding_all,
    padding_symmetric,
)
from ui.components.stat_card import StatCard
from database.repository import repository
from app.config import config_manager
from automation.scheduler import scheduler
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient


class DashboardView(ft.Container):
    """Executive Dashboard with live KPI cards, AI briefing, clutter banner, and activity stream."""

    def __init__(self, page: ft.Page, on_navigate: Callable[[str], None], **kwargs):
        self.page_ref = page
        self.on_navigate = on_navigate

        # Header controls
        self.account_sub_text = ft.Text("Connecting to Gmail...", size=13, color=COLORS["text_secondary"])
        self.ai_badge_text = ft.Text("Hybrid AI Active", size=12, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"])
        self.ai_badge_container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME, size=14, color=COLORS["badge_text"]),
                self.ai_badge_text,
            ], spacing=6, tight=True),
            bgcolor=COLORS["badge_bg"],
            padding=padding_symmetric(horizontal=12, vertical=6),
            border_radius=8,
            border=border_all(1, "#312E81"),
        )

        self.sync_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLORS["text_primary"], visible=False)
        self.sync_btn = ft.ElevatedButton(
            content=ft.Row([
                self.sync_spinner,
                ft.Text("Sync Now", weight=ft.FontWeight.BOLD, size=13),
            ], spacing=8, tight=True),
            bgcolor=COLORS["primary"],
            color=COLORS["text_primary"],
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self._handle_sync_click(),
        )

        # Stat cards
        self.card_total = StatCard(title="Total Emails", value="0", icon=ft.Icons.MARK_EMAIL_READ_OUTLINED, trend="Managed safely", accent_color=COLORS["primary"])
        self.card_unread = StatCard(title="Unread", value="0", icon=ft.Icons.MARK_EMAIL_UNREAD_OUTLINED, trend="Needs triage", accent_color=COLORS["secondary"])
        self.card_important = StatCard(title="Priority / VIP", value="0", icon=ft.Icons.STAR_BORDER_ROUNDED, trend="High importance", accent_color=COLORS["success"])
        self.card_cleanup = StatCard(title="Cleanup Ready", value="0", icon=ft.Icons.CLEANING_SERVICES_OUTLINED, trend="Clutter detected", accent_color=COLORS["warning"])

        # Clutter Opportunity Banner
        self.banner_sub_text = ft.Text(
            "AI identified newsletter clutter and promotional emails ready for safe review.",
            size=13,
            color=COLORS["text_secondary"],
        )
        self.banner_container = glass_container(
            content=ft.Row([
                ft.Icon(ft.Icons.AUTO_DELETE_OUTLINED, size=32, color=COLORS["warning"]),
                ft.Column([
                    ft.Text("AI Smart Cleanup Opportunities Detected", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    self.banner_sub_text,
                ], expand=True, spacing=4),
                ft.ElevatedButton(
                    "Review Suggestions",
                    icon=ft.Icons.ARROW_FORWARD,
                    bgcolor=COLORS["success"],
                    color=COLORS["text_primary"],
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: self.on_navigate("review"),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )

        # Briefing Markdown
        self.briefing_markdown = ft.Markdown(
            value="Sync your inbox to generate today's AI executive briefing.",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        )

        # Recent Activity Column
        self.activity_column = ft.Column(spacing=8)

        # Assemble layout
        content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=18,
            controls=[
                # Top Header Bar
                ft.Row([
                    ft.Column([
                        ft.Text("Executive Dashboard", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        self.account_sub_text,
                    ], spacing=2),
                    ft.Row([
                        self.ai_badge_container,
                        self.sync_btn,
                    ], spacing=12),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Stat Cards Row
                ft.Row([
                    self.card_total,
                    self.card_unread,
                    self.card_important,
                    self.card_cleanup,
                ], spacing=12),

                # Hero Clutter Banner
                self.banner_container,

                # Two-Column Layout: Briefing & Quick Actions
                ft.Row([
                    # Left: Today's Briefing
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.SUMMARIZE_OUTLINED, size=18, color=COLORS["primary"]),
                                ft.Text("Today's AI Executive Briefing", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ], spacing=8),
                            ft.Divider(height=1, color=COLORS["border"]),
                            self.briefing_markdown,
                        ], spacing=12),
                        bgcolor=COLORS["bg_card"],
                        border=border_all(1, COLORS["border"]),
                        border_radius=12,
                        padding=20,
                        expand=3,
                    ),

                    # Right: Quick Action Hub
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.BOLT_OUTLINED, size=18, color=COLORS["warning"]),
                                ft.Text("Quick Actions", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ], spacing=8),
                            ft.Divider(height=1, color=COLORS["border"]),
                            ft.OutlinedButton("Open Intelligence Inbox", icon=ft.Icons.INBOX, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.on_navigate("inbox")),
                            ft.OutlinedButton("Review Smart Cleanup", icon=ft.Icons.CLEANING_SERVICES, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.on_navigate("review")),
                            ft.OutlinedButton("View Daily AI Digests", icon=ft.Icons.CALENDAR_MONTH, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.on_navigate("digests")),
                            ft.OutlinedButton("Configure AI & Safety", icon=ft.Icons.SETTINGS, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.on_navigate("settings")),
                        ], spacing=10),
                        bgcolor=COLORS["bg_card"],
                        border=border_all(1, COLORS["border"]),
                        border_radius=12,
                        padding=20,
                        expand=2,
                    ),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, spacing=14),

                # Bottom: Recent Live Activity Log
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.TIMELINE_ROUNDED, size=18, color=COLORS["secondary"]),
                            ft.Text("Recent Activity Stream", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ], spacing=8),
                        ft.Divider(height=1, color=COLORS["border"]),
                        self.activity_column,
                    ], spacing=12),
                    bgcolor=COLORS["bg_card"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=12,
                    padding=20,
                ),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )

        self.refresh_data()

    def refresh_data(self) -> None:
        """Reloads stats, active account details, latest briefing, and activity stream."""
        account = repository.get_active_account()
        if account:
            last_sync = account.last_synced_at.strftime('%H:%M') if account.last_synced_at else 'Just now'
            self.account_sub_text.value = f"Connected: {account.email}  •  Last synced: {last_sync}"
        else:
            self.account_sub_text.value = "No account connected (Demo Mode active)"

        stats = repository.get_inbox_stats()
        self.card_total.set_value(f"{stats['total_emails']:,}")
        self.card_unread.set_value(f"{stats['unread_emails']:,}")
        self.card_important.set_value(f"{stats['important_emails']:,}")
        self.card_cleanup.set_value(f"{stats['cleanup_suggested_emails']:,}")

        self.banner_sub_text.value = f"{stats['cleanup_suggested_emails']} clutter items ready for safe review & archive."

        # Digest
        digest = repository.get_latest_daily_digest()
        if digest:
            self.briefing_markdown.value = digest.summary_markdown
        else:
            self.briefing_markdown.value = "Sync your inbox to generate today's AI executive briefing."

        # AI Status
        ai_mode = config_manager.config.ai_mode
        ollama_ok = LocalOllamaClient(base_url=config_manager.config.ollama_url).is_available()
        openai_ok = CloudOpenAIClient().is_configured()

        if ai_mode == "HYBRID":
            status_text = "Hybrid AI (Local + Cloud)" if (ollama_ok and openai_ok) else ("Local Ollama Active" if ollama_ok else "Cloud AI Active" if openai_ok else "Heuristic Engine")
        elif ai_mode == "LOCAL_ONLY":
            status_text = "Local Ollama Active" if ollama_ok else "Local Offline"
        elif ai_mode == "CLOUD_ONLY":
            status_text = "OpenAI Cloud Active" if openai_ok else "Cloud Unset"
        else:
            status_text = "Heuristic Rule Engine"

        self.ai_badge_text.value = status_text

        # Activity list
        self._refresh_activity_feed()

        if self.page:
            self.page.update()

    def _refresh_activity_feed(self) -> None:
        self.activity_column.controls.clear()
        recent = repository.get_inbox_emails(limit=5)
        if not recent:
            self.activity_column.controls.append(
                ft.Text("No emails synced yet. Click 'Sync Now' above.", size=13, color=COLORS["text_muted"])
            )
            return

        for email in recent:
            cat = email.category or "PERSONAL"
            cat_color = get_category_color(cat)
            source_color = COLORS["success"] if email.ai_source == "LOCAL_OLLAMA" else COLORS["text_muted"]

            row = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(cat[:8], size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        bgcolor=cat_color,
                        padding=padding_symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                    ),
                    ft.Text(email.sender_name or email.sender or "Unknown", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"], width=180, no_wrap=True),
                    ft.Text(email.subject or "(No Subject)", size=13, color=COLORS["text_secondary"], expand=True, no_wrap=True),
                    ft.Text(email.ai_source or "HEURISTIC", size=11, color=source_color, weight=ft.FontWeight.W_500),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                padding=padding_symmetric(vertical=4),
            )
            self.activity_column.controls.append(row)

    def _handle_sync_click(self) -> None:
        self.sync_spinner.visible = True
        self.sync_btn.disabled = True
        if self.page:
            self.page.update()

        scheduler.run_sync_now_async(on_complete=lambda: self._on_sync_done())

    def _on_sync_done(self) -> None:
        self.sync_spinner.visible = False
        self.sync_btn.disabled = False
        self.refresh_data()
        if self.page:
            self.page.open(ft.SnackBar(ft.Text("Gmail sync completed!"), bgcolor=COLORS["success"]))
            self.page.update()
