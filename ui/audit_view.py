"""
GmailAI Assistant - Action Audit Logs Viewer for Flet
"""
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
    empty_state,
    pill_badge,
)
from database.repository import repository


class AuditLogsView(ft.Container):
    """Immutable audit trail displaying every AI automated action, user approval, and operation."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page

        self.logs_column = ft.Column(
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Header
                ft.Row([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.SECURITY, size=22, color="#FFFFFF"),
                            bgcolor=COLORS["primary"],
                            padding=8,
                            border_radius=10,
                            shadow=ft.BoxShadow(spread_radius=0, blur_radius=6, color=COLORS["primary"] + "40", offset=ft.Offset(0, 2)),
                        ),
                        ft.Column([
                            ft.Text("Security & Action Audit Trail", size=22, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ft.Text("Immutable local record of all automated and approved email operations.", size=13, color=COLORS["text_secondary"]),
                        ], spacing=2),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.OutlinedButton(
                        "Refresh Logs",
                        icon=ft.Icons.REFRESH,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self.load_logs(),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Table Header
                ft.Container(
                    content=ft.Row([
                        ft.Text("TIMESTAMP", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], width=150),
                        ft.Text("ACTION", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], width=110),
                        ft.Text("SENDER / TARGET", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], width=180),
                        ft.Text("SUBJECT", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], expand=True),
                        ft.Text("APPROVED", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], width=100),
                        ft.Text("REASON", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"], width=180),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    bgcolor=COLORS["bg_card_hover"],
                    border=border_all(1, COLORS["border"]),
                    padding=padding_symmetric(horizontal=16, vertical=10),
                    border_radius=8,
                ),

                # Table Rows
                ft.Container(
                    content=self.logs_column,
                    expand=True,
                ),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )

        self.load_logs()

    def refresh_data(self) -> None:
        self.load_logs()

    def load_logs(self) -> None:
        self.logs_column.controls.clear()
        logs = repository.get_recent_audit_logs(limit=100)

        if not logs:
            self.logs_column.controls.append(
                empty_state(
                    icon=ft.Icons.SECURITY_OUTLINED,
                    title="No Audit Logs Recorded Yet",
                    subtitle="All automated and user-approved operations are logged here in an immutable audit trail.",
                )
            )
            safe_update(self.page_ref)
            return

        for idx, entry in enumerate(logs):
            time_str = entry.executed_at.strftime("%Y-%m-%d %H:%M:%S") if entry.executed_at else "Just now"
            act_col = (
                COLORS["danger"]
                if entry.action_type in ("MOVE_TRASH", "TRASH")
                else (
                    COLORS["success"]
                    if entry.action_type in ("DRAFT_REPLY", "SEND_REPLY")
                    else COLORS["primary"]
                )
            )
            appr_str = "YES (2x)" if entry.double_confirmed else ("YES" if entry.user_approved else "AUTO")
            appr_col = COLORS["success"] if entry.user_approved else COLORS["warning"]

            row_bg = COLORS["bg_card"] if idx % 2 == 0 else COLORS["bg_card_hover"]

            def make_hover(r_cont, default_bg):
                def _on_h(e):
                    r_cont.bgcolor = COLORS["badge_bg"] if e.data == "true" else default_bg
                    safe_update(r_cont)
                return _on_h

            row = ft.Container(
                content=ft.Row([
                    ft.Text(time_str, size=12, color=COLORS["text_secondary"], width=150),
                    ft.Container(
                        content=ft.Text(entry.action_type or "ACTION", size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        bgcolor=act_col,
                        padding=padding_symmetric(horizontal=8, vertical=3),
                        border_radius=4,
                        width=110,
                        alignment=align_center(),
                    ),
                    ft.Text(entry.sender or "(None)", size=12, color=COLORS["text_primary"], width=180, no_wrap=True),
                    ft.Text(entry.subject or "(No Subject)", size=12, color=COLORS["text_secondary"], expand=True, no_wrap=True),
                    ft.Container(
                        content=ft.Text(appr_str, size=11, weight=ft.FontWeight.BOLD, color=appr_col),
                        width=100,
                    ),
                    ft.Text(entry.reason or "Rule execution", size=11, color=COLORS["text_muted"], width=180, no_wrap=True),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                bgcolor=row_bg,
                border=border_only(
                    left=ft.BorderSide(3, act_col),
                    top=ft.BorderSide(1, COLORS["border"]),
                    right=ft.BorderSide(1, COLORS["border"]),
                    bottom=ft.BorderSide(1, COLORS["border"]),
                ),
                border_radius=8,
                padding=padding_symmetric(horizontal=16, vertical=8),
                animate=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
            )
            row.on_hover = make_hover(row, row_bg)
            self.logs_column.controls.append(row)

        safe_update(self.page_ref)
