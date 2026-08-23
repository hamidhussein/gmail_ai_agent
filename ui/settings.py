"""
GmailAI Assistant - Settings & AI Router Configuration
"""
import zipfile
import shutil
import datetime
import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional
from resources.styles.theme import FONTS, THEME
from app.config import config_manager
from authentication.credential_manager import credential_manager
from authentication.oauth_manager import oauth_manager
from database.repository import repository
from database.migrations import seed_demo_data
from ai.local_model import LocalOllamaClient
from ai.cloud_model import CloudOpenAIClient
from memory.user_profile import user_profile_manager
from core.security import safety_guard
from ui.components.toast import ToastNotification


class SettingsView(ctk.CTkFrame):
    """Configuration control panel for AI models, Gmail OAuth, safety rules, and backups."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 16))

        ctk.CTkLabel(
            header,
            text="⚙️ Settings & Intelligence Control",
            font=FONTS["h1"],
            text_color="#F8FAFC",
        ).pack(anchor="w")

        # Scrollable container for settings sections
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=28, pady=(0, 16))

        self._build_ai_router_section()
        self._build_oauth_section()
        self._build_safety_section()
        self._build_profile_section()
        self._build_backup_section()

    # --- Section 1: AI Router Configuration ---
    def _build_ai_router_section(self) -> None:
        card = self._create_card("🧠 Hybrid AI Router & Engine Configuration")

        # AI Mode Selector
        row_mode = ctk.CTkFrame(card, fg_color="transparent")
        row_mode.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row_mode, text="Active AI Mode:", font=FONTS["body_bold"], width=160, anchor="w").pack(side="left")
        self.ai_mode_menu = ctk.CTkOptionMenu(
            row_mode,
            values=["HYBRID", "LOCAL_ONLY", "CLOUD_ONLY", "HEURISTIC"],
            command=self._on_ai_mode_changed,
            fg_color=THEME["dark"]["primary"],
        )
        self.ai_mode_menu.set(config_manager.config.ai_mode)
        self.ai_mode_menu.pack(side="left", padx=8)

        # Local Ollama Settings
        row_ollama = ctk.CTkFrame(card, fg_color="transparent")
        row_ollama.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row_ollama, text="Local Ollama URL:", font=FONTS["body"], width=160, anchor="w").pack(side="left")
        self.ollama_url_entry = ctk.CTkEntry(row_ollama, width=220, fg_color="#0F172A")
        self.ollama_url_entry.insert(0, config_manager.config.ollama_url)
        self.ollama_url_entry.pack(side="left", padx=8)

        self.ollama_model_entry = ctk.CTkEntry(row_ollama, width=140, fg_color="#0F172A")
        self.ollama_model_entry.insert(0, config_manager.config.ollama_model)
        self.ollama_model_entry.pack(side="left", padx=8)

        test_ollama_btn = ctk.CTkButton(
            row_ollama,
            text="⚡ Test Local AI",
            font=FONTS["body_sm_bold"],
            width=110,
            fg_color="#334155",
            hover_color="#475569",
            command=self._test_ollama,
        )
        test_ollama_btn.pack(side="left", padx=8)

        # OpenAI Settings
        row_openai = ctk.CTkFrame(card, fg_color="transparent")
        row_openai.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row_openai, text="OpenAI API Key:", font=FONTS["body"], width=160, anchor="w").pack(side="left")
        self.openai_key_entry = ctk.CTkEntry(
            row_openai,
            width=220,
            show="•",
            placeholder_text="sk-...",
            fg_color="#0F172A",
        )
        existing_key = config_manager.get_openai_api_key()
        if existing_key:
            self.openai_key_entry.insert(0, existing_key)
        self.openai_key_entry.pack(side="left", padx=8)

        self.openai_model_entry = ctk.CTkEntry(row_openai, width=140, fg_color="#0F172A")
        self.openai_model_entry.insert(0, config_manager.config.openai_model)
        self.openai_model_entry.pack(side="left", padx=8)

        test_cloud_btn = ctk.CTkButton(
            row_openai,
            text="☁️ Save & Test Cloud",
            font=FONTS["body_sm_bold"],
            width=130,
            fg_color="#334155",
            hover_color="#475569",
            command=self._save_and_test_cloud,
        )
        test_cloud_btn.pack(side="left", padx=8)

    # --- Section 2: Google OAuth & Credentials ---
    def _build_oauth_section(self) -> None:
        card = self._create_card("🔐 Gmail Authentication & Accounts")

        row_auth = ctk.CTkFrame(card, fg_color="transparent")
        row_auth.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row_auth, text="Google credentials.json:", font=FONTS["body"], width=160, anchor="w").pack(side="left")
        
        self.creds_path_lbl = ctk.CTkLabel(
            row_auth,
            text=config_manager.config.credentials_path or "No file selected (Optional for Demo)",
            font=FONTS["body_sm"],
            text_color="#94A3B8",
            width=280,
            anchor="w",
        )
        self.creds_path_lbl.pack(side="left", padx=8)

        browse_btn = ctk.CTkButton(
            row_auth,
            text="📁 Browse File...",
            font=FONTS["body_sm"],
            width=120,
            fg_color="#334155",
            hover_color="#475569",
            command=self._browse_credentials,
        )
        browse_btn.pack(side="left", padx=8)

        login_btn = ctk.CTkButton(
            row_auth,
            text="🔑 Google Login",
            font=FONTS["body_sm_bold"],
            width=120,
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            command=self._start_google_login,
        )
        login_btn.pack(side="left", padx=8)

        # Demo Mode Button
        row_demo = ctk.CTkFrame(card, fg_color="transparent")
        row_demo.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row_demo, text="Demo / Testing Mode:", font=FONTS["body"], width=160, anchor="w").pack(side="left")

        seed_btn = ctk.CTkButton(
            row_demo,
            text="🧪 Reset / Seed Realistic Demo Data",
            font=FONTS["body_sm_bold"],
            width=240,
            fg_color="#059669",
            hover_color="#047857",
            command=self._seed_demo_action,
        )
        seed_btn.pack(side="left", padx=8)

    # --- Section 3: Safety Guardrails ---
    def _build_safety_section(self) -> None:
        card = self._create_card("🛡️ Safety Guardrails & Protected Domains")

        row_info = ctk.CTkFrame(card, fg_color="transparent")
        row_info.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(
            row_info,
            text="Protected entities (Banking, Legal, Medical, Gov) cannot be deleted or auto-archived without approval.",
            font=FONTS["body_sm"],
            text_color="#94A3B8",
        ).pack(anchor="w")

        # Protected Domains List Display
        row_doms = ctk.CTkFrame(card, fg_color="transparent")
        row_doms.pack(fill="x", padx=16, pady=8)

        self.dom_entry = ctk.CTkEntry(
            row_doms,
            placeholder_text="Add domain: e.g., company.com",
            font=FONTS["body_sm"],
            width=240,
            fg_color="#0F172A",
        )
        self.dom_entry.pack(side="left", padx=(0, 8))

        add_dom_btn = ctk.CTkButton(
            row_doms,
            text="➕ Protect Domain",
            font=FONTS["body_sm_bold"],
            width=140,
            fg_color="#334155",
            hover_color="#475569",
            command=self._add_domain,
        )
        add_dom_btn.pack(side="left")

    # --- Section 4: User Profile ---
    def _build_profile_section(self) -> None:
        card = self._create_card("👤 User Profile & AI Reply Signature")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(row, text="Display Name:", font=FONTS["body"], width=140, anchor="w").pack(side="left")
        self.name_entry = ctk.CTkEntry(row, width=200, fg_color="#0F172A")
        self.name_entry.insert(0, user_profile_manager.profile.name)
        self.name_entry.pack(side="left", padx=8)

        save_prof_btn = ctk.CTkButton(
            row,
            text="Save Profile",
            font=FONTS["body_sm_bold"],
            width=110,
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            command=self._save_profile,
        )
        save_prof_btn.pack(side="left", padx=8)

    # --- Section 5: Backup & Export ---
    def _build_backup_section(self) -> None:
        card = self._create_card("💾 Backup & Disaster Recovery")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)

        export_btn = ctk.CTkButton(
            row,
            text="📦 Export Backup (ZIP)",
            font=FONTS["body_sm_bold"],
            width=180,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._export_backup,
        )
        export_btn.pack(side="left", padx=(0, 12))

    def _create_card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        card.pack(fill="x", pady=8)

        c_header = ctk.CTkFrame(card, fg_color="transparent")
        c_header.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(c_header, text=title, font=FONTS["h3"], text_color="#F8FAFC").pack(anchor="w")
        return card

    # --- Handlers ---
    def _on_ai_mode_changed(self, new_mode: str) -> None:
        config_manager.config.ai_mode = new_mode
        config_manager.save()
        ToastNotification.show(self.winfo_toplevel(), f"AI Router set to {new_mode}", "info")

    def _test_ollama(self) -> None:
        url = self.ollama_url_entry.get().strip()
        model = self.ollama_model_entry.get().strip()
        config_manager.config.ollama_url = url
        config_manager.config.ollama_model = model
        config_manager.save()

        client = LocalOllamaClient(base_url=url, default_model=model)
        if client.is_available():
            ToastNotification.show(self.winfo_toplevel(), f"Ollama is running at {url}!", "success")
        else:
            ToastNotification.show(self.winfo_toplevel(), f"Could not connect to Ollama at {url}", "error")

    def _save_and_test_cloud(self) -> None:
        key = self.openai_key_entry.get().strip()
        model = self.openai_model_entry.get().strip()
        if key:
            config_manager.set_openai_api_key(key)
        config_manager.config.openai_model = model
        config_manager.save()

        client = CloudOpenAIClient(api_key=key, default_model=model)
        if client.test_connection():
            ToastNotification.show(self.winfo_toplevel(), "OpenAI API connection verified!", "success")
        else:
            ToastNotification.show(self.winfo_toplevel(), "OpenAI Key test failed or rate limited.", "error")

    def _browse_credentials(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Google OAuth credentials.json",
            filetypes=[("JSON Files", "*.json")],
        )
        if file_path:
            try:
                credential_manager.set_credentials_file(file_path)
                self.creds_path_lbl.configure(text=file_path)
                ToastNotification.show(self.winfo_toplevel(), "Credentials saved successfully.", "success")
            except Exception as e:
                ToastNotification.show(self.winfo_toplevel(), str(e), "error")

    def _start_google_login(self) -> None:
        try:
            email = oauth_manager.start_oauth_flow()
            ToastNotification.show(self.winfo_toplevel(), f"Connected as {email}", "success")
        except Exception as e:
            ToastNotification.show(self.winfo_toplevel(), f"Login failed: {e}", "error")

    def _seed_demo_action(self) -> None:
        seed_demo_data()
        ToastNotification.show(self.winfo_toplevel(), "Realistic demo emails and suggestions loaded!", "success")

    def _add_domain(self) -> None:
        dom = self.dom_entry.get().strip()
        if dom:
            safety_guard.add_protected_domain(dom)
            if dom not in config_manager.config.protected_domains:
                config_manager.config.protected_domains.append(dom)
                config_manager.save()
            self.dom_entry.delete(0, "end")
            ToastNotification.show(self.winfo_toplevel(), f"Domain '{dom}' added to safety protection list.", "success")

    def _save_profile(self) -> None:
        name = self.name_entry.get().strip()
        user_profile_manager.update_profile(name=name)
        ToastNotification.show(self.winfo_toplevel(), "Profile updated!", "success")

    def _export_backup(self) -> None:
        out_file = filedialog.asksaveasfilename(
            title="Save Backup Archive",
            defaultextension=".zip",
            initialfile=f"gmailai_backup_{datetime.date.today().strftime('%Y%m%d')}.zip",
            filetypes=[("ZIP Archive", "*.zip")],
        )
        if out_file:
            try:
                with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                    if config_manager.db_path.exists():
                        zipf.write(config_manager.db_path, arcname="gmailai.db")
                    if config_manager.config_file.exists():
                        zipf.write(config_manager.config_file, arcname="config.json")
                    if user_profile_manager.profile_path.exists():
                        zipf.write(user_profile_manager.profile_path, arcname="user_profile.json")

                ToastNotification.show(self.winfo_toplevel(), "Backup archive created successfully!", "success")
            except Exception as e:
                ToastNotification.show(self.winfo_toplevel(), f"Export failed: {e}", "error")
