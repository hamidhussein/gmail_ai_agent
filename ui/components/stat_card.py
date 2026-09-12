"""
GmailAI Assistant - Metric Stat Card Component for Flet
"""
import flet as ft
from typing import Optional
from resources.styles.theme import (
    COLORS,
    border_all,
    border_only,
    padding_symmetric,
    safe_update,
)


class StatCard(ft.Container):
    """Modern stat card widget with left accent stripe, hover glow, and refined typography."""

    def __init__(
        self,
        title: str,
        value: str,
        icon: str = ft.Icons.ANALYTICS_OUTLINED,
        trend: Optional[str] = None,
        accent_color: str = "#7C3AED",
        expand: bool = True,
        **kwargs,
    ):
        self.value_text = ft.Text(
            value,
            size=26,
            weight=ft.FontWeight.BOLD,
            color=COLORS["text_primary"],
        )
        self.accent_color = accent_color

        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=14, color="#FFFFFF"),
                            bgcolor=accent_color,
                            padding=6,
                            border_radius=7,
                        ),
                        ft.Text(
                            title,
                            size=11,
                            weight=ft.FontWeight.W_600,
                            color=COLORS["text_muted"],
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                self.value_text,
                ft.Text(
                    trend or "",
                    size=11,
                    color=COLORS["text_muted"],
                    weight=ft.FontWeight.W_400,
                ),
            ],
            spacing=5,
        )

        super().__init__(
            content=content,
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, accent_color),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=12,
            padding=padding_symmetric(horizontal=16, vertical=14),
            expand=expand,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_hover,
            **kwargs,
        )

    def _on_hover(self, e):
        is_hovered = e.data == "true"
        # Only change background on hover — avoid distracting border color changes
        self.bgcolor = COLORS["bg_card_hover"] if is_hovered else COLORS["bg_card"]
        safe_update(self)

    def set_value(self, new_val: str) -> None:
        self.value_text.value = new_val
        safe_update(self.value_text)
