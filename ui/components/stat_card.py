"""
GmailAI Assistant - Metric Stat Card Component
"""
import customtkinter as ctk
from typing import Optional
from resources.styles.theme import FONTS, THEME


class StatCard(ctk.CTkFrame):
    """Clean modern stat widget displaying metric, icon, title, and badge."""

    def __init__(
        self,
        master,
        title: str,
        value: str,
        icon: str = "📊",
        trend: Optional[str] = None,
        accent_color: str = "#6366F1",
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["dark"]["border"],
            **kwargs,
        )
        self.title_text = title
        self.accent_color = accent_color

        # Hover effects
        self.bind("<Enter>", lambda e: self.configure(border_color=THEME["dark"]["text_secondary"]))
        self.bind("<Leave>", lambda e: self.configure(border_color=THEME["dark"]["border"]))

        # Header with icon and title
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 6))

        # We keep emojis for now if passed in, but add a nice background circle
        self.icon_label = ctk.CTkLabel(
            header,
            text=icon,
            font=("Segoe UI Emoji", 16),
            width=32,
            height=32,
            fg_color=THEME["dark"]["bg_card_hover"],
            corner_radius=16, # Full circle
        )
        self.icon_label.pack(side="left", padx=(0, 10))

        self.title_label = ctk.CTkLabel(
            header,
            text=title.upper(),
            font=FONTS["body_sm_bold"],
            text_color=THEME["dark"]["text_secondary"],
        )
        self.title_label.pack(side="left")

        # Big Value Display
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=("Segoe UI", 28, "bold"),
            text_color=THEME["dark"]["text_primary"],
            anchor="w",
        )
        self.value_label.pack(fill="x", padx=18, pady=(2, 4))

        # Optional trend or subtitle
        if trend:
            self.trend_label = ctk.CTkLabel(
                self,
                text=trend,
                font=FONTS["body_sm"],
                text_color=accent_color,
                anchor="w",
            )
            self.trend_label.pack(fill="x", padx=18, pady=(0, 18))
        else:
            # Bottom spacer
            ctk.CTkFrame(self, height=18, fg_color="transparent").pack()

    def set_value(self, new_val: str) -> None:
        self.value_label.configure(text=new_val)
