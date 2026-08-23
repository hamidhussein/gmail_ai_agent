"""
GmailAI Assistant - Action & Safety Confirmation Dialogs
"""
import customtkinter as ctk
from typing import Callable, Optional
from resources.styles.theme import FONTS, THEME


class ActionConfirmDialog(ctk.CTkToplevel):
    """
    Safety confirmation modal dialog with mandatory double-verification
    for destructive operations.
    """

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        on_confirm: Callable[[bool], None],
        is_destructive: bool = False,
        details: Optional[str] = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("480x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_confirm = on_confirm
        self.is_destructive = is_destructive
        self.confirmed = False
        self.double_check_var = ctk.BooleanVar(value=not is_destructive)

        self.configure(fg_color=THEME["dark"]["bg_main"])
        self._build_ui(title, message, details)

    def _build_ui(self, title: str, message: str, details: Optional[str]) -> None:
        # Header Icon + Title
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 12))

        icon_str = "⚠️" if self.is_destructive else "ℹ️"
        icon_lbl = ctk.CTkLabel(header, text=icon_str, font=("Segoe UI Emoji", 24))
        icon_lbl.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            header,
            text=title,
            font=FONTS["h2"],
            text_color="#EF4444" if self.is_destructive else "#F8FAFC",
        )
        title_lbl.pack(side="left")

        # Message Body
        msg_lbl = ctk.CTkLabel(
            self,
            text=message,
            font=FONTS["body"],
            text_color=THEME["dark"]["text_primary"],
            wraplength=430,
            justify="left",
        )
        msg_lbl.pack(fill="x", padx=24, pady=(0, 12))

        if details:
            details_box = ctk.CTkTextbox(self, height=60, font=FONTS["code"], fg_color="#090D16")
            details_box.insert("1.0", details)
            details_box.configure(state="disabled")
            details_box.pack(fill="x", padx=24, pady=(0, 12))

        # Mandatory double verification checkbox if destructive
        if self.is_destructive:
            self.double_chk = ctk.CTkCheckBox(
                self,
                text="I confirm and understand this action will move emails to Trash.",
                variable=self.double_check_var,
                font=FONTS["body_sm_bold"],
                text_color="#FCA5A5",
                fg_color="#EF4444",
                hover_color="#DC2626",
                command=self._on_check_toggle,
            )
            self.double_chk.pack(fill="x", padx=24, pady=(0, 16))

        # Bottom Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(12, 24), side="bottom")

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=FONTS["body"],
            fg_color=THEME["dark"]["bg_card"],
            hover_color=THEME["dark"]["bg_card_hover"],
            text_color="#94A3B8",
            width=100,
            command=self._handle_cancel,
        )
        cancel_btn.pack(side="right", padx=(8, 0))

        self.confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Confirm Action",
            font=FONTS["body_bold"],
            fg_color="#EF4444" if self.is_destructive else THEME["dark"]["primary"],
            hover_color="#DC2626" if self.is_destructive else THEME["dark"]["primary_hover"],
            width=140,
            state="normal" if not self.is_destructive else "disabled",
            command=self._handle_confirm,
        )
        self.confirm_btn.pack(side="right")

    def _on_check_toggle(self) -> None:
        if self.double_check_var.get():
            self.confirm_btn.configure(state="normal")
        else:
            self.confirm_btn.configure(state="disabled")

    def _handle_confirm(self) -> None:
        self.confirmed = True
        self.destroy()
        self.on_confirm(self.double_check_var.get())

    def _handle_cancel(self) -> None:
        self.confirmed = False
        self.destroy()
