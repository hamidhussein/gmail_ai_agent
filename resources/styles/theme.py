"""
GmailAI Assistant - UI Design System & Theme Tokens
"""
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
        "primary": "#4F46E5",       # Electric Indigo
        "primary_hover": "#6366F1", # Neon Indigo
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
        "primary": "#4F46E5",
        "primary_hover": "#6366F1",
        "secondary": "#0EA5E9",
        "success": "#10B981",
        "warning": "#F59E0B",
        "danger": "#F43F5E",
        "danger_hover": "#E11D48",
        "badge_bg": "#EEF2FF",
        "badge_text": "#4F46E5",
    }
}

# Modern Typography Hierarchy
FONTS = {
    "h1": ("Segoe UI", 24, "bold"),
    "h2": ("Segoe UI", 20, "bold"),
    "h3": ("Segoe UI", 16, "bold"),
    "body_large": ("Segoe UI", 14),
    "body_bold": ("Segoe UI", 13, "bold"),
    "body": ("Segoe UI", 13),
    "body_sm": ("Segoe UI", 11),
    "body_sm_bold": ("Segoe UI", 11, "bold"),
    "code": ("Consolas", 12),
}


def get_category_color(category_str: str) -> str:
    """Returns color hex code for a given category name."""
    try:
        cat_enum = EmailCategory(category_str)
        return CATEGORY_COLORS.get(cat_enum, "#64748B")
    except Exception:
        return "#64748B"
