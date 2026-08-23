"""
GmailAI Assistant - Metric Stat Card Component for Flet
"""
import flet as ft
from typing import Optional
from resources.styles.theme import COLORS


class StatCard(ft.Container):
    """Modern glassmorphic stat card widget with hover elevation and accent glowing border."""

    def __init__(
        self,
        title: str,
        value: str,
        icon: str = ft.Icons.ANALYTICS_OUTLINED,
        trend: Optional[str] = None,
        accent_color: str = "#6366F1",
        expand: bool = True,
        **kwargs,
    ):
        self.value_text = ft.Text(
            value,
            size=28,
            weight=ft.FontWeight.BOLD,
            color=COLORS["text_primary"],
        )
        self.accent_color = accent_color

        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(icon, size=18, color=accent_color),
                            bgcolor=COLORS["bg_card_hover"],
                            padding=8,
                            border_radius=8,
                        ),
                        ft.Text(
                            title.upper(),
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=COLORS["text_secondary"],
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                ),
                self.value_text,
                ft.Text(
                    trend or "",
                    size=12,
                    color=accent_color if trend else COLORS["text_muted"],
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=8,
        )

        super().__init__(
            content=content,
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            border_radius=12,
            padding=16,
            expand=expand,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
            on_hover=self._on_hover,
            **kwargs,
        )

    def _on_hover(self, e):
        self.border = ft.border.all(1, self.accent_color if e.data == "true" else COLORS["border"])
        self.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
        self.update()

    def set_value(self, new_val: str) -> None:
        self.value_text.value = new_val
        if self.page:
            self.value_text.update()
