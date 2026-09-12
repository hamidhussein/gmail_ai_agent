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
    EVT_AUTH_REQUIRED,
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
    safe_update,
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
        self._apply_page_theme()
        page.bgcolor = COLORS["bg_main"]
        page.padding = 0
        page.window.width = 1280
        page.window.height = 860
        page.window.min_width = 1100
        page.window.min_height = 720

        # Ensure demo data if database is empty
        self._init_data_if_needed()

        # Build Sidebar Navigation & Main Container
        self._build_shell()

        # Subscribe to Event Bus
        self._register_events()

        # Start background work only after UI event handlers are ready.
        scheduler.start()
        page.on_disconnect = lambda e: scheduler.stop()

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

        def on_theme_hover(e):
            self.theme_btn.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
            safe_update(self.theme_btn)

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
            on_hover=on_theme_hover,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        # User Status Footer Pill / Google Sign In Prompt
        self.user_email_text = ft.Text("Demo Account", size=12, color=COLORS["text_secondary"], no_wrap=True)
        self.online_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=COLORS["success"])

        def on_footer_hover(e):
            self.user_footer.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
            safe_update(self.user_footer)

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
            on_hover=on_footer_hover,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        # Sidebar Container
        self.sidebar = ft.Container(
            width=220,
            bgcolor=COLORS["bg_sidebar"],
            border=border_only(right=ft.BorderSide(1, COLORS["border"])),
            padding=padding_symmetric(horizontal=14, vertical=20),
            content=ft.Column([
                # Brand Logo Header
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.ALL_INCLUSIVE, size=20, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=7,
                        border_radius=10,
                        shadow=ft.BoxShadow(spread_radius=0, blur_radius=6, color=COLORS["primary"] + "40", offset=ft.Offset(0, 2)),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text("GmailAI", size=17, weight=ft.FontWeight.BOLD, color=COLORS["sidebar_text"]),
                            ft.Container(
                                content=ft.Text("PRO", size=9, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                                bgcolor=COLORS["badge_bg"],
                                border=border_all(1, COLORS["primary"] + "40"),
                                padding=padding_symmetric(horizontal=5, vertical=1),
                                border_radius=4,
                            ),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text("Autonomous Intelligence", size=10, color=COLORS["sidebar_muted"]),
                    ], spacing=1),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),

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
            ft.Icon(icon_name, size=18, color=COLORS["sidebar_muted"]),
            ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=COLORS["sidebar_muted"], expand=True),
        ]
        if badge:
            row_items.append(badge)

        def on_nav_hover(e):
            if key != self.current_tab:
                container.bgcolor = COLORS["sidebar_hover"] if e.data == "true" else None
                safe_update(container)

        container = ft.Container(
            content=ft.Row(row_items, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            padding=padding_symmetric(horizontal=10, vertical=9),
            border_radius=8,
            on_click=lambda e, k=key: self.show_view(k),
            on_hover=on_nav_hover,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        return container

    def open_google_auth_dialog(self, reason: str = "", email: str = "") -> None:
        """Opens the 1-click Google Sign-In dialog modal."""
        dialog = GoogleAuthDialog(
            page=self.page,
            reason=reason,
            account_email=email,
        )
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
        self._apply_page_theme()
        self.page.bgcolor = COLORS["bg_main"]

        self.theme_icon.name = ft.Icons.DARK_MODE_OUTLINED if is_light else ft.Icons.LIGHT_MODE_OUTLINED
        self.theme_label.value = "Switch to Dark" if is_light else "Switch to Light"

        # Update sidebar styling
        self.sidebar.bgcolor = COLORS["bg_sidebar"]
        self.sidebar.border = border_only(right=ft.BorderSide(1, COLORS["border"]))
        self.theme_btn.bgcolor = COLORS["bg_card"]
        self.theme_btn.border = border_all(1, COLORS["border"])
        self.user_footer.bgcolor = COLORS["bg_card"]
        self.user_footer.border = border_all(1, COLORS["border"])
        self.theme_icon.color = COLORS["text_secondary"]
        self.theme_label.color = COLORS["text_secondary"]
        self.user_email_text.color = COLORS["text_secondary"]

        # Invalidate views to re-render in new theme palette
        self.views.clear()
        self.show_view(self.current_tab)

    def show_view(self, tab_key: str) -> None:
        """Swaps active view in the main content container with view caching."""
        self.current_tab = tab_key

        # Update sidebar styling and filled/outline icons
        for key, btn in self.nav_buttons.items():
            is_active = (key == tab_key)
            # Use subtle dark fill + left accent line — less heavy than full primary
            btn.bgcolor = COLORS["nav_active_bg"] if is_active else None
            btn.border = border_only(left=ft.BorderSide(3, COLORS["primary"])) if is_active else None
            row = btn.content
            nav_item = next((item for item in self.nav_items if item[0] == key), None)
            if nav_item:
                row.controls[0].name = nav_item[3] if is_active else nav_item[2]
            row.controls[0].color = "#FFFFFF" if is_active else COLORS["sidebar_muted"]
            row.controls[1].color = "#FFFFFF" if is_active else COLORS["sidebar_muted"]

        # Load or retrieve cached view
        is_cached = tab_key in self.views
        if not is_cached:
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

        # Mount view and update layout immediately for zero-lag tab transitions
        self.content_area.content = view
        self._update_badges(update_controls=False)
        try:
            self.page.update()
        except Exception:
            pass

        # If cached, refresh data smoothly after the tab transition
        if is_cached and hasattr(view, "refresh_data"):
            try:
                view.refresh_data()
            except Exception as ex:
                logger.warning(f"Error during refresh_data on view {tab_key}: {ex}")

    def _update_badges(self, update_controls: bool = True) -> None:
        try:
            account = repository.get_active_account()
            stats = repository.get_inbox_stats(account_id=account.id) if account else {
                "cleanup_suggested_emails": 0,
                "unread_emails": 0,
            }
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

            if account:
                self.user_email_text.value = account.email
                self.online_dot.bgcolor = COLORS["success"]
            else:
                self.user_email_text.value = "Demo Mode (Sign In)"
                self.online_dot.bgcolor = COLORS["warning"]

            if update_controls:
                safe_update(self.cleanup_badge_container)
                safe_update(self.inbox_badge_container)
                safe_update(self.user_footer)
        except Exception as ex:
            logger.debug(f"Error updating badges: {ex}")

    def _dispatch_ui(self, func, *args, **kwargs) -> None:
        """Schedules UI mutations on the Flet event loop thread-safely."""
        async def _coro():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in UI dispatch for {getattr(func, '__name__', str(func))}: {e}",
                    exc_info=True,
                )

        try:
            self.page.run_task(_coro)
        except Exception:
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"UI dispatch fallback failed: {e}")

    def _register_events(self) -> None:
        event_bus.subscribe(EVT_SYNC_COMPLETED, lambda data: self._dispatch_ui(self._on_sync_event, data))
        event_bus.subscribe(EVT_SUGGESTION_ACTIONED, lambda data: self._dispatch_ui(self._on_sync_event, data))
        event_bus.subscribe(EVT_TOAST_MESSAGE, lambda msg: self._dispatch_ui(self._show_toast, str(msg)))
        event_bus.subscribe(EVT_THEME_CHANGED, lambda theme: self._dispatch_ui(self._on_theme_event, theme))
        event_bus.subscribe(EVT_ACCOUNT_CHANGED, lambda email: self._dispatch_ui(self._on_account_changed, email))
        event_bus.subscribe(EVT_AUTH_REQUIRED, lambda data: self._dispatch_ui(self._on_auth_required, data))

    def _on_auth_required(self, data) -> None:
        """Handles revoked-token / reauthentication recovery dialog."""
        payload = data if isinstance(data, dict) else {}
        self.open_google_auth_dialog(
            reason=payload.get("reason", "Google authorization is required."),
            email=payload.get("email", ""),
        )

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
        self._apply_page_theme()
        self.page.bgcolor = COLORS["bg_main"]

        self.theme_icon.name = ft.Icons.DARK_MODE_OUTLINED if is_light else ft.Icons.LIGHT_MODE_OUTLINED
        self.theme_label.value = "Switch to Dark" if is_light else "Switch to Light"

        self.sidebar.bgcolor = COLORS["bg_sidebar"]
        self.sidebar.border = border_only(right=ft.BorderSide(1, COLORS["border"]))

        self.views.clear()
        self.show_view(self.current_tab)

    def _apply_page_theme(self) -> None:
        """Apply branded Material defaults so controls never fall back to blue."""
        rounded = ft.RoundedRectangleBorder(radius=10)
        self.page.theme = ft.Theme(
            use_material3=True,
            font_family="Segoe UI",
            color_scheme=ft.ColorScheme(
                primary=COLORS["primary"],
                on_primary="#FFFFFF",
                primary_container=COLORS["primary_soft"],
                on_primary_container=COLORS["badge_text"],
                secondary=COLORS["secondary"],
                on_secondary="#FFFFFF",
                tertiary=COLORS["accent"],
                on_tertiary="#FFFFFF",
                error=COLORS["danger"],
                surface=COLORS["bg_card"],
                on_surface=COLORS["text_primary"],
                outline=COLORS["border_hover"],
            ),
            button_theme=ft.ButtonTheme(
                style=ft.ButtonStyle(
                    bgcolor=COLORS["primary"],
                    color="#FFFFFF",
                    elevation=0,
                    padding=padding_symmetric(horizontal=18, vertical=12),
                    shape=rounded,
                )
            ),
            outlined_button_theme=ft.OutlinedButtonTheme(
                style=ft.ButtonStyle(
                    color=COLORS["primary"],
                    side=ft.BorderSide(1, COLORS["border_hover"]),
                    shape=rounded,
                )
            ),
            text_button_theme=ft.TextButtonTheme(
                style=ft.ButtonStyle(color=COLORS["primary"], shape=rounded)
            ),
        )

    def _on_sync_event(self, data) -> None:
        """Smoothly refreshes active and cached views in-place without destroying UI hierarchy."""
        self._update_badges()

        # Smooth in-place refresh of currently visible view
        active_view = self.views.get(self.current_tab)
        if active_view and hasattr(active_view, "refresh_data"):
            try:
                active_view.refresh_data()
            except Exception as ex:
                logger.warning(f"Error during smooth refresh of active view {self.current_tab}: {ex}")

        # Keep all other cached views up-to-date so tab switching is instant and accurate
        for key, view in self.views.items():
            if key != self.current_tab and hasattr(view, "refresh_data"):
                try:
                    view.refresh_data()
                except Exception:
                    pass

        try:
            self.page.update()
        except Exception:
            pass

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
