"""
GmailAI Assistant - UI Design System & Theme Tokens for Flet
"""
import flet as ft
from app.constants import EmailCategory, CATEGORY_COLORS

# Core Color Palette - "Midnight Glass"
THEME = {
    "dark": {
        "bg_main": "#060913",       # Deep Midnight Blue (Obsidian)
        "bg_card": "#0F1423",       # Elevated Glass Surface
        "bg_card_hover": "#1A2138", # Floating Hover Surface
        "bg_sidebar": "#030408",    # Vantablack sidebar
        "border": "#1E293B",        # Subtle glowing edge
        "text_primary": "#FFFFFF",  # Crisp White
        "text_secondary": "#94A3B8",# Soft Slate Blue
        "text_muted": "#475569",    # Deep Slate
        "primary": "#6366F1",       # Electric Indigo
        "primary_hover": "#4F46E5", # Deep Indigo
        "secondary": "#0EA5E9",     # Sky Blue
        "success": "#10B981",       # Neon Emerald
        "warning": "#F59E0B",       # Amber
        "danger": "#F43F5E",        # Hot Coral
        "danger_hover": "#E11D48",  # Rose Red
        "badge_bg": "#1E1B4B",      # Deep Indigo Glow
        "badge_text": "#A5B4FC",    # Soft Indigo Text
    },
    "light": {
        "bg_main": "#F8FAFC",
        "bg_card": "#FFFFFF",
        "bg_card_hover": "#F1F5F9",
        "bg_sidebar": "#FFFFFF",
        "border": "#E2E8F0",
        "text_primary": "#0F172A",
        "text_secondary": "#64748B",
        "text_muted": "#94A3B8",
        "primary": "#6366F1",
        "primary_hover": "#4F46E5",
        "secondary": "#0EA5E9",
        "success": "#10B981",
        "warning": "#F59E0B",
        "danger": "#F43F5E",
        "danger_hover": "#E11D48",
        "badge_bg": "#EEF2FF",
        "badge_text": "#4F46E5",
    }
}

COLORS = THEME["dark"]

# Typography Tokens
FONTS = {
    "h1": ft.TextStyle(size=26, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
    "h2": ft.TextStyle(size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
    "h3": ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
    "body_large": ft.TextStyle(size=15, color=COLORS["text_secondary"]),
    "body": ft.TextStyle(size=13, color=COLORS["text_secondary"]),
    "body_bold": ft.TextStyle(size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
    "body_sm": ft.TextStyle(size=11, color=COLORS["text_secondary"]),
    "body_sm_bold": ft.TextStyle(size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
}


def get_category_color(category_str: str) -> str:
    """Returns hex color string for a given category name."""
    try:
        cat_enum = EmailCategory(category_str)
        return CATEGORY_COLORS.get(cat_enum, "#64748B")
    except Exception:
        return "#64748B"


def glass_container(
    content: ft.Control,
    padding: int = 16,
    border_color: str = None,
    bg_color: str = None,
    border_radius: int = 12,
    expand: bool = False,
    on_click=None,
) -> ft.Container:
    """Creates a polished dark glassmorphic card container with subtle borders."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=bg_color or COLORS["bg_card"],
        border=ft.border.all(1, border_color or COLORS["border"]),
        expand=expand,
        on_click=on_click,
        animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT) if on_click else None,
    )
