"""
GmailAI Assistant - Action Audit Logs Viewer
"""
import customtkinter as ctk
from resources.styles.theme import FONTS, THEME
from database.repository import repository


class AuditLogsView(ctk.CTkFrame):
    """Real-time audit log viewer displaying every executed action and user authorization."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build_ui()
        self.load_logs()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 16))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="📜 Security & Action Audit Trail",
            font=FONTS["h1"],
            text_color="#F8FAFC",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Immutable local record of all automated and approved email operations.",
            font=FONTS["body"],
            text_color=THEME["dark"]["text_secondary"],
        ).pack(anchor="w", pady=(2, 0))

        ref_btn = ctk.CTkButton(
            header,
            text="🔄 Refresh Logs",
            font=FONTS["body_sm_bold"],
            fg_color="#334155",
            hover_color="#475569",
            width=110,
            command=self.load_logs,
        )
        ref_btn.pack(side="right")

        # Table Header
        tbl_header = ctk.CTkFrame(self, fg_color=THEME["dark"]["bg_card"], height=36, corner_radius=6)
        tbl_header.pack(fill="x", padx=28, pady=(0, 6))
        tbl_header.pack_propagate(False)

        cols = [
            ("Timestamp", 140),
            ("Action", 100),
            ("Sender / Target", 180),
            ("Subject", 240),
            ("Approved", 100),
            ("Reason", 200),
        ]
        for name, width in cols:
            ctk.CTkLabel(
                tbl_header,
                text=name.upper(),
                font=FONTS["body_sm_bold"],
                text_color="#94A3B8",
                width=width,
                anchor="w",
            ).pack(side="left", padx=8)

        # Scrollable log list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=28, pady=(0, 16))

    def load_logs(self) -> None:
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        logs = repository.get_recent_audit_logs(limit=100)
        if not logs:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No audit logs recorded yet.",
                font=FONTS["body"],
                text_color="#64748B",
            ).pack(pady=40)
            return

        for entry in logs:
            row = ctk.CTkFrame(self.scroll_frame, fg_color=THEME["dark"]["bg_card"], height=40, corner_radius=6)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            # Time
            time_str = entry.executed_at.strftime("%Y-%m-%d %H:%M:%S") if entry.executed_at else ""
            ctk.CTkLabel(row, text=time_str, font=FONTS["body_sm"], text_color="#94A3B8", width=140, anchor="w").pack(side="left", padx=8)

            # Action
            act_col = "#EF4444" if entry.action_type == "MOVE_TRASH" else ("#10B981" if entry.action_type == "DRAFT_REPLY" else "#3B82F6")
            ctk.CTkLabel(row, text=entry.action_type, font=FONTS["body_sm_bold"], text_color=act_col, width=100, anchor="w").pack(side="left", padx=8)

            # Target
            sender_str = (entry.sender or "")[:24]
            ctk.CTkLabel(row, text=sender_str, font=FONTS["body_sm"], text_color="#F8FAFC", width=180, anchor="w").pack(side="left", padx=8)

            # Subject
            subj_str = (entry.subject or "")[:32]
            ctk.CTkLabel(row, text=subj_str, font=FONTS["body_sm"], text_color="#CBD5E1", width=240, anchor="w").pack(side="left", padx=8)

            # Approved
            appr_str = "YES (2x)" if entry.double_confirmed else ("YES" if entry.user_approved else "AUTO")
            ctk.CTkLabel(row, text=appr_str, font=FONTS["body_sm_bold"], text_color="#10B981" if entry.user_approved else "#F59E0B", width=100, anchor="w").pack(side="left", padx=8)

            # Reason
            reason_str = (entry.reason or "")[:30]
            ctk.CTkLabel(row, text=reason_str, font=FONTS["body_sm"], text_color="#64748B", width=200, anchor="w").pack(side="left", padx=8)
