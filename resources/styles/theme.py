"""
GmailAI Assistant - UI Design System & Theme Tokens for Flet
"""
import flet as ft
from app.constants import EmailCategory, CATEGORY_COLORS

# Core Color Palettes
THEME = {
    "light": {
        # Backgrounds
        "bg_main": "#F8F6F3",
        "bg_card": "#FFFFFF",
        "bg_card_hover": "#F5F3F7",
        "bg_sidebar": "#21142B",
        "surface_alt": "#FAFAFA",
        "bg_zebra": "#FBF9F7",
        # Sidebar
        "sidebar_text": "#FFF7FC",
        "sidebar_muted": "#C9B9CE",
        "sidebar_hover": "#2E1A3A",
        # Borders
        "border": "#E8E2EE",
        "border_hover": "#D0C5D8",
        # Text
        "text_primary": "#1E1528",
        "text_secondary": "#5E546A",
        "text_muted": "#9B90A3",
        # Brand colors - used sparingly
        "primary": "#6D28D9",
        "primary_hover": "#5B21B6",
        "primary_soft": "#EDE9FE",
        "secondary": "#DB2777",
        "secondary_hover": "#BE185D",
        "accent": "#0891B2",
        "accent_hover": "#0E7490",
        # Semantic colors
        "success": "#059669",
        "success_soft": "#ECFDF5",
        "warning": "#B45309",
        "warning_soft": "#FFFBEB",
        "danger": "#DC2626",
        "danger_hover": "#B91C1C",
        "danger_soft": "#FEF2F2",
        # Badge system
        "badge_bg": "#F0EEF4",
        "badge_text": "#4B4558",
        # Chip active state
        "chip_active_bg": "#1E1535",
        "chip_active_text": "#FFFFFF",
        # Icon badge backgrounds
        "icon_bg": "#EDE9FE",
        # Nav
        "nav_active_bg": "#2E1A3A",
        # Misc
        "shadow": "#2D1B4012",
    },
    "dark": {
        # Backgrounds
        "bg_main": "#120C16",
        "bg_card": "#1C1421",
        "bg_card_hover": "#261B2D",
        "bg_sidebar": "#0C080F",
        "surface_alt": "#181120",
        "bg_zebra": "#17101B",
        # Sidebar
        "sidebar_text": "#FFF7FC",
        "sidebar_muted": "#BFB0C4",
        "sidebar_hover": "#28183A",
        # Borders
        "border": "#352540",
        "border_hover": "#503860",
        # Text
        "text_primary": "#F5F0FA",
        "text_secondary": "#C0B2C8",
        "text_muted": "#7E7088",
        # Brand colors
        "primary": "#9333EA",
        "primary_hover": "#7C3AED",
        "primary_soft": "#2E1748",
        "secondary": "#F472B6",
        "secondary_hover": "#EC4899",
        "accent": "#22D3EE",
        "accent_hover": "#06B6D4",
        # Semantic
        "success": "#10B981",
        "success_soft": "#052E1B",
        "warning": "#D97706",
        "warning_soft": "#2D1B07",
        "danger": "#EF4444",
        "danger_hover": "#DC2626",
        "danger_soft": "#3B0F0F",
        # Badge system
        "badge_bg": "#241A2E",
        "badge_text": "#C8BAD0",
        # Chip active
        "chip_active_bg": "#3B2A5A",
        "chip_active_text": "#FFFFFF",
        # Icon badge backgrounds
        "icon_bg": "#2A1A42",
        # Nav
        "nav_active_bg": "#28183A",
        # Misc
        "shadow": "#00000050",
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
    """Returns a selective border."""
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


def icon_badge(
    icon: str,
    color: str = "#FFFFFF",
    bg: str = None,
    size: int = 14,
    pad: int = 6,
    radius: int = 8,
) -> ft.Container:
    """Standard colored icon-in-rounded-square badge for section headers."""
    return ft.Container(
        content=ft.Icon(icon, size=size, color=color),
        bgcolor=bg or COLORS["primary"],
        padding=pad,
        border_radius=radius,
    )


def label_text(text: str, color: str = None, size: int = 11) -> ft.Text:
    """ALL-CAPS muted label used in table headers and card sub-labels."""
    return ft.Text(
        text.upper(),
        size=size,
        weight=ft.FontWeight.W_600,
        color=color or COLORS["text_muted"],
    )


def glass_container(
    content: ft.Control,
    padding=16,
    border_color: str = None,
    bg_color: str = None,
    border_radius: int = 12,
    expand: bool = False,
    on_click=None,
    accent_color: str = None,
) -> ft.Container:
    """Creates a polished card container with subtle borders and optional left accent stripe."""
    if accent_color:
        border = border_only(
            left=ft.BorderSide(3, accent_color),
            top=ft.BorderSide(1, border_color or COLORS["border"]),
            right=ft.BorderSide(1, border_color or COLORS["border"]),
            bottom=ft.BorderSide(1, border_color or COLORS["border"]),
        )
    else:
        border = border_all(1, border_color or COLORS["border"])

    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=bg_color or COLORS["bg_card"],
        border=border,
        expand=expand,
        on_click=on_click,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=12,
            color=COLORS["shadow"],
            offset=ft.Offset(0, 3),
        ),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT) if on_click else None,
    )


def section_card(
    title: str,
    subtitle: str,
    controls: list,
    icon: str = None,
    accent_color: str = None,
) -> ft.Container:
    """Creates a polished settings-style section card with optional left accent bar."""
    header_items = []
    if icon:
        header_items.append(icon_badge(icon, bg=accent_color or COLORS["primary"]))
    header_items.append(
        ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"])
    )

    body = ft.Column([
        ft.Row(header_items, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ft.Text(subtitle, size=12, color=COLORS["text_secondary"]),
        ft.Divider(height=1, color=COLORS["border"]),
        ft.Column(controls, spacing=12),
    ], spacing=10)

    border = border_only(
        left=ft.BorderSide(3, accent_color or COLORS["primary"]),
        top=ft.BorderSide(1, COLORS["border"]),
        right=ft.BorderSide(1, COLORS["border"]),
        bottom=ft.BorderSide(1, COLORS["border"]),
    )

    return ft.Container(
        content=body,
        bgcolor=COLORS["bg_card"],
        border=border,
        border_radius=12,
        padding=20,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=12,
            color=COLORS["shadow"],
            offset=ft.Offset(0, 3),
        ),
    )


def pill_badge(
    text: str,
    bg_color: str,
    text_color: str = "#FFFFFF",
    size: int = 11,
    icon: str = None,
) -> ft.Container:
    """Creates a small rounded pill badge with optional icon."""
    row_items = []
    if icon:
        row_items.append(ft.Icon(icon, size=12, color=text_color))
    row_items.append(
        ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=text_color)
    )
    return ft.Container(
        content=ft.Row(row_items, spacing=4, tight=True,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=bg_color,
        padding=padding_symmetric(horizontal=7, vertical=3),
        border_radius=6,
    )


def status_dot(color: str, size: int = 8) -> ft.Container:
    """Creates a small colored status indicator dot."""
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 2,
        bgcolor=color,
    )


def empty_state(
    icon: str,
    title: str,
    subtitle: str,
    action_button: ft.Control = None,
) -> ft.Container:
    """Creates a polished empty state placeholder."""
    controls = [
        ft.Container(
            content=ft.Icon(icon, size=28, color=COLORS["text_muted"]),
            bgcolor=COLORS["badge_bg"],
            padding=16,
            border_radius=36,
            width=60,
            height=60,
            alignment=align_center(),
        ),
        ft.Container(height=4),
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"],
                text_align=ft.TextAlign.CENTER),
        ft.Text(subtitle, size=12, color=COLORS["text_secondary"],
                text_align=ft.TextAlign.CENTER),
    ]
    if action_button:
        controls.append(ft.Container(height=4))
        controls.append(action_button)

    return ft.Container(
        content=ft.Column(
            controls,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        alignment=align_center(),
        padding=60,
    )
