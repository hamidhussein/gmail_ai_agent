"""
GmailAI Assistant - Animated Loading Spinner Component
"""
import math
import customtkinter as ctk
from resources.styles.theme import THEME


class LoadingSpinner(ctk.CTkCanvas):
    """
    Smooth rotating arc spinner widget built on CTkCanvas.
    Call .start() to begin animation and .stop() to hide.
    """

    def __init__(
        self,
        master,
        size: int = 28,
        arc_color: str = None,
        thickness: int = 3,
        speed_ms: int = 30,
        **kwargs,
    ):
        bg = THEME["dark"]["bg_card"]
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            **kwargs,
        )
        self._size = size
        self._arc_color = arc_color or THEME["dark"]["primary"]
        self._thickness = thickness
        self._speed_ms = speed_ms
        self._angle = 0
        self._running = False
        self._arc_id = None
        self._after_id = None

        # Draw track ring
        pad = thickness + 1
        self.create_oval(
            pad, pad, size - pad, size - pad,
            outline=THEME["dark"]["border"],
            width=thickness,
        )

    def _draw_frame(self) -> None:
        if self._arc_id:
            self.delete(self._arc_id)

        pad = self._thickness + 1
        start = self._angle
        extent = 270  # arc sweep length

        self._arc_id = self.create_arc(
            pad, pad,
            self._size - pad, self._size - pad,
            start=start,
            extent=extent,
            style="arc",
            outline=self._arc_color,
            width=self._thickness,
        )
        self._angle = (self._angle - 8) % 360

    def _tick(self) -> None:
        if not self._running:
            return
        self._draw_frame()
        self._after_id = self.after(self._speed_ms, self._tick)

    def start(self) -> None:
        """Begin the spinner animation and make it visible."""
        if self._running:
            return
        self._running = True
        self.pack_propagate(False)
        self._tick()

    def stop(self) -> None:
        """Stop the animation and hide the widget."""
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._arc_id:
            self.delete(self._arc_id)
            self._arc_id = None
