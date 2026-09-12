"""
GmailAI Assistant - 1-Click Google Sign-In & Onboarding Modal for Flet
"""
import flet as ft
from typing import Optional, Callable
from resources.styles.theme import (
    COLORS,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
)
from authentication.credential_manager import credential_manager
from authentication.oauth_manager import oauth_manager
from database.repository import repository


class GoogleAuthDialog(ft.AlertDialog):
    """
    User-friendly modal allowing non-technical users to sign in with Google in 1 click.
    Shows real-time status when the browser opens and asks for permissions.
    """

    def __init__(
        self,
        page: ft.Page,
        on_authenticated: Optional[Callable[[str], None]] = None,
        reason: str = "",
        account_email: str = "",
    ):
        self.page_ref = page
        self.on_authenticated = on_authenticated
        self.is_authenticating = False
        self.account_email = account_email

        # Status text & spinner
        self.status_spinner = ft.ProgressRing(width=18, height=18, stroke_width=2.5, color=COLORS["primary"], visible=False)
        self.status_text = ft.Text(
            reason or "Click below to securely sign in with your Google account.",
            size=13,
            color=COLORS["text_secondary"],
            text_align=ft.TextAlign.CENTER,
        )

        has_creds = credential_manager.get_client_config() is not None

        # Sign-in button (Google Blue style)
        google_action = COLORS["primary"]
        self.sign_in_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.LOCK_OPEN, size=18, color="#FFFFFF"),
                ft.Text(
                    "Reconnect Google" if reason else "Sign in with Google",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color="#FFFFFF",
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            bgcolor=google_action,
            border_radius=8,
            padding=padding_symmetric(horizontal=24, vertical=12),
            on_click=self._start_sign_in,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=12, color=google_action + "40", offset=ft.Offset(0, 3)),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        def on_btn_hover(e):
            if not self.is_authenticating:
                self.sign_in_btn.bgcolor = COLORS["primary_hover"] if e.data == "true" else google_action
                safe_update(self.sign_in_btn)

        self.sign_in_btn.on_hover = on_btn_hover

        # Quick Paste credentials section (collapsible if no credentials found)
        self.creds_paste_field = ft.TextField(
            hint_text="Paste your Google OAuth credentials.json here...",
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            text_size=11,
            content_padding=8,
            visible=not has_creds,
        )
        self.creds_notice = ft.Text(
            "First time? Paste your Google OAuth credentials or explore with Demo Mode." if not has_creds else "",
            size=11,
            color=COLORS["text_muted"],
            visible=not has_creds,
        )

        modal_body = ft.Container(
            width=480,
            padding=padding_all(24),
            content=ft.Column([
                # Google / GmailAI Header
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.ALL_INCLUSIVE, size=24, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=8,
                        border_radius=10,
                        shadow=ft.BoxShadow(spread_radius=0, blur_radius=6, color=COLORS["primary"] + "40", offset=ft.Offset(0, 2)),
                    ),
                    ft.Column([
                        ft.Text(
                            "Reconnect Gmail" if reason else "Sign in to GmailAI",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS["text_primary"],
                        ),
                        ft.Text("Privacy-first AI intelligence for your enterprise workspace", size=12, color=COLORS["text_secondary"]),
                    ], spacing=2),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),

                ft.Divider(height=1, color=COLORS["border"]),

                # Status info card
                ft.Container(
                    content=ft.Row([
                        self.status_spinner,
                        self.status_text,
                    ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    bgcolor=COLORS["bg_card_hover"],
                    padding=padding_symmetric(horizontal=14, vertical=10),
                    border_radius=8,
                ),

                # Sign In Button
                self.sign_in_btn,

                # Optional Credentials paste for initial setup
                self.creds_notice,
                self.creds_paste_field,

                # Demo mode fallback
                ft.Row([
                    ft.TextButton(
                        "Continue with Demo Data",
                        icon=ft.Icons.VISIBILITY_OUTLINED,
                        on_click=self._continue_demo,
                    ),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Cancel",
                        on_click=lambda e: self._close_dialog(),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=14, tight=True),
        )

        super().__init__(
            content=modal_body,
            actions=[],
            modal=True,
            bgcolor=COLORS["bg_card"],
            shape=ft.RoundedRectangleBorder(radius=14),
        )

    def _start_sign_in(self, e):
        """Starts Google OAuth authorization flow asynchronously without freezing the UI."""
        if self.is_authenticating:
            return

        # Check if credentials exist or if user pasted them
        has_creds = credential_manager.get_client_config() is not None
        pasted_text = (self.creds_paste_field.value or "").strip()

        if not has_creds:
            if pasted_text:
                try:
                    credential_manager.save_client_config_from_json(pasted_text)
                    has_creds = True
                except Exception as ex:
                    self.status_text.value = f"Invalid credentials: {ex}"
                    self.status_text.color = COLORS["danger"]
                    safe_update(self.status_text)
                    return
            else:
                self.creds_paste_field.visible = True
                self.creds_notice.visible = True
                self.creds_notice.value = "Please paste your Google OAuth credentials JSON to connect your real Gmail account."
                self.creds_notice.color = COLORS["warning"]
                safe_update(self)
                return

        self.is_authenticating = True
        self.status_spinner.visible = True
        account_hint = f" for {self.account_email}" if self.account_email else ""
        self.status_text.value = f"Opening Google{account_hint}... Complete sign-in in your browser."
        self.status_text.color = COLORS["primary"]
        self.sign_in_btn.bgcolor = COLORS["border"]
        safe_update(self)

        def _on_success(email: str):
            try:
                self.page_ref.run_task(self._finish_success, email)
            except Exception:
                self._finish_success_now(email)

        def _on_error(err_msg: str):
            try:
                self.page_ref.run_task(self._finish_error, err_msg)
            except Exception:
                self._finish_error_now(err_msg)

        oauth_manager.start_oauth_flow_async(
            on_success=_on_success,
            on_error=_on_error,
            login_hint=self.account_email or None,
        )

    async def _finish_success(self, email: str) -> None:
        self._finish_success_now(email)

    def _finish_success_now(self, email: str) -> None:
        self.is_authenticating = False
        self.status_spinner.visible = False
        self.status_text.value = f"Success! Connected as {email}"
        self.status_text.color = COLORS["success"]
        safe_update(self)

        if self.page_ref:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Welcome! Connected as {email}"), bgcolor=COLORS["success"]))
            except Exception:
                pass

        if self.on_authenticated:
            self.on_authenticated(email)

        self._close_dialog()

    async def _finish_error(self, err_msg: str) -> None:
        self._finish_error_now(err_msg)

    def _finish_error_now(self, err_msg: str) -> None:
        self.is_authenticating = False
        self.status_spinner.visible = False
        clean_error = err_msg
        if "access_denied" in err_msg.lower():
            clean_error = "Google sign-in was cancelled. You can try again when ready."
        elif "address already in use" in err_msg.lower():
            clean_error = "Could not open the local sign-in callback. Close other sign-in windows and retry."
        self.status_text.value = f"Sign-in failed: {clean_error[:140]}"
        self.status_text.color = COLORS["danger"]
        self.sign_in_btn.bgcolor = COLORS["primary"]
        safe_update(self)

    def _continue_demo(self, e):
        self._close_dialog()
        if self.page_ref:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text("Exploring in Demo Mode with sample dataset"), bgcolor=COLORS["primary"]))
            except Exception:
                pass

    def _close_dialog(self):
        try:
            self.page_ref.close(self)
        except Exception:
            pass
