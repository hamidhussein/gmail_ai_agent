"""
GmailAI Assistant - Master Flet Desktop Application Shell
"""
import sys
import logging
import flet as ft
from typing import Dict, Any

from app.config import config_manager
from core.logger import setup_logger
from core.events import (
    event_bus,
    EVT_SYNC_COMPLETED,
    EVT_TOAST_MESSAGE,
    EVT_THEME_CHANGED,
    EVT_ACCOUNT_CHANGED,
    EVT_SUGGESTION_ACTIONED,
)
from database.repository import repository
from database.migrations import seed_demo_data
from automation.scheduler import scheduler
from resources.styles.theme import (
    COLORS,
    set_theme_mode,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
)

from ui.dashboard import DashboardView
from ui.inbox_view import InboxIntelligenceView
from ui.review_screen import ReviewScreenView
from ui.digests_view import DailyDigestsView
from ui.audit_view import AuditLogsView
from ui.settings import SettingsView
from ui.components.google_auth_modal import GoogleAuthDialog

logger = logging.getLogger("GmailAI.Main")


class GmailAIApp:
    """Master Application Controller coordinating navigation, views, background sync, and event bus."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_tab = "dashboard"
        self.views: Dict[str, ft.Container] = {}

        # Set theme (Light mode by default)
        initial_theme = config_manager.config.ui_theme or "light"
        set_theme_mode(initial_theme)

        # Page configuration
        page.title = "GmailAI Assistant — Privacy-First Hybrid AI Platform"
        page.theme_mode = ft.ThemeMode.LIGHT if initial_theme == "light" else ft.ThemeMode.DARK
        page.bgcolor = COLORS["bg_main"]
        page.padding = 0
        page.window.width = 1260
        page.window.height = 840
        page.window.min_width = 1080
        page.window.min_height = 700

        # Ensure demo data if database is empty
        self._init_data_if_needed()

        # Start scheduler
        scheduler.start()
        page.on_disconnect = lambda e: scheduler.stop()

        # Build Sidebar Navigation & Main Container
        self._build_shell()

        # Subscribe to Event Bus
        self._register_events()

        # Initial view
        self.show_view("dashboard")

    def _init_data_if_needed(self) -> None:
        stats = repository.get_inbox_stats()
        if config_manager.config.demo_mode and stats["total_emails"] == 0:
            logger.info("Fresh database detected. Seeding sample demo data...")
            seed_demo_data()

    def _build_shell(self) -> None:
        # Navigation Items
        self.nav_items = [
            ("dashboard", "Dashboard", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD),
            ("inbox", "Intelligence Inbox", ft.Icons.INBOX_OUTLINED, ft.Icons.INBOX),
            ("review", "Smart Cleanup", ft.Icons.CLEANING_SERVICES_OUTLINED, ft.Icons.CLEANING_SERVICES),
            ("digests", "Daily Briefings", ft.Icons.CALENDAR_MONTH_OUTLINED, ft.Icons.CALENDAR_MONTH),
            ("audit", "Audit Logs", ft.Icons.SECURITY_OUTLINED, ft.Icons.SECURITY),
            ("settings", "Settings & AI", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS),
        ]

        self.nav_buttons: Dict[str, ft.Container] = {}
        self.cleanup_badge_text = ft.Text("0", size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF")
        self.cleanup_badge_container = ft.Container(
            content=self.cleanup_badge_text,
            bgcolor=COLORS["danger"],
            padding=padding_symmetric(horizontal=6, vertical=2),
            border_radius=10,
            visible=False,
        )

        self.inbox_badge_text = ft.Text("0", size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF")
        self.inbox_badge_container = ft.Container(
            content=self.inbox_badge_text,
            bgcolor=COLORS["primary"],
            padding=padding_symmetric(horizontal=6, vertical=2),
            border_radius=10,
            visible=False,
        )

        nav_controls = []
        for key, label, icon_outline, icon_filled in self.nav_items:
            badge = None
            if key == "review":
                badge = self.cleanup_badge_container
            elif key == "inbox":
                badge = self.inbox_badge_container
            btn = self._build_nav_btn(key, label, icon_outline, badge)
            self.nav_buttons[key] = btn
            nav_controls.append(btn)

        # Theme Switcher Pill
        is_light = (config_manager.config.ui_theme != "dark")
        self.theme_icon = ft.Icon(
            ft.Icons.DARK_MODE_OUTLINED if is_light else ft.Icons.LIGHT_MODE_OUTLINED,
            size=16,
            color=COLORS["text_secondary"],
        )
        self.theme_label = ft.Text(
            "Switch to Dark" if is_light else "Switch to Light",
            size=12,
            weight=ft.FontWeight.W_500,
            color=COLORS["text_secondary"],
        )

        self.theme_btn = ft.Container(
            content=ft.Row([
                self.theme_icon,
                self.theme_label,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=padding_symmetric(horizontal=14, vertical=9),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=8,
            on_click=lambda e: self.toggle_theme(),
        )

        # User Status Footer Pill / Google Sign In Prompt
        self.user_email_text = ft.Text("Demo Account", size=12, color=COLORS["text_secondary"], no_wrap=True)
        self.online_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=COLORS["success"])

        self.user_footer = ft.Container(
            content=ft.Row([
                self.online_dot,
                self.user_email_text,
                ft.Container(expand=True),
                ft.Icon(ft.Icons.OPEN_IN_NEW, size=14, color=COLORS["text_muted"]),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=padding_symmetric(horizontal=12, vertical=10),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=10,
            tooltip="Click to manage or switch Google account",
            on_click=lambda e: self.open_google_auth_dialog(),
        )

        # Sidebar Container
        self.sidebar = ft.Container(
            width=240,
            bgcolor=COLORS["bg_sidebar"],
            border=border_only(right=ft.BorderSide(1, COLORS["border"])),
            padding=padding_symmetric(horizontal=14, vertical=20),
            content=ft.Column([
                # Brand Logo Header
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.ALL_INCLUSIVE, size=20, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=6,
                        border_radius=8,
                    ),
                    ft.Text("GmailAI", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    ft.Container(
                        content=ft.Text("PRO", size=10, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"]),
                        bgcolor=COLORS["badge_bg"],
                        padding=padding_symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    ),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),

                ft.Container(height=16),

                # Navigation Buttons List
                ft.Column(nav_controls, spacing=6, expand=True),

                # Theme Mode Switcher
                self.theme_btn,
                ft.Container(height=8),

                # Bottom Account Footer
                self.user_footer,
            ], spacing=0, expand=True),
        )

        # Main Content Container
        self.content_area = ft.Container(expand=True)

        # Root Layout
        self.page.add(
            ft.Row([
                self.sidebar,
                self.content_area,
            ], expand=True, spacing=0)
        )

        self._update_badges()

    def _build_nav_btn(self, key: str, label: str, icon_name: str, badge: ft.Container = None) -> ft.Container:
        row_items = [
            ft.Icon(icon_name, size=18, color=COLORS["text_secondary"]),
            ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=COLORS["text_secondary"], expand=True),
        ]
        if badge:
            row_items.append(badge)

        container = ft.Container(
            content=ft.Row(row_items, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            padding=padding_symmetric(horizontal=12, vertical=10),
            border_radius=8,
            on_click=lambda e, k=key: self.show_view(k),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        return container

    def open_google_auth_dialog(self) -> None:
        """Opens the 1-click Google Sign-In dialog modal."""
        dialog = GoogleAuthDialog(page=self.page, on_authenticated=self._on_account_changed)
        try:
            self.page.open(dialog)
        except Exception:
            pass

    def toggle_theme(self) -> None:
        """Switches between Light and Dark mode with live theme token updates."""
        new_theme = "dark" if config_manager.config.ui_theme == "light" else "light"
        config_manager.config.ui_theme = new_theme
        config_manager.save()
        set_theme_mode(new_theme)

        is_light = (new_theme == "light")
        self.page.theme_mode = ft.ThemeMode.LIGHT if is_light else ft.ThemeMode.DARK
        self.page.bgcolor = COLORS["bg_main"]

        self.theme_icon.name = ft.Icons.DARK_MODE_OUTLINED if is_light else ft.Icons.LIGHT_MODE_OUTLINED
        self.theme_label.value = "Switch to Dark" if is_light else "Switch to Light"

        # Update sidebar styling
        self.sidebar.bgcolor = COLORS["bg_sidebar"]
        self.sidebar.border = border_only(right=ft.BorderSide(1, COLORS["border"]))

        # Invalidate views to re-render in new theme palette
        self.views.clear()
        self.show_view(self.current_tab)

    def show_view(self, tab_key: str) -> None:
        """Swaps active view in the main content container with view caching."""
        self.current_tab = tab_key

        # Update sidebar styling
        for key, btn in self.nav_buttons.items():
            is_active = (key == tab_key)
            btn.bgcolor = COLORS["primary"] if is_active else None
            row = btn.content
            row.controls[0].color = "#FFFFFF" if is_active else COLORS["text_secondary"]
            row.controls[1].color = "#FFFFFF" if is_active else COLORS["text_secondary"]

        # Load or retrieve cached view
        if tab_key not in self.views:
            if tab_key == "dashboard":
                view = DashboardView(page=self.page, on_navigate=self.show_view)
            elif tab_key == "inbox":
                view = InboxIntelligenceView(page=self.page)
            elif tab_key == "review":
                view = ReviewScreenView(page=self.page)
            elif tab_key == "digests":
                view = DailyDigestsView(page=self.page)
            elif tab_key == "audit":
                view = AuditLogsView(page=self.page)
            elif tab_key == "settings":
                view = SettingsView(page=self.page)
            else:
                view = DashboardView(page=self.page, on_navigate=self.show_view)

            self.views[tab_key] = view
        else:
            view = self.views[tab_key]
            if hasattr(view, "refresh_data"):
                try:
                    view.refresh_data()
                except Exception as ex:
                    logger.warning(f"Error during refresh_data on view {tab_key}: {ex}")

        self.content_area.content = view
        self._update_badges()
        self.page.update()

    def _update_badges(self) -> None:
        stats = repository.get_inbox_stats()
        cleanup_count = stats.get("cleanup_suggested_emails", 0)

        if cleanup_count > 0:
            self.cleanup_badge_text.value = str(cleanup_count)
            self.cleanup_badge_container.visible = True
        else:
            self.cleanup_badge_container.visible = False

        unread_count = stats.get("unread_emails", 0)
        if unread_count > 0:
            self.inbox_badge_text.value = str(unread_count)
            self.inbox_badge_container.visible = True
        else:
            self.inbox_badge_container.visible = False

        account = repository.get_active_account()
        if account:
            self.user_email_text.value = account.email
            self.online_dot.bgcolor = COLORS["success"]
        else:
            self.user_email_text.value = "Demo Mode (Sign In)"
            self.online_dot.bgcolor = COLORS["warning"]

    def _register_events(self) -> None:
        event_bus.subscribe(EVT_SYNC_COMPLETED, lambda data: self._on_sync_event(data))
        event_bus.subscribe(EVT_SUGGESTION_ACTIONED, lambda data: self._on_sync_event(data))
        event_bus.subscribe(EVT_TOAST_MESSAGE, lambda msg: self._show_toast(str(msg)))
        event_bus.subscribe(EVT_THEME_CHANGED, lambda theme: self._on_theme_event(theme))
        event_bus.subscribe(EVT_ACCOUNT_CHANGED, lambda email: self._on_account_changed(email))

    def _on_account_changed(self, email: str) -> None:
        """Called when a user signs in with Google."""
        logger.info(f"Active account changed to {email}. Refreshing views...")
        self.views.clear()
        self._update_badges()
        self.show_view(self.current_tab)
        # Trigger immediate background sync
        try:
            scheduler.trigger_sync_now()
        except Exception:
            pass

    def _on_theme_event(self, new_theme: str) -> None:
        is_light = (new_theme == "light")
        self.page.theme_mode = ft.ThemeMode.LIGHT if is_light else ft.ThemeMode.DARK
        self.page.bgcolor = COLORS["bg_main"]

        self.theme_icon.name = ft.Icons.DARK_MODE_OUTLINED if is_light else ft.Icons.LIGHT_MODE_OUTLINED
        self.theme_label.value = "Switch to Dark" if is_light else "Switch to Light"

        self.sidebar.bgcolor = COLORS["bg_sidebar"]
        self.sidebar.border = border_only(right=ft.BorderSide(1, COLORS["border"]))

        self.views.clear()
        self.show_view(self.current_tab)

    def _on_sync_event(self, data) -> None:
        self.views.pop("dashboard", None)
        self._update_badges()
        if self.current_tab == "dashboard":
            self.show_view("dashboard")

    def _show_toast(self, message: str) -> None:
        try:
            self.page.open(ft.SnackBar(ft.Text(message), bgcolor=COLORS["primary"]))
            self.page.update()
        except Exception:
            pass


def main(page: ft.Page):
    setup_logger(log_dir=config_manager.log_dir)
    GmailAIApp(page)


if __name__ == "__main__":
    ft.run(main)
