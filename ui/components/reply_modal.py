"""
GmailAI Assistant - AI Reply Assistant Dialog for Flet
"""
import threading
import flet as ft
from typing import Dict, Any, Optional, Callable
from resources.styles.theme import COLORS
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

        # Controls
        self.tone_dropdown = ft.Dropdown(
            value=self.selected_tone,
            options=[ft.dropdown.Option(t.value) for t in ReplyTone],
            width=160,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            content_padding=10,
            on_change=self._on_tone_changed,
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

        self.spinner = ft.ProgressRing(width=18, height=18, stroke_width=2, color=COLORS["warning"], visible=False)
        self.status_text = ft.Text("Generating draft...", size=12, color=COLORS["warning"], visible=False)
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
            color=COLORS["text_primary"],
            on_click=lambda e: self._trigger_generation(),
        )

        self.draft_btn = ft.ElevatedButton(
            "Create Gmail Draft",
            icon=ft.Icons.SAVE_OUTLINED,
            bgcolor=COLORS["success"],
            color=COLORS["text_primary"],
            on_click=lambda e: self._save_draft(),
        )

        sender = self.email_data.get("sender_name") or self.email_data.get("sender", "Unknown")
        subject = self.email_data.get("subject", "(No Subject)")

        content = ft.Container(
            width=680,
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    ft.Container(
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(f"Replying to: {sender}", weight=ft.FontWeight.BOLD, size=14, color=COLORS["text_primary"]),
                                ft.Text(f"Subject: {subject}", size=12, color=COLORS["text_secondary"], no_wrap=True),
                            ],
                        ),
                        bgcolor=COLORS["bg_card_hover"],
                        padding=12,
                        border_radius=8,
                    ),
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
                            self.status_text,
                            ft.Container(expand=True),
                            self.char_count_text,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.reply_editor,
                ],
            ),
        )

        super().__init__(
            title=ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME, color=COLORS["primary"], size=22),
                ft.Text("AI Reply Assistant", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
            ]),
            content=content,
            actions=[
                ft.TextButton("Close", on_click=lambda e: self.close()),
                ft.TextButton("Copy Text", icon=ft.Icons.COPY_ALL_OUTLINED, on_click=lambda e: self._copy_text()),
                self.draft_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=COLORS["bg_main"],
        )

        self._trigger_generation()

    def _on_tone_changed(self, e):
        self.selected_tone = self.tone_dropdown.value
        self._trigger_generation()

    def _on_text_changed(self, e):
        count = len((self.reply_editor.value or "").strip())
        self.char_count_text.value = f"{count:,} chars"
        if self.page:
            self.char_count_text.update()

    def _trigger_generation(self) -> None:
        self.spinner.visible = True
        self.status_text.visible = True
        self.status_text.value = "AI is drafting your response..."
        self.status_text.color = COLORS["warning"]
        self.regen_btn.disabled = True
        if self.page:
            self.page.update()

        def worker():
            tone_val = ReplyTone(self.selected_tone)
            notes = (self.custom_prompt.value or "").strip()
            user_name = user_profile_manager.profile.name or "Alex"

            draft = reply_generator.generate_reply(
                sender_name=self.email_data.get("sender_name", ""),
                sender_email=self.email_data.get("sender", ""),
                subject=self.email_data.get("subject", ""),
                original_body=self.email_data.get("body_plain", ""),
                tone=tone_val,
                user_name=user_name,
                extra_instructions=notes if notes else None,
            )

            self.reply_editor.value = draft
            self.spinner.visible = False
            self.status_text.value = "Draft ready"
            self.status_text.color = COLORS["success"]
            self.regen_btn.disabled = False
            self.char_count_text.value = f"{len(draft.strip()):,} chars"
            if self.page:
                self.page.update()

        threading.Thread(target=worker, daemon=True).start()

    def _copy_text(self) -> None:
        if self.page:
            self.page.set_clipboard(self.reply_editor.value or "")
            self.page.open(ft.SnackBar(ft.Text("Copied draft to clipboard!"), bgcolor=COLORS["success"]))

    def _save_draft(self) -> None:
        self.draft_btn.disabled = True
        self.status_text.visible = True
        self.status_text.value = "Creating Gmail draft..."
        self.status_text.color = COLORS["warning"]
        if self.page:
            self.page.update()

        def worker():
            try:
                gmail_actions.create_draft(
                    recipient=self.email_data.get("sender", ""),
                    subject=self.email_data.get("subject", ""),
                    body_text=self.reply_editor.value or "",
                    thread_id=self.email_data.get("thread_id"),
                )
                self.status_text.value = "Gmail draft saved successfully!"
                self.status_text.color = COLORS["success"]
                if self.on_draft_created:
                    self.on_draft_created(self.email_data.get("message_id", ""))
            except Exception as ex:
                self.status_text.value = f"Saved locally: {ex}"
                self.status_text.color = COLORS["warning"]
            self.draft_btn.disabled = False
            if self.page:
                self.page.update()

        threading.Thread(target=worker, daemon=True).start()

    def close(self) -> None:
        if self.page:
            self.page.close(self)
