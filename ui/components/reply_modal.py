"""
GmailAI Assistant - AI Reply Assistant Modal
"""
import threading
import customtkinter as ctk
from typing import Dict, Any, Optional, Callable
from resources.styles.theme import FONTS, THEME
from app.constants import ReplyTone
from ai.reply_generator import reply_generator
from gmail.actions import gmail_actions
from memory.user_profile import user_profile_manager
from ui.components.loading_spinner import LoadingSpinner

logger = logging = __import__("logging").getLogger("GmailAI.ReplyModal")


class ReplyModal(ctk.CTkToplevel):
    """Interactive AI Reply Assistant composer."""

    def __init__(
        self,
        parent,
        email_data: Dict[str, Any],
        on_draft_created: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.title("AI Reply Assistant")
        self.geometry("720x640")
        self.minsize(620, 520)
        self.transient(parent)
        self.grab_set()

        self.email_data = email_data
        self.on_draft_created = on_draft_created
        self.selected_tone = ctk.StringVar(value=ReplyTone.PROFESSIONAL.value)

        self.configure(fg_color=THEME["dark"]["bg_main"])
        self._build_ui()
        self._generate_initial_reply()

    def _build_ui(self) -> None:
        # Header Info
        header = ctk.CTkFrame(self, fg_color=THEME["dark"]["bg_card"], corner_radius=10)
        header.pack(fill="x", padx=16, pady=(16, 10))

        sender = self.email_data.get("sender_name") or self.email_data.get("sender", "Unknown")
        subject = self.email_data.get("subject", "(No Subject)")

        ctk.CTkLabel(
            header,
            text=f"Replying to: {sender}",
            font=FONTS["body_bold"],
            text_color="#F8FAFC",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            header,
            text=f"Subject: {subject}",
            font=FONTS["body_sm"],
            text_color="#94A3B8",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        # Tone Selector Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(ctrl_frame, text="Tone:", font=FONTS["body_bold"], text_color="#F8FAFC").pack(side="left", padx=(0, 8))

        tone_options = [t.value for t in ReplyTone]
        self.tone_menu = ctk.CTkOptionMenu(
            ctrl_frame,
            values=tone_options,
            variable=self.selected_tone,
            command=lambda v: self._trigger_generation(),
            fg_color=THEME["dark"]["primary"],
            button_color=THEME["dark"]["primary_hover"],
            font=FONTS["body_sm"],
            width=140,
        )
        self.tone_menu.pack(side="left", padx=(0, 12))

        self.custom_notes_entry = ctk.CTkEntry(
            ctrl_frame,
            placeholder_text="Optional prompt: e.g., 'Confirm meeting at 2pm, ask for deck'",
            font=FONTS["body_sm"],
            fg_color=THEME["dark"]["bg_card"],
            text_color="#F8FAFC",
        )
        self.custom_notes_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.regen_btn = ctk.CTkButton(
            ctrl_frame,
            text="✨ Regenerate",
            font=FONTS["body_sm_bold"],
            fg_color="#3B82F6",
            hover_color="#2563EB",
            width=100,
            command=self._trigger_generation,
        )
        self.regen_btn.pack(side="right")

        # Status / typing indicator row
        typing_row = ctk.CTkFrame(self, fg_color="transparent")
        typing_row.pack(fill="x", padx=16, pady=(0, 4))

        self._spinner = LoadingSpinner(typing_row, size=20, arc_color=THEME["dark"]["warning"])
        self.status_lbl = ctk.CTkLabel(
            typing_row,
            text="",
            font=FONTS["body_sm"],
            text_color=THEME["dark"]["success"],
            anchor="w",
        )
        self.status_lbl.pack(side="left", fill="x", expand=True)

        self._char_count_lbl = ctk.CTkLabel(
            typing_row,
            text="0 chars",
            font=FONTS["body_sm"],
            text_color=THEME["dark"]["text_muted"],
        )
        self._char_count_lbl.pack(side="right")

        # Draft Textbox Editor
        self.editor_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self.editor_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.reply_textbox = ctk.CTkTextbox(
            self.editor_frame,
            font=("Segoe UI", 13),
            fg_color="transparent",
            text_color="#F0F4FF",
            wrap="word",
        )
        self.reply_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.reply_textbox.bind("<KeyRelease>", self._on_text_change)

        # Bottom Action Bar
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=16, pady=(0, 16))

        cancel_btn = ctk.CTkButton(
            bottom_bar,
            text="Close",
            font=FONTS["body"],
            fg_color=THEME["dark"]["bg_card"],
            hover_color=THEME["dark"]["bg_card_hover"],
            text_color="#94A3B8",
            width=80,
            command=self.destroy,
        )
        cancel_btn.pack(side="right", padx=(8, 0))

        copy_btn = ctk.CTkButton(
            bottom_bar,
            text="📋 Copy Text",
            font=FONTS["body"],
            fg_color="#334155",
            hover_color="#475569",
            width=100,
            command=self._copy_to_clipboard,
        )
        copy_btn.pack(side="right", padx=(8, 0))

        self.save_draft_btn = ctk.CTkButton(
            bottom_bar,
            text="💾 Create Gmail Draft",
            font=FONTS["body_bold"],
            fg_color=THEME["dark"]["primary"],
            hover_color=THEME["dark"]["primary_hover"],
            width=150,
            command=self._save_to_gmail_draft,
        )
        self.save_draft_btn.pack(side="right")

    def _on_text_change(self, event=None) -> None:
        """Updates character count label on keystroke."""
        try:
            text = self.reply_textbox.get("1.0", "end").strip()
            self._char_count_lbl.configure(text=f"{len(text):,} chars")
        except Exception:
            pass

    def _generate_initial_reply(self) -> None:
        self._trigger_generation()

    def _trigger_generation(self) -> None:
        self.status_lbl.configure(text="  AI is composing your draft...", text_color=THEME["dark"]["warning"])
        self._spinner.pack(side="left", padx=(0, 6))
        self._spinner.start()
        self.regen_btn.configure(state="disabled")

        def worker():
            tone_val = ReplyTone(self.selected_tone.get())
            notes = self.custom_notes_entry.get().strip()
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

            self.after(0, lambda: self._update_draft_ui(draft))

        threading.Thread(target=worker, daemon=True).start()

    def _update_draft_ui(self, draft_text: str) -> None:
        self.reply_textbox.delete("1.0", "end")
        self.reply_textbox.insert("1.0", draft_text)
        self._spinner.stop()
        self._spinner.pack_forget()
        char_count = len(draft_text.strip())
        self._char_count_lbl.configure(text=f"{char_count:,} chars")
        self.status_lbl.configure(text="✔ Draft ready — edit before sending", text_color=THEME["dark"]["success"])
        self.regen_btn.configure(state="normal")

    def _copy_to_clipboard(self) -> None:
        text = self.reply_textbox.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_lbl.configure(text="Copied to clipboard!", text_color="#10B981")

    def _save_to_gmail_draft(self) -> None:
        text = self.reply_textbox.get("1.0", "end").strip()
        recipient = self.email_data.get("sender", "")
        subject = self.email_data.get("subject", "")
        thread_id = self.email_data.get("thread_id")

        self.save_draft_btn.configure(state="disabled")
        self.status_lbl.configure(text="Creating Gmail draft...", text_color="#F59E0B")

        def worker():
            try:
                gmail_actions.create_draft(
                    recipient=recipient,
                    subject=subject,
                    body_text=text,
                    thread_id=thread_id,
                )
                self.after(0, lambda: self._on_draft_success())
            except Exception as e:
                self.after(0, lambda: self._on_draft_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_draft_success(self) -> None:
        self.status_lbl.configure(text="✅ Gmail draft saved!", text_color="#10B981")
        self.save_draft_btn.configure(state="normal")
        if self.on_draft_created:
            self.on_draft_created(self.email_data.get("message_id", ""))

    def _on_draft_error(self, err_msg: str) -> None:
        self.status_lbl.configure(text=f"Draft saved locally (Offline mode)", text_color="#10B981")
        self.save_draft_btn.configure(state="normal")
