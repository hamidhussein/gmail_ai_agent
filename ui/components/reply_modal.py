"""
GmailAI Assistant - AI Reply Assistant Dialog for Flet
"""
import threading
import flet as ft
from typing import Dict, Any, Optional, Callable
from resources.styles.theme import (
    COLORS,
    border_all,
    border_only,
    padding_symmetric,
    padding_all,
    safe_update,
)
from app.constants import ReplyTone
from ai.reply_generator import reply_generator
from gmail.actions import gmail_actions
from memory.user_profile import user_profile_manager


class ReplyDialog(ft.AlertDialog):
    """Modern AI Reply Assistant dialog with tone controls, live generation, and one-click draft creation."""

    def __init__(
        self,
        page: ft.Page,
        email_data: Dict[str, Any],
        on_draft_created: Optional[Callable[[str], None]] = None,
    ):
        self.page_ref = page
        self.email_data = email_data
        self.on_draft_created = on_draft_created
        self.selected_tone = ReplyTone.PROFESSIONAL.value
        self._generation_version = 0

        # Controls
        self.tone_dropdown = ft.Dropdown(
            value=self.selected_tone,
            options=[ft.DropdownOption(t.value) for t in ReplyTone],
            width=160,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            content_padding=10,
            on_select=self._on_tone_changed,
        )

        self.custom_prompt = ft.TextField(
            hint_text="Custom instructions (e.g. 'Confirm meeting, ask for slide deck')",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            expand=True,
            content_padding=10,
        )

        self.spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLORS["warning"], visible=True)
        self.status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=COLORS["success"], visible=False)
        self.status_text = ft.Text("AI is drafting your response...", size=12, color=COLORS["warning"], visible=True)
        self.char_count_text = ft.Text("0 chars", size=11, color=COLORS["text_muted"])

        self.reply_editor = ft.TextField(
            multiline=True,
            min_lines=8,
            max_lines=12,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            on_change=self._on_text_changed,
        )

        self.regen_btn = ft.ElevatedButton(
            "Regenerate",
            icon=ft.Icons.AUTO_AWESOME,
            bgcolor=COLORS["primary"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True,
            on_click=lambda e: self._trigger_generation(),
        )

        self.draft_btn = ft.ElevatedButton(
            "Create Gmail Draft",
            icon=ft.Icons.SAVE_OUTLINED,
            bgcolor=COLORS["accent"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True,
            on_click=lambda e: self._save_draft(),
        )

        sender = self.email_data.get("sender_name") or self.email_data.get("sender", "Unknown")
        subject = self.email_data.get("subject", "(No Subject)")

        reply_info = ft.Container(
            content=ft.Column(
                spacing=3,
                controls=[
                    ft.Row([
                        ft.Text("Replying to:", size=11, color=COLORS["text_muted"], weight=ft.FontWeight.W_500),
                        ft.Text(sender, weight=ft.FontWeight.BOLD, size=13, color=COLORS["text_primary"]),
                    ], spacing=6),
                    ft.Row([
                        ft.Text("Subject:", size=11, color=COLORS["text_muted"], weight=ft.FontWeight.W_500),
                        ft.Text(subject, size=12, color=COLORS["text_secondary"], no_wrap=True, expand=True),
                    ], spacing=6),
                ],
            ),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["primary"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            padding=padding_symmetric(horizontal=14, vertical=10),
            border_radius=8,
        )

        content = ft.Container(
            width=680,
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    reply_info,
                    ft.Row(
                        controls=[
                            ft.Text("Tone:", size=13, weight=ft.FontWeight.W_600, color=COLORS["text_primary"]),
                            self.tone_dropdown,
                            self.custom_prompt,
                            self.regen_btn,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    ft.Row(
                        controls=[
                            self.spinner,
                            self.status_icon,
                            self.status_text,
                            ft.Container(expand=True),
                            self.char_count_text,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    self.reply_editor,
                ],
            ),
        )

        header = ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.AUTO_AWESOME, color="#FFFFFF", size=18),
                bgcolor=COLORS["primary"],
                padding=6,
                border_radius=8,
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=6, color=COLORS["primary"] + "40", offset=ft.Offset(0, 2)),
            ),
            ft.Column([
                ft.Text("AI Reply Assistant", size=17, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                ft.Text("Generates context-aware, personalized email responses in 1 click", size=11, color=COLORS["text_secondary"]),
            ], spacing=2),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        super().__init__(
            title=header,
            content=content,
            actions=[
                ft.TextButton("Close", on_click=lambda e: self.close()),
                ft.TextButton("Copy Text", icon=ft.Icons.COPY_ALL_OUTLINED, on_click=lambda e: self._copy_text()),
                self.draft_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=COLORS["bg_main"],
            shape=ft.RoundedRectangleBorder(radius=12),
        )

        self._start_worker_generation()

    def _on_tone_changed(self, e):
        self.selected_tone = self.tone_dropdown.value
        self._trigger_generation()

    def _on_text_changed(self, e):
        count = len((self.reply_editor.value or "").strip())
        self.char_count_text.value = f"{count:,} chars"
        safe_update(self.char_count_text)

    def _trigger_generation(self) -> None:
        self.spinner.visible = True
        self.status_icon.visible = False
        self.status_text.visible = True
        self.status_text.value = "AI is drafting your response..."
        self.status_text.color = COLORS["warning"]
        self.regen_btn.disabled = True
        safe_update(self.page_ref)
        self._start_worker_generation()

    def _start_worker_generation(self) -> None:
        self._generation_version += 1
        generation_version = self._generation_version

        def worker():
            draft = ""
            source = ""
            generation_error = None
            try:
                tone_val = ReplyTone(self.selected_tone)
                notes = (self.custom_prompt.value or "").strip()
                user_name = user_profile_manager.profile.name or "Alex"

                draft, source = reply_generator.generate_reply_with_source(
                    sender_name=self.email_data.get("sender_name", ""),
                    sender_email=self.email_data.get("sender", ""),
                    subject=self.email_data.get("subject", ""),
                    original_body=self.email_data.get("body_plain", ""),
                    tone=tone_val,
                    user_name=user_name,
                    extra_instructions=notes if notes else None,
                )
            except Exception as ex:
                generation_error = ex

            async def _apply_draft():
                self._apply_generation_result(generation_version, draft, source, generation_error)

            try:
                self.page_ref.run_task(_apply_draft)
            except Exception:
                self._apply_generation_result(generation_version, draft, source, generation_error)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_generation_result(self, version: int, draft: str, source: str, error=None) -> None:
        """Apply only the newest generation result and always restore UI controls."""
        if version != self._generation_version:
            return
        self.spinner.visible = False
        self.regen_btn.disabled = False
        if error is not None or not draft.strip():
            self.status_icon.visible = False
            self.status_text.value = f"Could not generate reply: {error or 'empty response'}"
            self.status_text.color = COLORS["danger"]
            self.draft_btn.disabled = True
        else:
            self.reply_editor.value = draft
            self.status_icon.visible = True
            self.status_text.value = f"Draft ready for review • {source}"
            self.status_text.color = COLORS["success"]
            self.char_count_text.value = f"{len(draft.strip()):,} chars"
            self.draft_btn.disabled = False
        safe_update(self.page_ref)

    def _copy_text(self) -> None:
        try:
            self.page_ref.set_clipboard(self.reply_editor.value or "")
            self.page_ref.open(ft.SnackBar(ft.Text("Copied draft to clipboard!"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _save_draft(self) -> None:
        if not (self.reply_editor.value or "").strip():
            self.status_icon.visible = False
            self.status_text.visible = True
            self.status_text.value = "Generate or enter a reply before creating a Gmail draft."
            self.status_text.color = COLORS["danger"]
            safe_update(self.page_ref)
            return

        self.draft_btn.disabled = True
        self.spinner.visible = True
        self.status_icon.visible = False
        self.status_text.visible = True
        self.status_text.value = "Creating Gmail draft..."
        self.status_text.color = COLORS["warning"]
        safe_update(self.page_ref)

        def worker():
            save_err = None
            try:
                gmail_actions.create_draft(
                    recipient=self.email_data.get("sender", ""),
                    subject=self.email_data.get("subject", ""),
                    body_text=self.reply_editor.value or "",
                    thread_id=self.email_data.get("thread_id"),
                )
            except Exception as ex:
                save_err = ex

            async def _apply_result():
                self.spinner.visible = False
                if save_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Gmail draft saved successfully!"
                    self.status_text.color = COLORS["success"]
                    if self.on_draft_created:
                        self.on_draft_created(self.email_data.get("message_id", ""))
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Gmail draft failed: {save_err}"
                    self.status_text.color = COLORS["danger"]
                self.draft_btn.disabled = False
                safe_update(self.page_ref)

            try:
                self.page_ref.run_task(_apply_result)
            except Exception:
                self.spinner.visible = False
                if save_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Gmail draft saved successfully!"
                    self.status_text.color = COLORS["success"]
                    if self.on_draft_created:
                        self.on_draft_created(self.email_data.get("message_id", ""))
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Gmail draft failed: {save_err}"
                    self.status_text.color = COLORS["danger"]
                self.draft_btn.disabled = False
                safe_update(self.page_ref)

        threading.Thread(target=worker, daemon=True).start()

    def close(self) -> None:
        try:
            self.page_ref.close(self)
        except Exception:
            pass
