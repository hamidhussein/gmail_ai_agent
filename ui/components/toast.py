"""
GmailAI Assistant - Premium Animated Toast Notification System
"""
import customtkinter as ctk
from resources.styles.theme import FONTS, THEME
from typing import List


# Global stack to manage multiple concurrent toasts
_active_toasts: List["ToastNotification"] = []
_TOAST_HEIGHT = 64
_TOAST_WIDTH = 340
_TOAST_MARGIN = 16
_TOAST_BOTTOM_OFFSET = 24


def _restack_toasts(root) -> None:
    """Repositions all active toasts so they stack neatly bottom-right."""
    y_offset = _TOAST_BOTTOM_OFFSET
    for toast in reversed(_active_toasts):
        try:
            root_h = root.winfo_height()
            toast_y = 1.0 - (y_offset + _TOAST_HEIGHT) / root_h
            toast_x = 1.0 - (_TOAST_WIDTH + _TOAST_MARGIN) / root.winfo_width()
            toast.place(relx=toast_x, rely=toast_y, anchor="nw")
            y_offset += _TOAST_HEIGHT + 8
        except Exception:
            pass


class ToastNotification(ctk.CTkFrame):
    """
    Animated toast notification that slides in from the bottom-right,
    displays with a colored accent bar and a progress countdown bar,
    then auto-dismisses.
    """

    COLORS = {
        "success": ("#10B981", "#065F46"),
        "error":   ("#F43F5E", "#881337"),
        "warning": ("#F59E0B", "#78350F"),
        "info":    ("#0EA5E9", "#0C4A6E"),
    }

    ICONS = {
        "success": "\u2714",   # ✔
        "error":   "\u2718",   # ✘
        "warning": "\u26A0",   # ⚠
        "info":    "\u2139",   # ℹ
    }

    @classmethod
    def show(
        cls,
        root,
        message: str,
        level: str = "info",
        duration_ms: int = 3500,
    ) -> None:
        """Display an animated toast notification on the given root window."""
        try:
            toast = cls(root, message=message, level=level, duration_ms=duration_ms)
            _active_toasts.append(toast)
            _restack_toasts(root)
            toast._animate_in(root)
        except Exception:
            pass

    def __init__(self, root, message: str, level: str, duration_ms: int):
        accent, _ = self.COLORS.get(level, self.COLORS["info"])
        super().__init__(
            root,
            width=_TOAST_WIDTH,
            height=_TOAST_HEIGHT,
            fg_color=THEME["dark"]["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=THEME["dark"]["border"],
        )
        self._root = root
        self._duration_ms = duration_ms
        self._accent = accent
        self.place_forget()
        self._build(message, level, accent)

    def _build(self, message: str, level: str, accent: str) -> None:
        self.grid_propagate(False)

        # Left accent bar
        bar = ctk.CTkFrame(self, width=4, fg_color=accent, corner_radius=0)
        bar.pack(side="left", fill="y", padx=(0, 0))

        # Icon
        icon_lbl = ctk.CTkLabel(
            self,
            text=self.ICONS.get(level, "\u2139"),
            font=("Segoe UI", 16, "bold"),
            text_color=accent,
            width=28,
        )
        icon_lbl.pack(side="left", padx=(10, 4))

        # Message
        msg_lbl = ctk.CTkLabel(
            self,
            text=message,
            font=FONTS["body_sm_bold"],
            text_color=THEME["dark"]["text_primary"],
            anchor="w",
            wraplength=220,
            justify="left",
        )
        msg_lbl.pack(side="left", fill="x", expand=True, pady=8)

        # Close button
        close_btn = ctk.CTkButton(
            self,
            text="\u00D7",
            width=24,
            height=24,
            font=("Segoe UI", 14, "bold"),
            fg_color="transparent",
            hover_color=THEME["dark"]["bg_card_hover"],
            text_color=THEME["dark"]["text_secondary"],
            command=self._dismiss,
        )
        close_btn.pack(side="right", padx=8)

        # Progress bar at the bottom
        self._progress_bar = ctk.CTkProgressBar(
            self,
            width=_TOAST_WIDTH - 20,
            height=3,
            fg_color=THEME["dark"]["border"],
            progress_color=accent,
            corner_radius=0,
        )
        self._progress_bar.set(1.0)
        self._progress_bar.place(relx=0.5, rely=1.0, anchor="s", y=-2)

    def _animate_in(self, root) -> None:
        """Slides the toast in and starts the countdown."""
        self._step_progress(steps=100, elapsed=0)
        root.after(self._duration_ms, self._dismiss)

    def _step_progress(self, steps: int, elapsed: int) -> None:
        """Ticks the progress bar down over the duration."""
        if elapsed > steps:
            return
        try:
            remaining = 1.0 - (elapsed / steps)
            self._progress_bar.set(remaining)
            interval = self._duration_ms // steps
            self._root.after(interval, lambda: self._step_progress(steps, elapsed + 1))
        except Exception:
            pass

    def _dismiss(self) -> None:
        """Removes the toast from the stack and destroys it."""
        try:
            if self in _active_toasts:
                _active_toasts.remove(self)
            _restack_toasts(self._root)
            self.destroy()
        except Exception:
            pass
