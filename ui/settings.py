"""
GmailAI Assistant - Settings & AI Router Configuration for Flet
"""
import os
import zipfile
import datetime
import webbrowser
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    padding_all,
    padding_symmetric,
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


SETUP_STEPS = [
    {
        "step": 1,
        "title": "Open Google Cloud Console",
        "desc": "Go to the Google Cloud Console and create a new project (or select an existing one).",
        "url": "https://console.cloud.google.com/projectcreate",
    },
    {
        "step": 2,
        "title": "Enable Gmail API",
        "desc": "In your project, go to 'APIs & Services' → 'Library' and search for 'Gmail API'. Click it and press 'Enable'.",
        "url": "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
    },
    {
        "step": 3,
        "title": "Configure OAuth Consent Screen",
        "desc": "Go to 'APIs & Services' → 'OAuth consent screen'. Select 'External', fill in the app name (e.g. GmailAI), your email, and save. Add your email as a test user.",
        "url": "https://console.cloud.google.com/apis/credentials/consent",
    },
    {
        "step": 4,
        "title": "Create OAuth Client ID",
        "desc": "Go to 'APIs & Services' → 'Credentials' → 'Create Credentials' → 'OAuth Client ID'. Select 'Desktop app' as the type, name it 'GmailAI', and click Create.",
        "url": "https://console.cloud.google.com/apis/credentials",
    },
    {
        "step": 5,
        "title": "Download & Paste JSON",
        "desc": "Click the download button (⬇) next to your new credential. Open the downloaded JSON file in any text editor, select all, copy, and paste it into the box below.",
    },
]


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

        # Section 2: Gmail OAuth — Account Status + Setup Wizard
        self.account_status_text = ft.Text("Checking account...", size=14, color=COLORS["text_primary"])

        has_creds = credential_manager.get_client_config() is not None
        self.creds_status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if has_creds else ft.Icons.ERROR_OUTLINE,
            size=18,
            color=COLORS["success"] if has_creds else COLORS["warning"],
        )
        self.creds_status_text = ft.Text(
            "Google credentials configured" if has_creds else "No credentials found — follow setup steps below",
            size=12,
            color=COLORS["success"] if has_creds else COLORS["warning"],
        )

        # JSON paste field for credentials
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

        # Build the step-by-step guide
        self.setup_steps_column = ft.Column(
            spacing=8,
            controls=self._build_setup_steps(),
        )

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
                ft.Text("Settings & Intelligence Control", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),

                # Gmail Connection & Setup Wizard
                self._build_gmail_section(),

                # AI Engine Router
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
                            ft.ElevatedButton("Test Ollama", icon=ft.Icons.CHECK, bgcolor=COLORS["primary"], color="#FFFFFF", on_click=lambda e: self._test_ollama()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        ft.Row([
                            self.openai_key_field,
                            ft.ElevatedButton("Save Key", icon=ft.Icons.KEY, bgcolor=COLORS["secondary"], color="#FFFFFF", on_click=lambda e: self._save_openai_key()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    ],
                ),

                # Safety Guardrails
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

                # Appearance
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

                # User Personalization
                self._section_card(
                    title="👤 User Personalization & AI Memory",
                    subtitle="Personalize how the AI Reply Assistant formats greetings, tone, and signatures.",
                    controls=[
                        ft.Row([
                            self.user_name_field,
                            self.user_company_field,
                            ft.ElevatedButton("Save Profile", icon=ft.Icons.SAVE, bgcolor=COLORS["success"], color="#FFFFFF", on_click=lambda e: self._save_profile()),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    ],
                ),

                # Data & Backup
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

    # =====================================================================
    # Gmail Section Builder
    # =====================================================================
    def _build_gmail_section(self) -> ft.Container:
        """Builds the guided Gmail OAuth setup card."""
        return ft.Container(
            content=ft.Column([
                ft.Text("🔐 Gmail Account Connection", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                ft.Text("Connect your Gmail account to unlock AI-powered inbox intelligence.", size=12, color=COLORS["text_secondary"]),
                ft.Divider(height=1, color=COLORS["border"]),

                # Current account status
                ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, size=22, color=COLORS["success"]),
                    self.account_status_text,
                    ft.Container(expand=True),
                    ft.ElevatedButton("Connect Gmail", icon=ft.Icons.LOGIN, bgcolor=COLORS["primary"], color="#FFFFFF", on_click=lambda e: self._reauth_gmail()),
                    ft.OutlinedButton("Disconnect", icon=ft.Icons.LOGOUT, style=ft.ButtonStyle(color=COLORS["danger"]), on_click=lambda e: self._disconnect_gmail()),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),

                # Credentials status
                ft.Row([
                    self.creds_status_icon,
                    self.creds_status_text,
                ], spacing=6),

                ft.Divider(height=1, color=COLORS["border"]),

                # Step-by-step Setup Guide
                ft.Text("Setup Guide (First Time Only)", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                ft.Text("Follow these 5 steps to connect your Gmail. You only need to do this once.", size=12, color=COLORS["text_secondary"]),

                self.setup_steps_column,

                # JSON paste area (Step 5)
                ft.Container(
                    content=ft.Column([
                        ft.Text("Step 5: Paste credentials.json content", size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        self.creds_json_field,
                        self.creds_error_text,
                        ft.Row([
                            ft.ElevatedButton(
                                "Save Credentials & Connect Gmail",
                                icon=ft.Icons.SAVE,
                                bgcolor=COLORS["success"],
                                color="#FFFFFF",
                                on_click=lambda e: self._save_and_connect(),
                            ),
                            ft.OutlinedButton(
                                "Browse File Instead",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda e: self._pick_credentials_file(),
                            ),
                        ], spacing=10),
                    ], spacing=10),
                    bgcolor=COLORS["bg_card_hover"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                    padding=16,
                ),
            ], spacing=12),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=12,
            padding=20,
        )

    def _build_setup_steps(self) -> list:
        """Builds the numbered step guide controls."""
        controls = []
        for step_info in SETUP_STEPS[:4]:  # Steps 1-4 (step 5 is inline with paste box)
            step_num = step_info["step"]
            row_items = [
                ft.Container(
                    content=ft.Text(str(step_num), size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=COLORS["primary"],
                    width=26,
                    height=26,
                    border_radius=13,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Column([
                    ft.Text(step_info["title"], size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                    ft.Text(step_info["desc"], size=11, color=COLORS["text_secondary"]),
                ], expand=True, spacing=2),
            ]
            if "url" in step_info:
                row_items.append(
                    ft.TextButton(
                        "Open",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda e, url=step_info["url"]: self._open_url(url),
                    )
                )
            controls.append(
                ft.Container(
                    content=ft.Row(row_items, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=padding_symmetric(horizontal=10, vertical=8),
                    bgcolor=COLORS["bg_card_hover"],
                    border_radius=8,
                )
            )
        return controls

    # =====================================================================
    # Helpers
    # =====================================================================
    def refresh_data(self) -> None:
        account = repository.get_active_account()
        if account:
            self.account_status_text.value = f"Authenticated as {account.email} (Active)"
            self.account_status_text.color = COLORS["success"]
        else:
            self.account_status_text.value = "No active Gmail account connected (Demo Mode active)"
            self.account_status_text.color = COLORS["warning"]

        has_creds = credential_manager.get_client_config() is not None
        self.creds_status_icon.name = ft.Icons.CHECK_CIRCLE if has_creds else ft.Icons.ERROR_OUTLINE
        self.creds_status_icon.color = COLORS["success"] if has_creds else COLORS["warning"]
        self.creds_status_text.value = "Google credentials configured" if has_creds else "No credentials found — follow setup steps below"
        self.creds_status_text.color = COLORS["success"] if has_creds else COLORS["warning"]

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
        config_manager.config.hybrid_confidence_threshold = val
        config_manager.save()
        safe_update(self.confidence_val_text)

    # =====================================================================
    # Gmail Auth Actions
    # =====================================================================
    def _save_and_connect(self):
        """Saves pasted JSON credentials and then starts OAuth flow."""
        json_text = self.creds_json_field.value or ""
        if not json_text.strip():
            self.creds_error_text.value = "Please paste the contents of your downloaded credentials.json file."
            self.creds_error_text.visible = True
            safe_update(self.creds_error_text)
            return

        try:
            saved_path = credential_manager.save_client_config_from_json(json_text)
            self.creds_error_text.visible = False
            self._toast("Credentials saved! Opening browser for Gmail login...", COLORS["success"])
            self.refresh_data()

            # Now start OAuth flow
            try:
                email = oauth_manager.start_auth_flow()
                if email:
                    self._toast(f"Gmail connected: {email}", COLORS["success"])
                self.refresh_data()
            except Exception as ex:
                self._toast(f"OAuth flow failed: {ex}", COLORS["danger"])
        except Exception as ex:
            self.creds_error_text.value = str(ex)
            self.creds_error_text.visible = True
            safe_update(self.creds_error_text)

    def _pick_credentials_file(self):
        """Opens a file picker dialog for credentials.json."""
        def on_result(e: ft.FilePickerResultEvent):
            if e.files and len(e.files) > 0:
                file_path = e.files[0].path
                try:
                    credential_manager.set_credentials_file(file_path)
                    self._toast("Credentials file loaded! Opening browser for Gmail login...", COLORS["success"])
                    self.refresh_data()

                    try:
                        email = oauth_manager.start_auth_flow()
                        if email:
                            self._toast(f"Gmail connected: {email}", COLORS["success"])
                        self.refresh_data()
                    except Exception as ex:
                        self._toast(f"OAuth flow failed: {ex}", COLORS["danger"])
                except Exception as ex:
                    self._toast(f"Invalid credentials file: {ex}", COLORS["danger"])

        try:
            picker = ft.FilePicker(on_result=on_result)
            self.page_ref.overlay.append(picker)
            safe_update(self.page_ref)
            picker.pick_files(
                dialog_title="Select your credentials.json file",
                allowed_extensions=["json"],
                allow_multiple=False,
            )
        except Exception as ex:
            self._toast(f"File picker error: {ex}", COLORS["danger"])

    def _reauth_gmail(self):
        has_creds = credential_manager.get_client_config() is not None
        if not has_creds:
            self._toast("Please complete the setup steps first to provide your Google credentials.", COLORS["warning"])
            return

        self._toast("Opening browser for Gmail login...", COLORS["primary"])
        try:
            email = oauth_manager.start_auth_flow()
            if email:
                self._toast(f"Gmail connected: {email}", COLORS["success"])
            self.refresh_data()
        except Exception as e:
            self._toast(f"OAuth failed: {e}", COLORS["danger"])

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
