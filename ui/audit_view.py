"""
GmailAI Assistant - Action Audit Logs Viewer for Flet
"""
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    padding_all,
    padding_symmetric,
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
                    ft.Column([
                        ft.Text("Security & Action Audit Trail", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Immutable local record of all automated and approved email operations.", size=13, color=COLORS["text_secondary"]),
                    ], spacing=2),
                    ft.OutlinedButton(
                        "Refresh Logs",
                        icon=ft.Icons.REFRESH,
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
                    padding=padding_symmetric(horizontal=16, vertical=8),
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
                ft.Container(
                    content=ft.Text("No audit logs recorded yet.", size=13, color=COLORS["text_muted"]),
                    alignment=ft.alignment.center,
                    padding=40,
                )
            )
            if self.page:
                self.page.update()
            return

        for entry in logs:
            time_str = entry.executed_at.strftime("%Y-%m-%d %H:%M:%S") if entry.executed_at else "Just now"
            act_col = COLORS["danger"] if entry.action_type == "MOVE_TRASH" else (COLORS["success"] if entry.action_type == "DRAFT_REPLY" else COLORS["secondary"])
            appr_str = "YES (2x)" if entry.double_confirmed else ("YES" if entry.user_approved else "AUTO")
            appr_col = COLORS["success"] if entry.user_approved else COLORS["warning"]

            row = ft.Container(
                content=ft.Row([
                    ft.Text(time_str, size=12, color=COLORS["text_secondary"], width=150),
                    ft.Container(
                        content=ft.Text(entry.action_type or "ACTION", size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        bgcolor=act_col,
                        padding=padding_symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                        width=110,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(entry.sender or "(None)", size=12, color=COLORS["text_primary"], width=180, no_wrap=True),
                    ft.Text(entry.subject or "(No Subject)", size=12, color=COLORS["text_secondary"], expand=True, no_wrap=True),
                    ft.Text(appr_str, size=12, weight=ft.FontWeight.BOLD, color=appr_col, width=100),
                    ft.Text(entry.reason or "Rule execution", size=11, color=COLORS["text_muted"], width=180, no_wrap=True),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                bgcolor=COLORS["bg_card"],
                border=border_all(1, COLORS["border"]),
                border_radius=8,
                padding=padding_symmetric(horizontal=16, vertical=8),
            )
            self.logs_column.controls.append(row)

        if self.page:
            self.page.update()
