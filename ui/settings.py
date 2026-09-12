"""
GmailAI Assistant - Settings & AI Router Configuration for Flet

Provides a consumer-ready settings experience with:
  - 1-click "Sign in with Google" account connection
  - Multi-account switcher for connected accounts
  - Collapsible advanced section for custom Google Cloud credentials
  - AI router, safety, appearance, profile, and data management controls
"""
import os
import zipfile
import datetime
import webbrowser
from typing import Optional, List, Dict, Any
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    set_theme_mode,
    pill_badge,
)
from app.config import config_manager
from core.events import event_bus, EVT_THEME_CHANGED
from authentication.credential_manager import credential_manager
from authentication.oauth_manager import oauth_manager
from ui.components.google_auth_modal import GoogleAuthDialog
from database.repository import repository
from database.migrations import seed_demo_data
from ai.local_model import LocalOllamaClient
from memory.user_profile import user_profile_manager
from automation.scheduler import scheduler


class SettingsView(ft.Container):
    """Full control panel for AI models, Gmail OAuth, appearance, safety thresholds, and profile settings."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page

        # Section 1: AI Router Controls
        self.ai_mode_dropdown = ft.Dropdown(
            value=config_manager.config.ai_mode,
            options=[
                ft.DropdownOption("HYBRID"),
                ft.DropdownOption("LOCAL_ONLY"),
                ft.DropdownOption("CLOUD_ONLY"),
                ft.DropdownOption("HEURISTIC"),
            ],
            width=200,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            on_select=self._on_ai_mode_change,
        )

        self.ollama_url_field = ft.TextField(
            value=config_manager.config.ollama_url,
            label="Local Ollama Endpoint",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            expand=True,
            content_padding=10,
        )

        self.ollama_model_field = ft.TextField(
            value=config_manager.config.ollama_model,
            label="Ollama Model Name",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            width=200,
            content_padding=10,
        )

        self.openai_key_field = ft.TextField(
            value=config_manager.get_openai_api_key() or "",
            label="OpenAI API Key (Optional)",
            password=True,
            can_reveal_password=True,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            expand=True,
            content_padding=10,
        )

        # Gemini API Key field
        self.gemini_key_field = ft.TextField(
            value=config_manager.get_gemini_api_key() or "",
            label="Google Gemini API Key",
            password=True,
            can_reveal_password=True,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            expand=True,
            content_padding=10,
        )

        self.gemini_model_field = ft.TextField(
            value=config_manager.config.gemini_model,
            label="Gemini Model Name",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            width=200,
            content_padding=10,
        )

        # Cloud Provider selector
        self.cloud_provider_dropdown = ft.Dropdown(
            value=config_manager.config.cloud_provider,
            options=[
                ft.DropdownOption("gemini"),
                ft.DropdownOption("openai"),
            ],
            width=200,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            on_select=self._on_cloud_provider_change,
        )

        # Section 2: Gmail OAuth — Connected Accounts Manager
        self.account_status_text = ft.Text("Checking account...", size=14, color=COLORS["text_primary"])
        self.accounts_list_column = ft.Column(spacing=8)

        # Advanced credentials (collapsed by default)
        self.advanced_expanded = False
        self.creds_json_field = ft.TextField(
            label="Paste your credentials.json content here",
            multiline=True,
            min_lines=4,
            max_lines=8,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            content_padding=10,
            expand=True,
        )
        self.creds_error_text = ft.Text("", size=12, color=COLORS["danger"], visible=False)
        self.advanced_content = ft.Container(visible=False)

        # Section 3: Safety Guardrails
        self.confidence_slider = ft.Slider(
            min=50,
            max=95,
            divisions=9,
            value=int(config_manager.config.hybrid_confidence_threshold * 100),
            label="{value}%",
            active_color=COLORS["primary"],
            on_change=self._on_confidence_change,
        )
        self.confidence_val_text = ft.Text(
            f"{int(config_manager.config.hybrid_confidence_threshold * 100)}%",
            size=14, weight=ft.FontWeight.BOLD, color=COLORS["primary"],
        )
        self.confidence_bar = ft.ProgressBar(
            value=config_manager.config.hybrid_confidence_threshold,
            height=6,
            color=COLORS["primary"],
            bgcolor=COLORS["border"],
            border_radius=3,
        )

        # Section 4: User Profile
        self.user_name_field = ft.TextField(
            value=user_profile_manager.profile.name or "Alex",
            label="Your Name",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            width=260,
            content_padding=10,
        )
        self.user_company_field = ft.TextField(
            value=user_profile_manager.profile.company_name or "",
            label="Organization / Company",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            width=260,
            content_padding=10,
        )

        # Section 5: Appearance
        self.theme_dropdown = ft.Dropdown(
            value=config_manager.config.ui_theme or "light",
            options=[
                ft.DropdownOption("light"),
                ft.DropdownOption("dark"),
            ],
            width=220,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            on_select=self._on_theme_change,
        )

        # ===== Build Layout =====
        content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=20,
            controls=[
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.SETTINGS, size=22, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=8,
                        border_radius=10,
                        shadow=ft.BoxShadow(spread_radius=0, blur_radius=6, color=COLORS["primary"] + "40", offset=ft.Offset(0, 2)),
                    ),
                    ft.Column([
                        ft.Text("Settings & Intelligence Control", size=22, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Configure AI routing, safety guardrails, authentication, and personalization.", size=13, color=COLORS["text_secondary"]),
                    ], spacing=2),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Gmail Connection — Consumer-Ready Experience
                self._build_gmail_section(),

                # AI Engine Router
                self._section_card(
                    title="Hybrid AI Router Configuration",
                    subtitle="Configure local Ollama execution and cloud LLM provider (Gemini or OpenAI).",
                    icon=ft.Icons.PSYCHOLOGY_OUTLINED,
                    controls=[
                        ft.Row([
                            ft.Text("Active Routing Mode:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.ai_mode_dropdown,
                            ft.Container(width=20),
                            ft.Text("Cloud Provider:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.cloud_provider_dropdown,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Text("Local AI (Ollama)", size=12, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                        ft.Row([
                            self.ollama_url_field,
                            self.ollama_model_field,
                            ft.ElevatedButton("Test Ollama", icon=ft.Icons.CHECK, bgcolor=COLORS["primary"], color="#FFFFFF", on_click=lambda e: self._test_ollama()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Text("Google Gemini (Recommended Cloud AI)", size=12, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                        ft.Row([
                            self.gemini_key_field,
                            self.gemini_model_field,
                            ft.ElevatedButton("Save Gemini Key", icon=ft.Icons.KEY, bgcolor="#4285F4", color="#FFFFFF", on_click=lambda e: self._save_gemini_key()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=COLORS["text_muted"]),
                                ft.Text("Get your free Gemini API key at Google AI Studio: aistudio.google.com/apikey", size=11, color=COLORS["text_muted"]),
                                ft.TextButton("Get API Key", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: self._open_url("https://aistudio.google.com/apikey")),
                            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=padding_symmetric(horizontal=8, vertical=6),
                            bgcolor=COLORS["bg_card_hover"],
                            border_radius=6,
                        ),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Text("OpenAI (Alternative Cloud AI)", size=12, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                        ft.Row([
                            self.openai_key_field,
                            ft.ElevatedButton("Save OpenAI Key", icon=ft.Icons.KEY, bgcolor=COLORS["secondary"], color="#FFFFFF", on_click=lambda e: self._save_openai_key()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    ],
                ),

                # Safety Guardrails
                self._section_card(
                    title="Safety Guardrails & Thresholds",
                    subtitle="Set minimum confidence required before proposing automated actions.",
                    icon=ft.Icons.SHIELD_OUTLINED,
                    controls=[
                        ft.Row([
                            ft.Text("Minimum AI Confidence for Auto-Suggestions:", size=13, color=COLORS["text_primary"]),
                            ft.Container(expand=True),
                            self.confidence_val_text,
                        ]),
                        self.confidence_slider,
                        self.confidence_bar,
                    ],
                ),

                # Appearance
                self._section_card(
                    title="Appearance & Theme Palette",
                    subtitle="Switch between crisp clean Light Mode and Obsidian Midnight Dark Mode.",
                    icon=ft.Icons.PALETTE_OUTLINED,
                    controls=[
                        ft.Row([
                            ft.Text("Active Theme Mode:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.theme_dropdown,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ],
                ),

                # User Personalization
                self._section_card(
                    title="User Personalization & AI Memory",
                    subtitle="Personalize how the AI Reply Assistant formats greetings, tone, and signatures.",
                    icon=ft.Icons.PERSON_OUTLINED,
                    controls=[
                        ft.Row([
                            self.user_name_field,
                            self.user_company_field,
                            ft.ElevatedButton("Save Profile", icon=ft.Icons.SAVE, bgcolor=COLORS["accent"], color="#FFFFFF", on_click=lambda e: self._save_profile()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ],
                ),

                # Data & Backup
                self._section_card(
                    title="Data Management & Demo Tools",
                    subtitle="Export encrypted database backups or re-seed realistic demo data.",
                    icon=ft.Icons.STORAGE_OUTLINED,
                    controls=[
                        ft.Row([
                            ft.ElevatedButton(
                                "Export Backup Archive (.zip)",
                                icon=ft.Icons.DOWNLOAD,
                                bgcolor=COLORS["primary"],
                                color="#FFFFFF",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda e: self._export_backup(),
                            ),
                            ft.OutlinedButton(
                                "Reset Demo Dataset",
                                icon=ft.Icons.REFRESH,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["warning"]),
                                on_click=lambda e: self._seed_demo(),
                            ),
                        ], spacing=12),
                    ],
                ),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )
        self.refresh_data()

    # =====================================================================
    # Gmail Section Builder — Consumer-Ready Connected Accounts
    # =====================================================================
    def _build_gmail_section(self) -> ft.Container:
        """Builds the consumer-ready Gmail account connection card."""
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.LOCK_PERSON_OUTLINED, size=16, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=6,
                        border_radius=6,
                    ),
                    ft.Text("Gmail Account Connection", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("Connect your Gmail account to unlock AI-powered inbox intelligence. Sign in with your Google account — no developer setup required.", size=12, color=COLORS["text_secondary"]),
                ft.Divider(height=1, color=COLORS["border"]),

                # Current account status
                ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, size=22, color=COLORS["success"]),
                    self.account_status_text,
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "Sign in with Google",
                        icon=ft.Icons.LOGIN,
                        bgcolor=COLORS["primary"],
                        color="#FFFFFF",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._add_new_account(),
                    ),
                    ft.OutlinedButton(
                        "Sync Now",
                        icon=ft.Icons.SYNC,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["primary"]),
                        on_click=lambda e: self._sync_now(),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),

                # Connected accounts list
                self.accounts_list_column,

                ft.Divider(height=1, color=COLORS["border"]),

                # Advanced / Custom Credentials Section (collapsed by default)
                self._build_advanced_credentials_section(),
            ], spacing=12),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["primary"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=12,
            padding=20,
        )

    def _build_advanced_credentials_section(self) -> ft.Container:
        """Builds the collapsible advanced credentials section for power users."""
        self.advanced_toggle_icon = ft.Icon(ft.Icons.EXPAND_MORE, size=18, color=COLORS["text_muted"])
        self.advanced_toggle_text = ft.Text("Advanced: Custom Google Cloud Credentials", size=12, color=COLORS["text_muted"])

        self.advanced_content = ft.Container(
            visible=False,
            content=ft.Column([
                ft.Text(
                    "For enterprise users or developers who want to use their own Google Cloud project. "
                    "Create an OAuth 2.0 Desktop Client ID in Google Cloud Console, download the credentials.json, and paste it below.",
                    size=11,
                    color=COLORS["text_secondary"],
                ),
                ft.Container(height=4),
                ft.Row([
                    ft.TextButton("Open Google Cloud Console", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: self._open_url("https://console.cloud.google.com/apis/credentials")),
                    ft.TextButton("OAuth Setup Guide", icon=ft.Icons.HELP_OUTLINE, on_click=lambda e: self._open_url("https://developers.google.com/identity/protocols/oauth2")),
                ], spacing=8),
                self.creds_json_field,
                self.creds_error_text,
                ft.Row([
                    ft.ElevatedButton(
                        "Save Custom Credentials & Connect",
                        icon=ft.Icons.SAVE,
                        bgcolor=COLORS["accent"],
                        color="#FFFFFF",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._save_and_connect(),
                    ),
                    ft.OutlinedButton(
                        "Browse File Instead",
                        icon=ft.Icons.FOLDER_OPEN,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._pick_credentials_file(),
                    ),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Reset to Default Credentials",
                        icon=ft.Icons.RESTORE,
                        style=ft.ButtonStyle(color=COLORS["warning"]),
                        on_click=lambda e: self._clear_custom_credentials(),
                    ),
                ], spacing=10),
            ], spacing=10),
            padding=ft.Padding(left=0, top=10, right=0, bottom=0),
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        self.advanced_toggle_icon,
                        self.advanced_toggle_text,
                        ft.Container(expand=True),
                        ft.Text(
                            "Using custom credentials" if credential_manager.has_custom_credentials() else "Using built-in defaults",
                            size=11,
                            color=COLORS["success"] if credential_manager.has_custom_credentials() else COLORS["text_muted"],
                            italic=True,
                        ),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    on_click=lambda e: self._toggle_advanced(),
                    padding=padding_symmetric(horizontal=8, vertical=6),
                    border_radius=6,
                    ink=True,
                ),
                self.advanced_content,
            ], spacing=0),
        )

    def _toggle_advanced(self):
        """Toggles the advanced credentials section visibility."""
        self.advanced_expanded = not self.advanced_expanded
        self.advanced_content.visible = self.advanced_expanded
        self.advanced_toggle_icon.name = ft.Icons.EXPAND_LESS if self.advanced_expanded else ft.Icons.EXPAND_MORE
        safe_update(self.advanced_content)
        safe_update(self.advanced_toggle_icon)

    def _build_account_card(self, account_info: Dict[str, Any]) -> ft.Container:
        """Builds a single account row card for the connected accounts list."""
        email = account_info["email"]
        display_name = account_info.get("display_name", email)
        is_active = account_info.get("is_active", False)
        has_token = account_info.get("has_valid_token", False)
        last_synced = account_info.get("last_synced_at")

        # Status indicator
        if is_active and has_token:
            status_color = COLORS["success"]
            status_text = "Active & Syncing"
            status_icon = ft.Icons.CHECK_CIRCLE
        elif has_token:
            status_color = COLORS["text_muted"]
            status_text = "Connected"
            status_icon = ft.Icons.CHECK_CIRCLE_OUTLINE
        else:
            status_color = COLORS["warning"]
            status_text = "Re-auth Required"
            status_icon = ft.Icons.WARNING_AMBER_OUTLINED

        # Last sync time
        sync_label = ""
        if last_synced:
            sync_label = f" • Last synced: {last_synced.strftime('%b %d, %H:%M')}"

        # Initials avatar
        initials = "".join([p[0].upper() for p in display_name.split()[:2]]) if display_name else "?"

        def on_card_hover(e):
            card.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
            safe_update(card)

        card = ft.Container(
            content=ft.Row([
                # Avatar
                ft.Container(
                    content=ft.Text(initials, size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=COLORS["primary"] if is_active else COLORS["text_muted"],
                    width=34, height=34, border_radius=17,
                    alignment=ft.Alignment(0, 0),
                ),
                # Info
                ft.Column([
                    ft.Row([
                        ft.Text(display_name, size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                        ft.Container(
                            content=ft.Text(status_text, size=9, weight=ft.FontWeight.BOLD, color=status_color),
                            bgcolor=status_color + "18",
                            padding=padding_symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(f"{email}{sync_label}", size=11, color=COLORS["text_secondary"]),
                ], spacing=2, expand=True),
                # Actions
                *([] if is_active else [
                    ft.TextButton(
                        "Switch",
                        icon=ft.Icons.SWAP_HORIZ,
                        style=ft.ButtonStyle(color=COLORS["primary"]),
                        on_click=lambda e, em=email: self._switch_account(em),
                    ),
                ]),
                ft.IconButton(
                    icon=ft.Icons.LOGOUT,
                    icon_size=16,
                    icon_color=COLORS["danger"],
                    tooltip=f"Sign out {email}",
                    on_click=lambda e, em=email: self._disconnect_single_account(em),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["primary"] + "30" if is_active else COLORS["border"]),
            border_radius=10,
            padding=padding_symmetric(horizontal=14, vertical=10),
            on_hover=on_card_hover,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        return card

    # =====================================================================
    # Helpers
    # =====================================================================
    def refresh_data(self) -> None:
        account = repository.get_active_account()
        if account:
            self.account_status_text.value = f"Authenticated as {account.email} (Active)"
            self.account_status_text.color = COLORS["success"]
        else:
            self.account_status_text.value = "No active Gmail account connected — click 'Sign in with Google' to get started"
            self.account_status_text.color = COLORS["warning"]

        # Rebuild connected accounts list
        self._refresh_accounts_list()

        safe_update(self.page_ref)

    def _refresh_accounts_list(self):
        """Rebuilds the connected accounts card list."""
        self.accounts_list_column.controls.clear()
        try:
            accounts = oauth_manager.list_authenticated_accounts()
            # Show accounts that have tokens (authenticated)
            authenticated = [a for a in accounts if a["has_valid_token"]]
            if authenticated:
                for acc_info in authenticated:
                    self.accounts_list_column.controls.append(self._build_account_card(acc_info))
            else:
                self.accounts_list_column.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=COLORS["text_muted"]),
                            ft.Text("No Gmail accounts connected yet. Click 'Sign in with Google' above.", size=12, color=COLORS["text_muted"]),
                        ], spacing=8),
                        padding=padding_symmetric(horizontal=8, vertical=10),
                    )
                )
        except Exception as ex:
            self.accounts_list_column.controls.append(
                ft.Text(f"Error loading accounts: {ex}", size=11, color=COLORS["danger"])
            )
        safe_update(self.accounts_list_column)

    def _section_card(self, title: str, subtitle: str, controls: list, icon: Optional[str] = None) -> ft.Container:
        header_items = []
        if icon:
            header_items.append(
                ft.Container(
                    content=ft.Icon(icon, size=16, color="#FFFFFF"),
                    bgcolor=COLORS["primary"],
                    padding=6,
                    border_radius=6,
                )
            )
        header_items.append(ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]))

        return ft.Container(
            content=ft.Column([
                ft.Row(header_items, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text(subtitle, size=12, color=COLORS["text_secondary"]),
                ft.Divider(height=1, color=COLORS["border"]),
                ft.Column(controls, spacing=12),
            ], spacing=10),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["primary"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=12,
            padding=20,
        )

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # =====================================================================
    # Event Handlers
    # =====================================================================
    def _on_ai_mode_change(self, e):
        config_manager.config.ai_mode = self.ai_mode_dropdown.value
        config_manager.save()
        self._toast(f"AI Mode set to {self.ai_mode_dropdown.value}", COLORS["success"])

    def _on_theme_change(self, e):
        new_theme = self.theme_dropdown.value
        config_manager.config.ui_theme = new_theme
        config_manager.save()
        set_theme_mode(new_theme)
        event_bus.publish(EVT_THEME_CHANGED, new_theme)
        if self.page_ref:
            self.page_ref.theme_mode = ft.ThemeMode.LIGHT if new_theme == "light" else ft.ThemeMode.DARK
            self.page_ref.bgcolor = COLORS["bg_main"]
            safe_update(self.page_ref)
        self._toast(f"Theme set to {new_theme.capitalize()} Mode", COLORS["success"])

    def _on_confidence_change(self, e):
        val = float(e.control.value) / 100.0
        self.confidence_val_text.value = f"{int(e.control.value)}%"
        self.confidence_bar.value = val
        config_manager.config.hybrid_confidence_threshold = val
        config_manager.save()
        safe_update(self.confidence_val_text)
        safe_update(self.confidence_bar)

    # =====================================================================
    # Gmail Auth Actions — Consumer-Ready
    # =====================================================================
    def _add_new_account(self):
        """Opens browser Google sign-in to add a new Gmail account."""
        self._start_authentication()

    def _switch_account(self, email: str):
        """Switches the active account to the given email without re-auth."""
        try:
            success = oauth_manager.switch_active_account(email)
            if success:
                self._toast(f"Switched to {email}", COLORS["success"])
                self.refresh_data()
            else:
                self._toast(f"Could not switch to {email}. Token may be invalid — try signing in again.", COLORS["warning"])
        except Exception as ex:
            self._toast(f"Error switching account: {ex}", COLORS["danger"])

    def _disconnect_single_account(self, email: str):
        """Disconnects a single Gmail account."""
        try:
            oauth_manager.disconnect_account(email)
            self._toast(f"Signed out of {email}", COLORS["warning"])
            self.refresh_data()
        except Exception as ex:
            self._toast(f"Error disconnecting: {ex}", COLORS["danger"])

    def _sync_now(self):
        """Triggers an immediate background sync with visual feedback."""
        account = repository.get_active_account()
        if not account:
            self._toast("No active account to sync. Sign in with Google first.", COLORS["warning"])
            return
        self._toast(f"Syncing {account.email}...", COLORS["primary"])
        try:
            scheduler.trigger_sync_now(on_complete=lambda: self._toast("Sync complete!", COLORS["success"]))
        except Exception as ex:
            self._toast(f"Sync error: {ex}", COLORS["danger"])

    def _save_and_connect(self):
        """Saves pasted JSON credentials and then starts OAuth flow."""
        json_text = self.creds_json_field.value or ""
        if not json_text.strip():
            self.creds_error_text.value = "Please paste the contents of your downloaded credentials.json file."
            self.creds_error_text.visible = True
            safe_update(self.creds_error_text)
            return

        try:
            credential_manager.save_client_config_from_json(json_text)
            self.creds_error_text.visible = False
            self._toast("Custom credentials saved! Opening browser for Gmail login...", COLORS["success"])
            self.refresh_data()

            # Now start OAuth flow
            self._start_authentication()
        except Exception as ex:
            self.creds_error_text.value = str(ex)
            self.creds_error_text.visible = True
            safe_update(self.creds_error_text)

    def _pick_credentials_file(self):
        """Opens a file picker dialog for credentials.json."""
        try:
            self.page_ref.run_task(self._pick_credentials_file_async)
        except Exception as ex:
            self._toast(f"File picker error: {ex}", COLORS["danger"])

    async def _pick_credentials_file_async(self) -> None:
        """Uses the Flet 0.86+ async FilePicker API mounted on the page overlay."""
        picker = ft.FilePicker()
        self.page_ref.overlay.append(picker)
        safe_update(self.page_ref)

        try:
            files = await picker.pick_files(
                dialog_title="Select your credentials.json file",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
                allow_multiple=False,
            )

            if not files:
                return

            file_path = files[0].path
            if not file_path:
                self._toast("The selected file is not available as a local file.", COLORS["warning"])
                return

            credential_manager.set_credentials_file(file_path)
            self._toast("Custom credentials loaded. Opening Google sign-in...", COLORS["success"])
            self.refresh_data()
            self._start_authentication()
        except Exception as ex:
            self._toast(f"Could not load credentials: {ex}", COLORS["danger"])
        finally:
            if picker in self.page_ref.overlay:
                self.page_ref.overlay.remove(picker)
                safe_update(self.page_ref)

    def _clear_custom_credentials(self):
        """Reverts to built-in default OAuth credentials."""
        credential_manager.clear_custom_credentials()
        self._toast("Reverted to built-in default credentials.", COLORS["success"])
        self.refresh_data()

    def _reauth_gmail(self):
        """Re-authenticates the current active account or opens the auth dialog."""
        account = repository.get_active_account()
        self._start_authentication(account.email if account else "")

    def _start_authentication(self, login_hint: str = "") -> None:
        """Start browser authentication without blocking the settings UI."""
        self._toast("Opening Google sign-in in your browser...", COLORS["primary"])

        def on_success(email: str):
            try:
                self.page_ref.run_task(self._finish_authentication, email)
            except Exception:
                self.refresh_data()
                self._toast(f"Gmail connected: {email}", COLORS["success"])

        def on_error(message: str):
            try:
                self.page_ref.run_task(self._show_authentication_error, message)
            except Exception:
                self._toast(f"Google sign-in failed: {message}", COLORS["danger"])

        oauth_manager.start_oauth_flow_async(
            on_success=on_success,
            on_error=on_error,
            login_hint=login_hint or None,
        )

    async def _finish_authentication(self, email: str) -> None:
        self.refresh_data()
        self._toast(f"Gmail connected: {email}", COLORS["success"])

    async def _show_authentication_error(self, message: str) -> None:
        self._toast(f"Google sign-in failed: {message[:140]}", COLORS["danger"])

    def _disconnect_gmail(self):
        repository.disconnect_all_accounts()
        self.refresh_data()
        self._toast("Gmail account disconnected", COLORS["warning"])

    # =====================================================================
    # Other Actions
    # =====================================================================
    def _test_ollama(self):
        url = self.ollama_url_field.value.strip()
        model = self.ollama_model_field.value.strip()
        config_manager.config.ollama_url = url
        config_manager.config.ollama_model = model
        config_manager.save()

        client = LocalOllamaClient(base_url=url, default_model=model)
        if client.is_available():
            self._toast("Ollama connection successful! Model ready.", COLORS["success"])
        else:
            self._toast(f"Could not connect to Ollama at {url}", COLORS["danger"])

    def _save_openai_key(self):
        key = self.openai_key_field.value.strip()
        config_manager.set_openai_api_key(key)
        self._toast("OpenAI API key saved!" if key else "OpenAI key cleared", COLORS["success"])

    def _save_gemini_key(self):
        key = self.gemini_key_field.value.strip()
        model = self.gemini_model_field.value.strip()
        config_manager.set_gemini_api_key(key)
        if model:
            config_manager.config.gemini_model = model
            config_manager.save()
        self._toast("Gemini API key saved!" if key else "Gemini key cleared", COLORS["success"])

    def _on_cloud_provider_change(self, e):
        provider = self.cloud_provider_dropdown.value
        config_manager.config.cloud_provider = provider
        config_manager.save()
        self._toast(f"Cloud AI provider set to {provider.capitalize()}", COLORS["success"])

    def _save_profile(self):
        name = self.user_name_field.value.strip()
        company = self.user_company_field.value.strip()
        user_profile_manager.update_profile(name=name, company_name=company)
        self._toast("User profile saved!", COLORS["success"])

    def _export_backup(self):
        try:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_gmailai_{now}.zip"
            with zipfile.ZipFile(backup_path, 'w') as zipf:
                zipf.write(config_manager.db_path, arcname="gmailai.db")
                zipf.write(config_manager.config_file, arcname="config.json")
            self._toast(f"Backup exported: {backup_path}", COLORS["success"])
        except Exception as e:
            self._toast(f"Backup failed: {e}", COLORS["danger"])

    def _seed_demo(self):
        seed_demo_data()
        self._toast("Sample demo dataset refreshed!", COLORS["success"])

    def _toast(self, message: str, color: str):
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(message), bgcolor=color))
        except Exception:
            pass
