"""
GmailAI Assistant - Navigation Sidebar Component
"""
import customtkinter as ctk
from typing import Callable, Dict, Optional
from resources.styles.theme import FONTS, THEME


class SidebarNavigation(ctk.CTkFrame):
    """Modern sidebar navigation with brand header and badge counters."""

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        current_tab: str = "dashboard",
        **kwargs,
    ):
        super().__init__(
            master,
            width=240,
            corner_radius=0,
            fg_color=THEME["dark"]["bg_sidebar"],
            **kwargs,
        )
        self.on_navigate = on_navigate
        self.current_tab = current_tab
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.badge_labels: Dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # Header / Brand Logo
        self.brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.brand_frame.pack(fill="x", padx=20, pady=(24, 28))

        self.logo_icon = ctk.CTkLabel(
            self.brand_frame,
            text="\uE914",  # Fluent Icon Mail (or sparkle) \uE914 is generic, \uE81C is mail. Let's use \uE81C for Mail
            font=("Segoe Fluent Icons", 22),
            text_color=THEME["dark"]["primary"],
        )
        self.logo_icon.pack(side="left", padx=(0, 10))

        self.brand_title = ctk.CTkLabel(
            self.brand_frame,
            text="GmailAI",
            font=("Segoe UI", 20, "bold"),
            text_color=THEME["dark"]["text_primary"],
        )
        self.brand_title.pack(side="left")

        self.brand_sub = ctk.CTkLabel(
            self.brand_frame,
            text="PRO",
            font=("Segoe UI", 9, "bold"),
            fg_color=THEME["dark"]["badge_bg"],
            text_color=THEME["dark"]["badge_text"],
            corner_radius=4,
            width=36,
            height=20,
        )
        self.brand_sub.pack(side="left", padx=(8, 0))

        # Navigation Links using Segoe Fluent Icons
        nav_items = [
            ("dashboard", "\uE909  Dashboard", None),        # Home icon
            ("inbox", "\uE715  Intelligence Inbox", None),   # Mailbox icon
            ("review", "\uE71C  Smart Cleanup", "review_badge"), # Broom/Check icon
            ("digests", "\uE8EF  Daily Briefings", None),    # Report/Document icon
            ("audit", "\uE81C  Audit Logs", None),           # List icon
            ("settings", "\uE713  Settings & AI", None),      # Settings gear icon
        ]

        self.links_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.links_frame.pack(fill="x", padx=12, expand=True, anchor="n")

        for tab_key, label_text, badge_key in nav_items:
            item_frame = ctk.CTkFrame(self.links_frame, fg_color="transparent", height=42)
            item_frame.pack(fill="x", pady=3)
            item_frame.pack_propagate(False)

            is_active = self.current_tab == tab_key
            
            # Button with Fluent Icons
            btn = ctk.CTkButton(
                item_frame,
                text=label_text,
                anchor="w",
                font=("Segoe Fluent Icons", 14) if is_active else ("Segoe Fluent Icons", 14),
                fg_color=THEME["dark"]["primary"] if is_active else "transparent",
                hover_color=THEME["dark"]["bg_card_hover"],
                text_color=THEME["dark"]["text_primary"] if is_active else THEME["dark"]["text_secondary"],
                corner_radius=8,
                command=lambda k=tab_key: self._handle_click(k),
            )
            
            # Since the text is mixed, we use a custom approach or a font that supports both.
            # CustomTkinter supports fallback. But to be safe and crisp, we can use two labels, or just 
            # use a standard font that includes the Segoe UI symbols. Segoe UI Symbol works great.
            btn.configure(font=("Segoe UI", 13, "bold") if is_active else ("Segoe UI", 13))
            btn.pack(side="left", fill="both", expand=True)
            self.nav_buttons[tab_key] = btn

            if badge_key:
                badge = ctk.CTkLabel(
                    btn,
                    text="",
                    font=FONTS["body_sm_bold"],
                    fg_color="#EF4444",
                    text_color="#FFFFFF",
                    corner_radius=10,
                    width=20,
                    height=20,
                )
                self.badge_labels[badge_key] = badge

        # Footer User Info & Status
        self.footer_frame = ctk.CTkFrame(
            self, 
            fg_color=THEME["dark"]["bg_card"], 
            corner_radius=12,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.footer_frame.pack(fill="x", side="bottom", padx=16, pady=20)

        self.status_dot = ctk.CTkLabel(
            self.footer_frame,
            text="\uE73E",  # Filled circle in Segoe UI Symbol
            font=("Segoe UI Symbol", 12),
            text_color=THEME["dark"]["success"],
        )
        self.status_dot.pack(side="left", padx=(14, 8), pady=12)

        self.user_label = ctk.CTkLabel(
            self.footer_frame,
            text="Connected",
            font=FONTS["body_sm_bold"],
            text_color=THEME["dark"]["text_primary"],
            anchor="w",
        )
        self.user_label.pack(side="left", fill="x", expand=True, pady=12)

    def _handle_click(self, tab_key: str) -> None:
        self.set_active_tab(tab_key)
        self.on_navigate(tab_key)

    def set_active_tab(self, tab_key: str) -> None:
        self.current_tab = tab_key
        for key, btn in self.nav_buttons.items():
            if key == tab_key:
                btn.configure(
                    fg_color=THEME["dark"]["primary"],
                    text_color=THEME["dark"]["text_primary"],
                    font=("Segoe UI", 13, "bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=THEME["dark"]["text_secondary"],
                    font=("Segoe UI", 13),
                )

    def update_badge(self, badge_key: str, count: int) -> None:
        if badge_key in self.badge_labels:
            badge = self.badge_labels[badge_key]
            if count > 0:
                badge.configure(text=str(count))
                badge.place(relx=0.9, rely=0.5, anchor="center")
            else:
                badge.place_forget()

    def update_user_status(self, email_or_status: str, is_online: bool = True) -> None:
        short = email_or_status if len(email_or_status) <= 18 else email_or_status[:15] + "..."
        self.user_label.configure(text=short)
        self.status_dot.configure(text="🟢" if is_online else "🟡")
