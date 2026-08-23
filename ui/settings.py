"""
GmailAI Assistant - Settings & AI Router Configuration for Flet
"""
import zipfile
import datetime
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    padding_all,
    safe_update,
    set_theme_mode,
)
from app.config import config_manager
from core.events import event_bus, EVT_THEME_CHANGED
from authentication.credential_manager import credential_manager
from authentication.oauth_manager import oauth_manager
from database.repository import repository
from database.migrations import seed_demo_data
from ai.local_model import LocalOllamaClient
from memory.user_profile import user_profile_manager


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

        # Section 2: Account Status
        self.account_status_text = ft.Text("Checking account...", size=14, color=COLORS["text_primary"])

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
        self.confidence_val_text = ft.Text(f"{int(config_manager.config.hybrid_confidence_threshold * 100)}%", size=14, weight=ft.FontWeight.BOLD, color=COLORS["primary"])

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

        content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=20,
            controls=[
                # Header
                ft.Text("Settings & Intelligence Control", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),

                # Section 1: AI Engine Router
                self._section_card(
                    title="🧠 Hybrid AI Router Configuration",
                    subtitle="Configure local Ollama execution and optional cloud LLM fallback.",
                    controls=[
                        ft.Row([
                            ft.Text("Active Routing Mode:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.ai_mode_dropdown,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Row([
                            self.ollama_url_field,
                            self.ollama_model_field,
                            ft.ElevatedButton("Test Ollama", icon=ft.Icons.CHECK, bgcolor=COLORS["primary"], color=COLORS["text_primary"], on_click=lambda e: self._test_ollama()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ft.Row([
                            self.openai_key_field,
                            ft.ElevatedButton("Save Key", icon=ft.Icons.KEY, bgcolor=COLORS["secondary"], color=COLORS["text_primary"], on_click=lambda e: self._save_openai_key()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    ],
                ),

                # Section 2: Gmail OAuth Connection
                self._section_card(
                    title="🔐 Gmail OAuth 2.0 Authorization",
                    subtitle="Manage token permissions and Google Cloud authentication.",
                    controls=[
                        ft.Row([
                            ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, size=24, color=COLORS["success"]),
                            self.account_status_text,
                            ft.Container(expand=True),
                            ft.ElevatedButton("Re-Authenticate Gmail", icon=ft.Icons.LOGIN, bgcolor=COLORS["primary"], color=COLORS["text_primary"], on_click=lambda e: self._reauth_gmail()),
                            ft.OutlinedButton("Disconnect", icon=ft.Icons.LOGOUT, style=ft.ButtonStyle(color=COLORS["danger"]), on_click=lambda e: self._disconnect_gmail()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ],
                ),

                # Section 3: Safety Guardrails
                self._section_card(
                    title="🛡️ Safety Guardrails & Thresholds",
                    subtitle="Set minimum confidence required before proposing automated actions.",
                    controls=[
                        ft.Row([
                            ft.Text("Minimum AI Confidence for Auto-Suggestions:", size=13, color=COLORS["text_primary"]),
                            ft.Container(expand=True),
                            self.confidence_val_text,
                        ]),
                        self.confidence_slider,
                    ],
                ),

                # Section 4: Appearance & Theme
                self._section_card(
                    title="🎨 Appearance & Theme Palette",
                    subtitle="Switch between crisp clean Light Mode and Obsidian Midnight Dark Mode.",
                    controls=[
                        ft.Row([
                            ft.Text("Active Theme Mode:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.theme_dropdown,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    ],
                ),

                # Section 5: User Personalization
                self._section_card(
                    title="👤 User Personalization & AI Memory",
                    subtitle="Personalize how the AI Reply Assistant formats greetings, tone, and signatures.",
                    controls=[
                        ft.Row([
                            self.user_name_field,
                            self.user_company_field,
                            ft.ElevatedButton("Save Profile", icon=ft.Icons.SAVE, bgcolor=COLORS["success"], color=COLORS["text_primary"], on_click=lambda e: self._save_profile()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ],
                ),

                # Section 6: Data & Backup Tools
                self._section_card(
                    title="💾 Data Management & Demo Tools",
                    subtitle="Export encrypted database backups or re-seed realistic demo data.",
                    controls=[
                        ft.Row([
                            ft.OutlinedButton("Export Backup Archive (.zip)", icon=ft.Icons.DOWNLOAD, on_click=lambda e: self._export_backup()),
                            ft.OutlinedButton("Reset Demo Dataset", icon=ft.Icons.REFRESH, on_click=lambda e: self._seed_demo()),
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

    def refresh_data(self) -> None:
        account = repository.get_active_account()
        if account:
            self.account_status_text.value = f"Authenticated as {account.email} (Active)"
            self.account_status_text.color = COLORS["success"]
        else:
            self.account_status_text.value = "No active Gmail account connected (Demo Mode active)"
            self.account_status_text.color = COLORS["warning"]

        safe_update(self.page_ref)

    def _section_card(self, title: str, subtitle: str, controls: list) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                ft.Text(subtitle, size=12, color=COLORS["text_secondary"]),
                ft.Divider(height=1, color=COLORS["border"]),
                ft.Column(controls, spacing=12),
            ], spacing=10),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=12,
            padding=20,
        )

    def _on_ai_mode_change(self, e):
        config_manager.config.ai_mode = self.ai_mode_dropdown.value
        config_manager.save()
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(f"AI Mode set to {self.ai_mode_dropdown.value}"), bgcolor=COLORS["success"]))
        except Exception:
            pass

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
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(f"Theme set to {new_theme.capitalize()} Mode"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _test_ollama(self):
        url = self.ollama_url_field.value.strip()
        model = self.ollama_model_field.value.strip()
        config_manager.config.ollama_url = url
        config_manager.config.ollama_model = model
        config_manager.save()

        client = LocalOllamaClient(base_url=url, model=model)
        if client.is_available():
            try:
                self.page_ref.open(ft.SnackBar(ft.Text("Ollama connection successful! Model ready."), bgcolor=COLORS["success"]))
            except Exception:
                pass
        else:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Could not connect to Ollama at {url}"), bgcolor=COLORS["danger"]))
            except Exception:
                pass

    def _save_openai_key(self):
        key = self.openai_key_field.value.strip()
        config_manager.set_openai_api_key(key)
        if key:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text("OpenAI API key saved encrypted!"), bgcolor=COLORS["success"]))
            except Exception:
                pass
        else:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text("OpenAI key cleared"), bgcolor=COLORS["text_secondary"]))
            except Exception:
                pass

    def _reauth_gmail(self):
        try:
            self.page_ref.open(ft.SnackBar(ft.Text("Opening browser for OAuth login..."), bgcolor=COLORS["primary"]))
        except Exception:
            pass
        try:
            oauth_manager.start_auth_flow()
            self.refresh_data()
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"OAuth failed: {e}"), bgcolor=COLORS["danger"]))
            except Exception:
                pass

    def _disconnect_gmail(self):
        repository.disconnect_all_accounts()
        self.refresh_data()
        try:
            self.page_ref.open(ft.SnackBar(ft.Text("Gmail account disconnected"), bgcolor=COLORS["warning"]))
        except Exception:
            pass

    def _on_confidence_change(self, e):
        val = float(e.control.value) / 100.0
        self.confidence_val_text.value = f"{int(e.control.value)}%"
        config_manager.config.hybrid_confidence_threshold = val
        config_manager.save()
        safe_update(self.confidence_val_text)

    def _save_profile(self):
        name = self.user_name_field.value.strip()
        company = self.user_company_field.value.strip()
        user_profile_manager.update_profile(name=name, company_name=company)
        try:
            self.page_ref.open(ft.SnackBar(ft.Text("User profile saved!"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _export_backup(self):
        try:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_gmailai_{now}.zip"
            with zipfile.ZipFile(backup_path, 'w') as zipf:
                zipf.write(config_manager.db_path, arcname="gmailai.db")
                zipf.write(config_manager.config_file, arcname="config.json")
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Backup exported: {backup_path}"), bgcolor=COLORS["success"]))
            except Exception:
                pass
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Backup failed: {e}"), bgcolor=COLORS["danger"]))
            except Exception:
                pass

    def _seed_demo(self):
        seed_demo_data()
        try:
            self.page_ref.open(ft.SnackBar(ft.Text("Sample demo dataset refreshed!"), bgcolor=COLORS["success"]))
        except Exception:
            pass
