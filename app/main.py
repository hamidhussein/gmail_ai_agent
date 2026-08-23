"""
GmailAI Assistant - Main Application Entrypoint & Window Orchestrator
"""
import sys
import logging
import customtkinter as ctk
from typing import Dict, Any

from app.config import config_manager
from core.logger import setup_logger
from core.events import event_bus, EVT_SYNC_COMPLETED, EVT_SYNC_STARTED, EVT_TOAST_MESSAGE
from database.repository import repository
from database.migrations import seed_demo_data
from automation.scheduler import scheduler
from resources.styles.theme import THEME

from ui.components.navigation import SidebarNavigation
from ui.components.toast import ToastNotification
from ui.dashboard import DashboardView
from ui.inbox_view import InboxIntelligenceView
from ui.review_screen import ReviewScreenView
from ui.digests_view import DailyDigestsView
from ui.audit_view import AuditLogsView
from ui.settings import SettingsView

logger = logging.getLogger("GmailAI.Main")


class GmailAIApp(ctk.CTk):
    """Primary CustomTkinter Desktop Application Window."""

    def __init__(self):
        super().__init__()

        # Appearance & Geometry
        ctk.set_appearance_mode(config_manager.config.ui_theme)
        ctk.set_default_color_theme("blue")

        self.title("GmailAI Assistant — Privacy-First Hybrid AI Platform")
        self.geometry("1240x820")
        self.minsize(1080, 700)
        self.configure(fg_color=THEME["dark"]["bg_main"])

        # State & View cache
        self.current_tab = "dashboard"
        self.views: Dict[str, ctk.CTkFrame] = {}

        # Ensure initial database state
        self._init_data_if_needed()

        # Build UI layout
        self._build_layout()

        # Subscribe to Event Bus
        self._register_event_handlers()

        # Start background scheduling
        scheduler.start()

        # Protocol for clean shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_data_if_needed(self) -> None:
        """Seeds initial realistic data if fresh database."""
        stats = repository.get_inbox_stats()
        if stats["total_emails"] == 0:
            logger.info("Fresh database detected. Seeding sample demo data...")
            seed_demo_data()

    def _build_layout(self) -> None:
        # Left Navigation Sidebar
        self.sidebar = SidebarNavigation(
            self,
            on_navigate=self.show_view,
            current_tab="dashboard",
        )
        self.sidebar.pack(side="left", fill="y")

        # Right Main Content Container
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(side="right", fill="both", expand=True)

        # Initialize and mount initial view
        self.show_view("dashboard")
        self._update_badges()

    def show_view(self, tab_key: str) -> None:
        """Swaps active view with caching — on second visit, just re-shows the cached view and calls refresh()."""
        self.current_tab = tab_key
        self.sidebar.set_active_tab(tab_key)

        # Hide all current children
        for child in self.content_container.winfo_children():
            child.pack_forget()

        try:
            # Return cached view if it exists, otherwise build fresh
            if tab_key in self.views:
                view = self.views[tab_key]
                view.pack(fill="both", expand=True)
                # Call refresh if available
                if hasattr(view, "refresh_data"):
                    view.refresh_data()
                elif hasattr(view, "load_suggestions"):
                    view.load_suggestions()
                elif hasattr(view, "load_digests"):
                    view.load_digests()
            else:
                view = self._build_view(tab_key)
                if view:
                    self.views[tab_key] = view
                    view.pack(fill="both", expand=True)
        except Exception as exc:
            logger.error(f"Unhandled error loading view '{tab_key}': {exc}", exc_info=True)
            self._show_error_view(tab_key, exc)

        self._update_badges()

    def _build_view(self, tab_key: str):
        """Instantiates the correct view for a given tab key."""
        if tab_key == "dashboard":
            return DashboardView(self.content_container, on_navigate=self.show_view)
        elif tab_key == "inbox":
            return InboxIntelligenceView(self.content_container)
        elif tab_key == "review":
            return ReviewScreenView(self.content_container)
        elif tab_key == "digests":
            return DailyDigestsView(self.content_container)
        elif tab_key == "audit":
            return AuditLogsView(self.content_container)
        elif tab_key == "settings":
            return SettingsView(self.content_container)
        else:
            return DashboardView(self.content_container, on_navigate=self.show_view)

    def _show_error_view(self, tab_key: str, exc: Exception) -> None:
        """Renders an in-app error card when a view fails to load."""
        error_frame = ctk.CTkFrame(self.content_container, fg_color="#1E1E2E", corner_radius=0)
        error_frame.pack(fill="both", expand=True)

        # Centred error card
        card = ctk.CTkFrame(error_frame, fg_color="#2A2A3D", corner_radius=16, width=520)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            card, text="⚠", font=("Inter", 48), text_color="#F59E0B"
        ).pack(pady=(32, 4))
        ctk.CTkLabel(
            card, text=f"Failed to load '{tab_key}' view",
            font=("Inter", 18, "bold"), text_color="#F1F5F9"
        ).pack(pady=(0, 8))
        ctk.CTkLabel(
            card, text=str(exc), font=("Inter", 12), text_color="#94A3B8",
            wraplength=440, justify="center"
        ).pack(pady=(0, 20))
        ctk.CTkButton(
            card, text="⟳  Retry", font=("Inter", 14, "bold"),
            fg_color="#6366F1", hover_color="#4F46E5", corner_radius=8,
            command=lambda: self.show_view(tab_key),
        ).pack(pady=(0, 28))

    def _update_badges(self) -> None:
        """Updates sidebar notification badge counts."""
        stats = repository.get_inbox_stats()
        cleanup_count = stats.get("cleanup_suggested_emails", 0)
        self.sidebar.update_badge("review_badge", cleanup_count)

        acc = repository.get_active_account()
        if acc:
            self.sidebar.update_user_status(acc.email, is_online=True)
        else:
            self.sidebar.update_user_status("Demo Account", is_online=False)

    def _register_event_handlers(self) -> None:
        event_bus.subscribe(EVT_SYNC_COMPLETED, lambda data: self.after(0, self._on_sync_event))
        event_bus.subscribe(EVT_TOAST_MESSAGE, lambda data: self.after(0, lambda: ToastNotification.show(self, str(data))))

    def _on_sync_event(self) -> None:
        # Invalidate dashboard cache so next visit rebuilds fresh data
        self.views.pop("dashboard", None)
        self._update_badges()
        if self.current_tab == "dashboard":
            self.show_view("dashboard")

    def _on_close(self) -> None:
        logger.info("Application closing...")
        scheduler.stop()
        self.destroy()
        sys.exit(0)


def main():
    setup_logger(log_dir=config_manager.log_dir)
    app = GmailAIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
