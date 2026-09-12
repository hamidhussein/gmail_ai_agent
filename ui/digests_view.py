"""
GmailAI Assistant - Daily AI Briefings Viewer for Flet
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
    icon_badge,
)
from database.repository import repository
from database.models import DailyDigestRecord
from automation.daily_digest import daily_digest_generator


class DailyDigestsView(ft.Container):
    """Historical daily executive briefings with collapsible markdown cards and on-demand generation."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.gen_btn_spinner = ft.ProgressRing(width=16, height=16, stroke_width=2, color="#FFFFFF", visible=False)
        self.gen_btn = ft.ElevatedButton(
            content=ft.Row([
                self.gen_btn_spinner,
                ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color="#FFFFFF"),
                ft.Text("Generate Today's Briefing", weight=ft.FontWeight.BOLD, size=13),
            ], spacing=8, tight=True),
            bgcolor=COLORS["primary"],
            color="#FFFFFF",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=2,
            ),
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
                    ft.Row([
                        icon_badge(ft.Icons.CALENDAR_MONTH, size=18, pad=8, radius=10),
                        ft.Column([
                            ft.Text("Daily Intelligence Briefings", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ft.Text("Morning inbox summaries, VIP highlights, and action items.", size=12, color=COLORS["text_secondary"]),
                        ], spacing=2),
                    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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
                empty_state(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    title="No Briefings Generated Yet",
                    subtitle="Click 'Generate Today's Briefing' above to create an AI synthesis of your inbox.",
                )
            )
            safe_update(self.page_ref)
            return

        for d in digests:
            card = self._build_digest_card(d)
            self.digests_column.controls.append(card)

        safe_update(self.page_ref)

    def _build_digest_card(self, d: DailyDigestRecord) -> ft.Container:
        def on_hover(e):
            container.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
            safe_update(container)

        container = ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color="#FFFFFF", size=14),
                        bgcolor=COLORS["primary"],
                        padding=5,
                        border_radius=6,
                    ),
                    ft.Text(f"Briefing — {d.digest_date}", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                    ft.Container(expand=True),
                    ft.Row([
                        pill_badge(f"{d.total_emails} emails", COLORS["badge_bg"], COLORS["badge_text"]),
                        pill_badge(f"{d.important_count} VIP", COLORS["success_soft"], COLORS["success"]),
                        pill_badge(f"{d.need_reply_count} replies", COLORS["warning_soft"], COLORS["warning"]),
                        pill_badge(f"{d.cleanup_suggested_count} clutter", COLORS["danger_soft"], COLORS["danger"]),
                    ], spacing=5),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                controls=[
                    ft.Container(
                        content=ft.Markdown(
                            d.summary_markdown,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                        padding=16,
                        bgcolor=COLORS["surface_alt"],
                        border=border_all(1, COLORS["border"]),
                        border_radius=8,
                    )
                ],
                expanded=False,
            ),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["accent"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=10,
            padding=padding_symmetric(horizontal=12, vertical=4),
            on_hover=on_hover,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        return container

    def _generate_now(self) -> None:
        self.gen_btn_spinner.visible = True
        self.gen_btn.disabled = True
        safe_update(self.page_ref)

        def worker():
            gen_err = None
            try:
                daily_digest_generator.generate_digest_for_today()
            except Exception as e:
                gen_err = e

            async def _apply_result():
                self.gen_btn_spinner.visible = False
                self.gen_btn.disabled = False
                if gen_err is None:
                    if self.page_ref:
                        try:
                            self.page_ref.open(ft.SnackBar(ft.Text("Today's briefing generated!"), bgcolor=COLORS["success"]))
                        except Exception:
                            pass
                    self.load_digests()
                else:
                    from core.error_reporter import format_user_error
                    msg = format_user_error(gen_err, "generate daily briefing")
                    if self.page_ref:
                        try:
                            self.page_ref.open(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["danger"]))
                        except Exception:
                            pass
                safe_update(self.page_ref)

            try:
                self.page_ref.run_task(_apply_result)
            except Exception:
                self.gen_btn_spinner.visible = False
                self.gen_btn.disabled = False
                self.load_digests()
                safe_update(self.page_ref)

        import threading
        threading.Thread(target=worker, daemon=True).start()
