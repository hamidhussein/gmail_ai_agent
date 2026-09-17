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
    align_center,
)
from app.constants import ReplyTone
from ai.reply_generator import reply_generator
from gmail.actions import gmail_actions
from memory.user_profile import user_profile_manager

TONE_META = [
    (ReplyTone.PROFESSIONAL, "Professional", ft.Icons.BUSINESS_CENTER_OUTLINED),
    (ReplyTone.FRIENDLY, "Friendly", ft.Icons.SENTIMENT_SATISFIED_ALT_OUTLINED),
    (ReplyTone.SHORT, "Concise", ft.Icons.FLASH_ON_OUTLINED),
    (ReplyTone.DETAILED, "Detailed", ft.Icons.SUBJECT_OUTLINED),
    (ReplyTone.FOLLOW_UP, "Follow-up", ft.Icons.UPDATE_OUTLINED),
    (ReplyTone.APOLOGY, "Apology", ft.Icons.HEALING_OUTLINED),
]

QUICK_PROMPTS = [
    "Confirm agreement & next steps",
    "Request revised proposal / pricing",
    "Decline politely with thanks",
    "Ask to schedule a 15-min sync",
]


class ReplyDialog(ft.AlertDialog):
    """Modern, production-grade AI Reply Assistant dialog with live tone switching, quick prompts, and draft/send actions."""

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

        # Tone Selector Pills
        self.tone_chip_controls = []
        for tone_enum, label, icon_name in TONE_META:
            is_active = (tone_enum.value == self.selected_tone)
            chip = ft.Container(
                content=ft.Row([
                    ft.Icon(icon_name, size=13, color=COLORS["chip_active_text"] if is_active else COLORS["text_muted"]),
                    ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=COLORS["chip_active_text"] if is_active else COLORS["text_secondary"]),
                ], spacing=5, tight=True),
                bgcolor=COLORS["chip_active_bg"] if is_active else "transparent",
                border=border_all(1, COLORS["primary"] if is_active else COLORS["border"]),
                border_radius=100,
                padding=padding_symmetric(horizontal=10, vertical=5),
                on_click=lambda e, t=tone_enum.value: self._set_tone_from_pill(t),
                animate=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
            )
            self.tone_chip_controls.append((tone_enum.value, chip))

        self.tone_row = ft.Row(
            spacing=6,
            controls=[c for _, c in self.tone_chip_controls],
            scroll=ft.ScrollMode.HIDDEN,
        )

        # Legacy Dropdown maintained for programmatic consistency
        self.tone_dropdown = ft.Dropdown(
            value=self.selected_tone,
            options=[ft.DropdownOption(t.value) for t in ReplyTone],
            width=140,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=12,
            content_padding=padding_symmetric(horizontal=8, vertical=4),
            visible=False,
            on_select=self._on_tone_changed,
        )

        # Custom instruction field
        self.custom_prompt = ft.TextField(
            hint_text="Add custom guidance (e.g. 'Attach updated slide deck', 'Decline offer')...",
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            expand=True,
            content_padding=padding_symmetric(horizontal=12, vertical=8),
        )

        # Quick inspiration prompt chips
        prompt_chips = []
        for qp in QUICK_PROMPTS:
            chip = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, size=11, color=COLORS["primary"]),
                    ft.Text(qp, size=11, color=COLORS["text_secondary"]),
                ], spacing=3, tight=True),
                bgcolor=COLORS["bg_card"],
                border=border_all(1, COLORS["border"]),
                border_radius=6,
                padding=padding_symmetric(horizontal=8, vertical=3),
                on_click=lambda e, p=qp: self._apply_quick_prompt(p),
            )
            prompt_chips.append(chip)

        self.quick_prompts_row = ft.Row(
            spacing=6,
            controls=prompt_chips,
            scroll=ft.ScrollMode.HIDDEN,
        )

        self.spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLORS["warning"], visible=True)
        self.status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=COLORS["success"], visible=False)
        self.status_text = ft.Text("AI is drafting your response...", size=12, color=COLORS["warning"], visible=True)
        self.char_count_text = ft.Text("0 chars • 0 words", size=11, color=COLORS["text_muted"])

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

        self.copy_btn = ft.OutlinedButton(
            "Copy Text",
            icon=ft.Icons.COPY_ALL_OUTLINED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self._copy_text(),
        )

        self.draft_btn = ft.ElevatedButton(
            "Save Draft",
            icon=ft.Icons.SAVE_OUTLINED,
            bgcolor=COLORS["accent"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True,
            on_click=lambda e: self._save_draft(),
        )

        self.send_btn = ft.ElevatedButton(
            "Send Reply",
            icon=ft.Icons.SEND_ROUNDED,
            bgcolor=COLORS["primary"],
            color="#FFFFFF",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            disabled=True,
            on_click=lambda e: self._confirm_send(),
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
            bgcolor=COLORS["surface_alt"],
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
            width=700,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    reply_info,
                    # Tone Picker Section
                    ft.Column([
                        ft.Row([
                            ft.Text("Tone Style:", size=12, weight=ft.FontWeight.W_600, color=COLORS["text_secondary"]),
                            self.tone_row,
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], spacing=6),
                    # Custom Prompt Field & Quick Chips
                    ft.Row([
                        self.custom_prompt,
                        self.regen_btn,
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.quick_prompts_row,
                    # Status & Word Count Row
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
                    # Text Editor
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
                ft.Text("Generates context-aware, personalized email responses tailored to your tone", size=11, color=COLORS["text_secondary"]),
            ], spacing=2),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        super().__init__(
            title=header,
            content=content,
            actions=[
                ft.TextButton("Close", on_click=lambda e: self.close()),
                self.copy_btn,
                self.draft_btn,
                self.send_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=COLORS["bg_main"],
            shape=ft.RoundedRectangleBorder(radius=12),
        )

        self._start_worker_generation()

    def _set_tone_from_pill(self, tone_value: str) -> None:
        self.selected_tone = tone_value
        self.tone_dropdown.value = tone_value
        for key, chip in self.tone_chip_controls:
            is_active = (key == tone_value)
            chip.bgcolor = COLORS["chip_active_bg"] if is_active else "transparent"
            chip.border = border_all(1, COLORS["primary"] if is_active else COLORS["border"])
            row = chip.content
            row.controls[0].color = COLORS["chip_active_text"] if is_active else COLORS["text_muted"]
            row.controls[1].color = COLORS["chip_active_text"] if is_active else COLORS["text_secondary"]
        safe_update(self.tone_row)
        self._trigger_generation()

    def _apply_quick_prompt(self, prompt_text: str) -> None:
        existing = (self.custom_prompt.value or "").strip()
        if existing:
            self.custom_prompt.value = f"{existing}, {prompt_text}"
        else:
            self.custom_prompt.value = prompt_text
        safe_update(self.custom_prompt)
        self._trigger_generation()

    def _on_tone_changed(self, e):
        self._set_tone_from_pill(self.tone_dropdown.value)

    def _on_text_changed(self, e):
        text = (self.reply_editor.value or "").strip()
        chars = len(text)
        words = len(text.split()) if text else 0
        self.char_count_text.value = f"{chars:,} chars • {words:,} words"
        safe_update(self.char_count_text)

    def _trigger_generation(self) -> None:
        self.spinner.visible = True
        self.status_icon.visible = False
        self.status_text.visible = True
        self.status_text.value = "AI is drafting your response..."
        self.status_text.color = COLORS["warning"]
        self.regen_btn.disabled = True
        self.draft_btn.disabled = True
        self.send_btn.disabled = True
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
        """Apply only the newest generation result and restore controls."""
        if version != self._generation_version:
            return
        self.spinner.visible = False
        self.regen_btn.disabled = False
        if error is not None or not draft.strip():
            self.status_icon.visible = False
            self.status_text.value = f"Could not generate reply: {error or 'empty response'}"
            self.status_text.color = COLORS["danger"]
            self.draft_btn.disabled = True
            self.send_btn.disabled = True
        else:
            self.reply_editor.value = draft
            self.status_icon.visible = True
            self.status_text.value = f"Draft ready • Powered by {source}"
            self.status_text.color = COLORS["success"]
            chars = len(draft.strip())
            words = len(draft.strip().split())
            self.char_count_text.value = f"{chars:,} chars • {words:,} words"
            self.draft_btn.disabled = False
            self.send_btn.disabled = False
        safe_update(self.page_ref)

    def _copy_text(self) -> None:
        text = self.reply_editor.value or ""
        if not text.strip():
            return
        try:
            self.page_ref.set_clipboard(text)
            self.copy_btn.icon = ft.Icons.CHECK
            self.copy_btn.text = "Copied!"
            safe_update(self.copy_btn)

            def _revert():
                import time
                time.sleep(1.8)
                self.copy_btn.text = "Copy Text"
                self.copy_btn.icon = ft.Icons.COPY_ALL_OUTLINED
                safe_update(self.copy_btn)

            threading.Thread(target=_revert, daemon=True).start()
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
        self.status_text.value = "Saving draft to Gmail..."
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
                    message_id=self.email_data.get("message_id"),
                )
            except Exception as ex:
                save_err = ex

            async def _apply_result():
                self.spinner.visible = False
                if save_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Draft saved to Gmail Drafts folder!"
                    self.status_text.color = COLORS["success"]
                    if self.on_draft_created:
                        self.on_draft_created(self.email_data.get("message_id", ""))
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Draft save status: {save_err}"
                    self.status_text.color = COLORS["warning"]
                self.draft_btn.disabled = False
                safe_update(self.page_ref)

            try:
                self.page_ref.run_task(_apply_result)
            except Exception:
                self.spinner.visible = False
                if save_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Draft saved to Gmail Drafts folder!"
                    self.status_text.color = COLORS["success"]
                    if self.on_draft_created:
                        self.on_draft_created(self.email_data.get("message_id", ""))
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Draft save status: {save_err}"
                    self.status_text.color = COLORS["warning"]
                self.draft_btn.disabled = False
                safe_update(self.page_ref)

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_send(self) -> None:
        """Prompt user with a confirmation dialog before sending the email live."""
        recipient = self.email_data.get("sender", "Unknown")
        subject = self.email_data.get("subject", "")

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.OUTBOX_ROUNDED, color=COLORS["primary"], size=20),
                ft.Text("Send this reply?", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Text(f"Are you sure you want to send this email directly to:\n\n{recipient}\n\nSubject: Re: {subject}"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page_ref.pop_dialog()),
                ft.ElevatedButton(
                    "Confirm & Send",
                    icon=ft.Icons.SEND,
                    bgcolor=COLORS["primary"],
                    color="#FFFFFF",
                    on_click=lambda e: self._execute_send(confirm_dialog),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page_ref.show_dialog(confirm_dialog)

    def _execute_send(self, confirm_dialog: ft.AlertDialog) -> None:
        self.page_ref.pop_dialog()
        self.send_btn.disabled = True
        self.spinner.visible = True
        self.status_icon.visible = False
        self.status_text.visible = True
        self.status_text.value = "Sending reply..."
        self.status_text.color = COLORS["warning"]
        safe_update(self.page_ref)

        def worker():
            send_err = None
            try:
                gmail_actions.send_reply(
                    recipient=self.email_data.get("sender", ""),
                    subject=self.email_data.get("subject", ""),
                    body_text=self.reply_editor.value or "",
                    thread_id=self.email_data.get("thread_id"),
                    message_id=self.email_data.get("message_id"),
                    user_approved=True,
                )
            except Exception as ex:
                send_err = ex

            async def _apply_send_result():
                self.spinner.visible = False
                if send_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Reply sent successfully!"
                    self.status_text.color = COLORS["success"]
                    self.page_ref.show_dialog(ft.SnackBar(ft.Text("Reply sent successfully!"), bgcolor=COLORS["success"]))
                    self.send_btn.disabled = True
                    self.draft_btn.disabled = True
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Sending failed: {send_err}"
                    self.status_text.color = COLORS["danger"]
                    self.send_btn.disabled = False
                safe_update(self.page_ref)

            try:
                self.page_ref.run_task(_apply_send_result)
            except Exception:
                self.spinner.visible = False
                if send_err is None:
                    self.status_icon.visible = True
                    self.status_text.value = "Reply sent successfully!"
                    self.status_text.color = COLORS["success"]
                    self.send_btn.disabled = True
                    self.draft_btn.disabled = True
                else:
                    self.status_icon.visible = False
                    self.status_text.value = f"Sending failed: {send_err}"
                    self.status_text.color = COLORS["danger"]
                    self.send_btn.disabled = False
                safe_update(self.page_ref)

        threading.Thread(target=worker, daemon=True).start()

    def close(self) -> None:
        try:
            self.page_ref.pop_dialog()
        except Exception:
            pass
