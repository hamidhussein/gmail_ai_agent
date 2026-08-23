"""
GmailAI Assistant - Daily AI Briefings Viewer for Flet
"""
import flet as ft
from resources.styles.theme import (
    COLORS,
    border_all,
    padding_all,
    padding_symmetric,
)
from database.repository import repository
from database.models import DailyDigestRecord
from automation.daily_digest import daily_digest_generator


class DailyDigestsView(ft.Container):
    """Historical daily executive briefings with collapsible markdown cards and on-demand generation."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.gen_btn_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLORS["text_primary"], visible=False)
        self.gen_btn = ft.ElevatedButton(
            content=ft.Row([
                self.gen_btn_spinner,
                ft.Text("Generate Today's Briefing", weight=ft.FontWeight.BOLD, size=13),
            ], spacing=8, tight=True),
            bgcolor=COLORS["primary"],
            color=COLORS["text_primary"],
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self._generate_now(),
        )

        self.digests_column = ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                ft.Row([
                    ft.Column([
                        ft.Text("Daily AI Intelligence Briefings", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Executive morning briefings summarizing inbox trends, VIP highlights, and action items.", size=13, color=COLORS["text_secondary"]),
                    ], spacing=2),
                    self.gen_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Container(
                    content=self.digests_column,
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

        self.load_digests()

    def refresh_data(self) -> None:
        self.load_digests()

    def load_digests(self) -> None:
        self.digests_column.controls.clear()
        session = repository.get_session()
        try:
            digests = session.query(DailyDigestRecord).order_by(DailyDigestRecord.digest_date.desc()).limit(20).all()
        finally:
            session.close()

        if not digests:
            self.digests_column.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.CALENDAR_MONTH, size=54, color=COLORS["text_muted"]),
                        ft.Text("No briefings generated yet", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Click 'Generate Today's Briefing' above to create one.", size=13, color=COLORS["text_secondary"]),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.alignment.center,
                    padding=60,
                )
            )
            if self.page:
                self.page.update()
            return

        for d in digests:
            card = self._build_digest_card(d)
            self.digests_column.controls.append(card)

        if self.page:
            self.page.update()

    def _build_digest_card(self, d: DailyDigestRecord) -> ft.Container:
        return ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row([
                    ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=COLORS["primary"], size=20),
                    ft.Text(f"Briefing Date: {d.digest_date}", size=15, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    ft.Container(expand=True),
                    ft.Row([
                        self._badge(f"{d.total_emails} emails", COLORS["secondary"]),
                        self._badge(f"{d.important_count} VIP", COLORS["success"]),
                        self._badge(f"{d.need_reply_count} replies", COLORS["warning"]),
                        self._badge(f"{d.cleanup_suggested_count} clutter", COLORS["danger"]),
                    ], spacing=6),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                controls=[
                    ft.Container(
                        content=ft.Markdown(
                            d.summary_markdown,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                        padding=16,
                        bgcolor=COLORS["bg_main"],
                        border_radius=8,
                    )
                ],
                initially_expanded=False,
            ),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=12,
            padding=padding_symmetric(horizontal=12, vertical=4),
        )

    def _badge(self, text: str, color: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            bgcolor=color,
            padding=padding_symmetric(horizontal=8, vertical=4),
            border_radius=6,
        )

    def _generate_now(self) -> None:
        self.gen_btn_spinner.visible = True
        self.gen_btn.disabled = True
        if self.page:
            self.page.update()

        try:
            daily_digest_generator.generate_digest_for_today()
            if self.page:
                self.page.open(ft.SnackBar(ft.Text("Today's briefing generated!"), bgcolor=COLORS["success"]))
            self.load_digests()
        except Exception as e:
            if self.page:
                self.page.open(ft.SnackBar(ft.Text(f"Failed to generate briefing: {e}"), bgcolor=COLORS["danger"]))
        finally:
            self.gen_btn_spinner.visible = False
            self.gen_btn.disabled = False
            if self.page:
                self.page.update()
