"""
GmailAI Assistant - UI Design System & Theme Tokens for Flet
"""
import flet as ft
from app.constants import EmailCategory, CATEGORY_COLORS

# Core Color Palettes
THEME = {
    "light": {
        "bg_main": "#F8FAFC",       # Clean Slate 50
        "bg_card": "#FFFFFF",       # Crisp White Card
        "bg_card_hover": "#F1F5F9", # Light Slate 100
        "bg_sidebar": "#FFFFFF",    # Pure White Sidebar
        "border": "#E2E8F0",        # Light Slate 200 Border
        "text_primary": "#0F172A",  # Deep Slate 900
        "text_secondary": "#64748B",# Slate 500
        "text_muted": "#94A3B8",    # Slate 400
        "primary": "#6366F1",       # Electric Indigo
        "primary_hover": "#4F46E5", # Deep Indigo
        "secondary": "#0EA5E9",     # Sky Blue
        "success": "#10B981",       # Emerald
        "warning": "#F59E0B",       # Amber
        "danger": "#F43F5E",        # Coral
        "danger_hover": "#E11D48",  # Rose Red
        "badge_bg": "#EEF2FF",      # Indigo 50
        "badge_text": "#4F46E5",    # Indigo 600
    },
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
    }
}

current_theme_mode = "light"
COLORS = dict(THEME["light"])


def set_theme_mode(mode: str) -> None:
    """Dynamically updates active theme tokens in-place."""
    global current_theme_mode
    mode_key = "dark" if mode == "dark" else "light"
    current_theme_mode = mode_key
    COLORS.clear()
    COLORS.update(THEME[mode_key])


def get_category_color(category_str: str) -> str:
    """Returns hex color string for a given category name."""
    try:
        cat_enum = EmailCategory(category_str)
        return CATEGORY_COLORS.get(cat_enum, "#64748B")
    except Exception:
        return "#64748B"


def border_all(width: float = 1, color: str = None) -> ft.Border:
    """Returns a full border around all sides."""
    return ft.Border.all(width, color or COLORS["border"])


def border_only(**kwargs) -> ft.Border:
    """Returns a selective border (e.g. right=ft.BorderSide(1, color))."""
    return ft.Border.only(**kwargs)


def padding_all(value: float) -> ft.Padding:
    """Returns uniform padding for all 4 sides."""
    return ft.Padding(value, value, value, value)


def padding_symmetric(horizontal: float = 0, vertical: float = 0) -> ft.Padding:
    """Returns symmetric horizontal and vertical padding."""
    return ft.Padding(horizontal, vertical, horizontal, vertical)


def align_center() -> ft.Alignment:
    """Returns centered alignment."""
    return ft.Alignment(0, 0)


def safe_update(control: ft.Control) -> None:
    """Safely updates a control or page without raising RuntimeError if not mounted."""
    try:
        if control is not None:
            control.update()
    except Exception:
        pass


def glass_container(
    content: ft.Control,
    padding = 16,
    border_color: str = None,
    bg_color: str = None,
    border_radius: int = 12,
    expand: bool = False,
    on_click=None,
) -> ft.Container:
    """Creates a polished card container with subtle borders."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=bg_color or COLORS["bg_card"],
        border=border_all(1, border_color or COLORS["border"]),
        expand=expand,
        on_click=on_click,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT) if on_click else None,
    )
