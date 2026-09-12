"""
GmailAI Assistant - Executive Dashboard View for Flet
"""
import datetime
import threading
import flet as ft
from typing import Callable, Optional
from resources.styles.theme import (
    COLORS,
    get_category_color,
    glass_container,
    section_card,
    pill_badge,
    empty_state,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
    icon_badge,
    status_dot,
)
from ui.components.stat_card import StatCard
from database.repository import repository
from app.config import config_manager
from automation.scheduler import scheduler
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from ai.gemini_model import CloudGeminiClient


class DashboardView(ft.Container):
    """Executive Dashboard with live KPI cards, AI briefing, clutter banner, and activity stream."""

    def __init__(self, page: ft.Page, on_navigate: Optional[Callable[[str], None]] = None, **kwargs):
        self.page_ref = page
        self.on_navigate = on_navigate

        today_str = datetime.date.today().strftime("%A, %B %d, %Y")

        # Header controls
        self.account_sub_text = ft.Text("Connecting to Gmail...", size=13, color=COLORS["text_secondary"])
        self.ai_badge_text = ft.Text("Hybrid AI Active", size=11, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"])
        self.ai_badge_container = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME, size=13, color=COLORS["badge_text"]),
                self.ai_badge_text,
            ], spacing=6, tight=True),
            bgcolor=COLORS["badge_bg"],
            padding=padding_symmetric(horizontal=12, vertical=6),
            border_radius=20,
            border=border_all(1, COLORS["border"]),
        )

        self.sync_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color="#FFFFFF", visible=False)
        self.sync_btn = ft.ElevatedButton(
            content=ft.Row([
                self.sync_spinner,
                ft.Text("Sync Now", weight=ft.FontWeight.BOLD, size=13),
            ], spacing=8, tight=True),
            bgcolor=COLORS["primary"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
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
        self.banner_container = ft.Container(
            content=ft.Row([
                icon_badge(ft.Icons.AUTO_DELETE_OUTLINED, bg=COLORS["warning"], size=18, pad=10, radius=10),
                ft.Column([
                    ft.Text("Smart Cleanup Opportunities", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    self.banner_sub_text,
                ], expand=True, spacing=3),
                ft.OutlinedButton(
                    "Review Suggestions",
                    icon=ft.Icons.ARROW_FORWARD,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        color=COLORS["warning"],
                        side=ft.BorderSide(1, COLORS["warning"]),
                    ),
                    on_click=lambda e: self.on_navigate("review") if self.on_navigate else None,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            bgcolor=COLORS["warning_soft"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["warning"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=12,
            padding=16,
        )

        # Briefing Markdown
        self.briefing_markdown = ft.Markdown(
            value="Sync your inbox to generate today's AI executive briefing.",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        )

        # Recent Activity Column
        self.activity_column = ft.Column(spacing=4)

        # Quick Action cards
        quick_actions = [
            ("Intelligence Inbox", ft.Icons.INBOX, COLORS["primary"], "inbox",
             "AI-categorized & scored emails"),
            ("Smart Cleanup", ft.Icons.CLEANING_SERVICES, COLORS["accent"], "review",
             "Review clutter suggestions"),
            ("Daily Briefings", ft.Icons.CALENDAR_MONTH, COLORS["secondary"], "digests",
             "AI executive summaries"),
            ("Settings & AI", ft.Icons.SETTINGS, COLORS["text_secondary"], "settings",
             "Configure models & safety"),
        ]

        quick_action_controls = []
        for label, icon, color, nav_key, desc in quick_actions:
            def make_qa_hover(c):
                def _h(e):
                    c.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
                    safe_update(c)
                return _h

            qa_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, size=14, color="#FFFFFF"),
                        bgcolor=color,
                        padding=7,
                        border_radius=7,
                    ),
                    ft.Text(label, size=13, weight=ft.FontWeight.W_500, color=COLORS["text_primary"], expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=14, color=COLORS["text_muted"]),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=padding_symmetric(horizontal=12, vertical=9),
                border=border_all(1, COLORS["border"]),
                border_radius=8,
                bgcolor=COLORS["bg_card"],
                on_click=lambda e, k=nav_key: self.on_navigate(k) if self.on_navigate else None,
                animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            qa_card.on_hover = make_qa_hover(qa_card)
            quick_action_controls.append(qa_card)

        # Assemble layout
        content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                # Top Header Bar
                ft.Row([
                    ft.Column([
                        ft.Text("Executive Dashboard", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Row([
                            self.account_sub_text,
                            ft.Text("•", color=COLORS["text_muted"], size=11),
                            ft.Text(today_str, size=11, color=COLORS["text_muted"]),
                        ], spacing=6),
                    ], spacing=3),
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
                                ft.Container(
                                    content=ft.Icon(ft.Icons.SUMMARIZE_OUTLINED, size=14, color="#FFFFFF"),
                                    bgcolor=COLORS["primary"],
                                    padding=6,
                                    border_radius=6,
                                ),
                                ft.Text("Today's AI Executive Briefing", size=15, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ], spacing=10),
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
                                ft.Container(
                                    content=ft.Icon(ft.Icons.BOLT_OUTLINED, size=14, color="#FFFFFF"),
                                    bgcolor=COLORS["warning"],
                                    padding=6,
                                    border_radius=6,
                                ),
                                ft.Text("Quick Actions", size=15, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ], spacing=10),
                            ft.Divider(height=1, color=COLORS["border"]),
                            ft.Column(quick_action_controls, spacing=6),
                        ], spacing=12),
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
                            ft.Container(
                                content=ft.Icon(ft.Icons.TIMELINE_ROUNDED, size=14, color="#FFFFFF"),
                                bgcolor=COLORS["secondary"],
                                padding=6,
                                border_radius=6,
                            ),
                            ft.Text("Recent Activity Stream", size=15, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ], spacing=10),
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
        self._active_account_id = account.id if account else None
        if account:
            last_sync = account.last_synced_at.strftime('%H:%M') if account.last_synced_at else 'Just now'
            self.account_sub_text.value = f"Connected: {account.email}  •  Last synced: {last_sync}"
        else:
            self.account_sub_text.value = "No account connected (Demo Mode active)"

        stats = repository.get_inbox_stats(account_id=self._active_account_id)
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

        # AI Status: Fast non-blocking initial display, background probe
        ai_mode = config_manager.config.ai_mode
        cloud_provider = config_manager.config.cloud_provider.lower()
        if cloud_provider == "gemini":
            cloud_ok = CloudGeminiClient().is_configured()
            cloud_name = "Gemini"
        else:
            cloud_ok = CloudOpenAIClient().is_configured()
            cloud_name = "OpenAI"

        if ai_mode == "HEURISTIC":
            self.ai_badge_text.value = "Heuristic Rule Engine"
        elif ai_mode == "CLOUD_ONLY":
            self.ai_badge_text.value = f"{cloud_name} Cloud Active" if cloud_ok else "Cloud Unset"
        elif ai_mode == "LOCAL_ONLY":
            self.ai_badge_text.value = getattr(self, "_cached_ai_status", "Local Ollama Active")
            self._probe_ai_status_background(ai_mode, cloud_ok, cloud_name)
        else:  # HYBRID
            self.ai_badge_text.value = getattr(self, "_cached_ai_status", f"Hybrid AI (Local + {cloud_name})")
            self._probe_ai_status_background(ai_mode, cloud_ok, cloud_name)

        # Activity list
        self._refresh_activity_feed()
        safe_update(self.page_ref)

    def _probe_ai_status_background(self, ai_mode: str, cloud_ok: bool, cloud_name: str = "Cloud") -> None:
        """Probes Ollama daemon in background thread to keep tab switching instantaneous."""
        def _worker():
            try:
                ollama_ok = LocalOllamaClient(base_url=config_manager.config.ollama_url).is_available()
                if ai_mode == "HYBRID":
                    status_text = (
                        f"Hybrid AI (Local + {cloud_name})" if (ollama_ok and cloud_ok)
                        else ("Local Ollama Active" if ollama_ok else f"{cloud_name} Cloud Active" if cloud_ok else "Heuristic Engine")
                    )
                elif ai_mode == "LOCAL_ONLY":
                    status_text = "Local Ollama Active" if ollama_ok else "Local Offline"
                else:
                    status_text = "Heuristic Rule Engine"

                self._cached_ai_status = status_text
                if self.ai_badge_text.value != status_text:
                    self.ai_badge_text.value = status_text
                    safe_update(self.ai_badge_text)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_activity_feed(self) -> None:
        self.activity_column.controls.clear()
        recent = repository.get_inbox_emails(account_id=getattr(self, '_active_account_id', None), limit=5)
        if not recent:
            self.activity_column.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=COLORS["text_muted"]),
                        ft.Text("No emails synced yet. Click 'Sync Now' above.", size=13, color=COLORS["text_muted"]),
                    ], spacing=8),
                    padding=padding_symmetric(horizontal=8, vertical=12),
                )
            )
            return

        for idx, email in enumerate(recent):
            cat_str = str(getattr(email.category, "value", email.category) or "PERSONAL")
            cat_color = get_category_color(cat_str)
            is_zebra = idx % 2 == 1

            row = ft.Container(
                content=ft.Row([
                    status_dot(cat_color, size=7),
                    ft.Text(
                        email.sender_name or email.sender or "Unknown",
                        size=13, weight=ft.FontWeight.W_600,
                        color=COLORS["text_primary"], width=160, no_wrap=True,
                    ),
                    ft.Text(
                        email.subject or "(No Subject)",
                        size=12, color=COLORS["text_secondary"], expand=True, no_wrap=True,
                    ),
                    ft.Text(
                        cat_str[:8],
                        size=10, weight=ft.FontWeight.W_600,
                        color=cat_color,
                    ),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                padding=padding_symmetric(horizontal=10, vertical=7),
                bgcolor=COLORS["bg_zebra"] if is_zebra else "transparent",
                border_radius=6,
            )
            self.activity_column.controls.append(row)

    def _handle_sync_click(self) -> None:
        self.sync_spinner.visible = True
        self.sync_btn.disabled = True
        safe_update(self.page_ref)

        def _sync_worker_callback():
            self._on_sync_done()

        try:
            scheduler.run_sync_now_async(on_complete=_sync_worker_callback)
        except Exception:
            self.sync_spinner.visible = False
            self.sync_btn.disabled = False
            safe_update(self.page_ref)

    def _on_sync_done(self) -> None:
        async def _apply_sync_done():
            self.sync_spinner.visible = False
            self.sync_btn.disabled = False
            try:
                self.refresh_data()
            except Exception:
                pass
            if self.page_ref:
                try:
                    self.page_ref.open(ft.SnackBar(ft.Text("Gmail sync completed!"), bgcolor=COLORS["success"]))
                except Exception:
                    pass
            safe_update(self.page_ref)

        try:
            self.page_ref.run_task(_apply_sync_done)
        except Exception:
            self.sync_spinner.visible = False
            self.sync_btn.disabled = False
            try:
                self.refresh_data()
            except Exception:
                pass
            safe_update(self.page_ref)
