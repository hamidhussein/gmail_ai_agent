"""
GmailAI Assistant - Polished Intelligence Inbox & Reader for Flet
"""
import re
import html
import json
import datetime
import threading
import flet as ft
from typing import Dict, Any, List, Optional
from app.constants import ReplyTone
from resources.styles.theme import (
    COLORS,
    get_category_color,
    border_all,
    border_only,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
    empty_state,
    pill_badge,
)
from ui.components.reply_modal import ReplyDialog
from database.repository import repository
from gmail.actions import gmail_actions
from ai.reply_generator import reply_generator
from memory.learning import learning_engine
from memory.user_profile import user_profile_manager
from core.events import event_bus, EVT_SUGGESTION_ACTIONED, EVT_SYNC_COMPLETED

AVATAR_PALETTE = [
    "#2563EB",  # Sapphire Blue
    "#0EA5E9",  # Sky Blue
    "#10B981",  # Emerald
    "#0D9488",  # Teal
    "#F59E0B",  # Amber
    "#EC4899",  # Pink
    "#8B5CF6",  # Violet
    "#14B8A6",  # Cyan Teal
]

FILTER_OPTIONS = [
    ("ALL", "All", ft.Icons.INBOX_OUTLINED),
    ("UNREAD", "Unread", ft.Icons.MARK_EMAIL_UNREAD_OUTLINED),
    ("STARRED", "Starred", ft.Icons.STAR_OUTLINE),
    ("CLIENT", "Client", ft.Icons.PERSON_OUTLINE),
    ("WORK", "Work", ft.Icons.BUSINESS_CENTER_OUTLINED),
    ("BANK", "Bank", ft.Icons.ACCOUNT_BALANCE_OUTLINED),
    ("FINANCE", "Finance", ft.Icons.ATTACH_MONEY_OUTLINED),
    ("LEGAL", "Legal", ft.Icons.GAVEL_OUTLINED),
    ("NEWSLETTER", "Newsletters", ft.Icons.NEWSPAPER_OUTLINED),
    ("PROMOTION", "Promotions", ft.Icons.LOCAL_OFFER_OUTLINED),
    ("SOCIAL", "Social", ft.Icons.PEOPLE_OUTLINE),
    ("SPAM", "Spam", ft.Icons.REPORT_GMAILERRORRED_OUTLINED),
]


def get_sender_initials(name: str, email: str) -> str:
    """Returns 1-2 uppercase initials from sender name or email."""
    cleaned = (name or "").strip()
    if not cleaned:
        cleaned = (email or "").split("@")[0].strip()
    if not cleaned:
        return "?"

    words = cleaned.split()
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    return cleaned[:2].upper()


def get_avatar_color(text: str) -> str:
    """Returns a deterministic accent color for the avatar."""
    val = sum(ord(c) for c in (text or "A"))
    return AVATAR_PALETTE[val % len(AVATAR_PALETTE)]


def clean_email_text(raw_text: str) -> str:
    """Decodes HTML entities, removes raw angle brackets from links, and cleans whitespace."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    # Remove angle brackets around standalone URLs: <https://...> -> https://...
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_date_display(dt: Any) -> str:
    """Formats datetime into human-friendly representation."""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except Exception:
            return dt

    now = datetime.datetime.utcnow()
    diff = now - dt

    if diff.days == 0:
        return dt.strftime("%I:%M %p").lstrip("0")
    elif diff.days == 1:
        return f"Yesterday {dt.strftime('%I:%M %p').lstrip('0')}"
    elif diff.days < 7:
        return dt.strftime("%a %I:%M %p")
    elif dt.year == now.year:
        return dt.strftime("%b %d")
    else:
        return dt.strftime("%b %d, %Y")


def format_full_date(dt: Any) -> str:
    """Returns full timestamp format (e.g. Wednesday, Jul 29, 2026 • 10:45 AM)."""
    if not dt:
        return "Unknown Date"
    if isinstance(dt, str):
        try:
            dt = datetime.datetime.fromisoformat(dt)
        except Exception:
            return dt
    return dt.strftime("%A, %b %d, %Y • %I:%M %p").lstrip("0")


class InboxIntelligenceView(ft.Container):
    """Polished Intelligence Inbox with clean markdown email reader, metadata cards, and AI analysis."""

    def __init__(self, page: ft.Page, **kwargs):
        self.page_ref = page
        self.current_filter = "ALL"
        self.search_query = ""
        self.selected_email: Optional[Dict[str, Any]] = None
        self.emails_data: List[Any] = []

        # Internal card reference tracking for silky smooth in-place selection
        self.card_refs: Dict[int, ft.Container] = {}
        self.unread_dot_refs: Dict[int, ft.Container] = {}
        self.subj_text_refs: Dict[int, ft.Text] = {}
        self.sender_text_refs: Dict[int, ft.Text] = {}
        self.star_btn_refs: Dict[int, ft.IconButton] = {}

        # Detail view star & read button refs for live updates
        self.detail_star_btn: Optional[ft.IconButton] = None
        self.detail_read_btn: Optional[ft.IconButton] = None

        # Top search field with clear suffix
        self.clear_search_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            icon_size=16,
            icon_color=COLORS["text_muted"],
            tooltip="Clear search",
            visible=False,
            on_click=self._on_clear_search,
        )

        self.search_field = ft.TextField(
            hint_text="Search sender, subject, keywords...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=self.clear_search_btn,
            border_color=COLORS["border"],
            bgcolor=COLORS["bg_card"],
            focused_border_color=COLORS["primary"],
            text_size=13,
            content_padding=10,
            width=320,
            on_change=self._on_search_change,
        )

        # Count indicator
        self.count_badge = ft.Text("Loading emails...", size=12, color=COLORS["text_secondary"])

        # Filter chips row
        self.chip_controls = []
        for key, label, icon_name in FILTER_OPTIONS:
            is_active = (key == "ALL")
            chip = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        icon_name,
                        size=13,
                        color=COLORS["chip_active_text"] if is_active else COLORS["text_muted"],
                    ),
                    ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=COLORS["chip_active_text"] if is_active else COLORS["text_secondary"],
                    ),
                ], spacing=5, tight=True),
                bgcolor=COLORS["chip_active_bg"] if is_active else "transparent",
                border=border_all(1, COLORS["border"]),
                border_radius=100,
                padding=padding_symmetric(horizontal=10, vertical=5),
                on_click=lambda e, k=key: self._on_filter_click(k),
                animate=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
            )
            self.chip_controls.append((key, chip))

        self.filter_chips_row = ft.Row(
            spacing=6,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[c for _, c in self.chip_controls],
        )

        # Left Column: Email list
        self.email_list_column = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Right Column: Detail Reader Container
        self.detail_container = ft.Container(
            content=empty_state(
                icon=ft.Icons.MARK_EMAIL_READ_OUTLINED,
                title="Intelligence Reader",
                subtitle="Select an email to view conversation details, AI triage insights, and action items.",
            ),
            bgcolor=COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(1, COLORS["border"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=12,
            padding=0,
            expand=16,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        content = ft.Column(
            expand=True,
            spacing=16,
            controls=[
                # Top Header Row
                ft.Row([
                    ft.Column([
                        ft.Row([
                            ft.Text("Intelligence Inbox", size=24, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            ft.Container(
                                content=self.count_badge,
                                bgcolor=COLORS["badge_bg"],
                                padding=padding_symmetric(horizontal=8, vertical=3),
                                border_radius=12,
                                border=border_all(1, COLORS["border"]),
                            ),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text("Categorized, analyzed, and action-ready email management.", size=13, color=COLORS["text_secondary"]),
                    ], spacing=2),
                    ft.Row([
                        self.search_field,
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_size=20,
                            icon_color=COLORS["text_secondary"],
                            tooltip="Refresh inbox",
                            on_click=lambda e: self.load_emails(),
                        ),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                # Category Filter Chips Row
                self.filter_chips_row,

                # Split Master-Detail Layout
                ft.Row([
                    # Email List (8 parts)
                    ft.Container(
                        content=self.email_list_column,
                        expand=8,
                    ),
                    # Email Detail Reader (16 parts — more reading space)
                    self.detail_container,
                ], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.START),
            ],
        )

        super().__init__(
            content=content,
            expand=True,
            padding=padding_all(24),
            **kwargs,
        )

        self.load_emails()

    def refresh_data(self) -> None:
        self.load_emails()

    def _on_clear_search(self, e):
        self.search_field.value = ""
        self.clear_search_btn.visible = False
        safe_update(self.search_field)
        self.search_query = ""
        self.load_emails()

    def _on_search_change(self, e):
        val = (self.search_field.value or "").strip()
        self.clear_search_btn.visible = bool(val)
        safe_update(self.search_field)
        self.search_query = val
        self.load_emails()

    def _on_filter_click(self, filter_key: str):
        self.current_filter = filter_key
        for key, chip in self.chip_controls:
            is_active = (key == filter_key)
            chip.bgcolor = COLORS["chip_active_bg"] if is_active else "transparent"
            chip.border = border_all(1, COLORS["border"])
            row = chip.content
            row.controls[0].color = COLORS["chip_active_text"] if is_active else COLORS["text_muted"]
            row.controls[1].color = COLORS["chip_active_text"] if is_active else COLORS["text_secondary"]
            row.controls[1].weight = ft.FontWeight.W_500
        safe_update(self.filter_chips_row)
        self.load_emails()

    def load_emails(self) -> None:
        """Loads emails from repository according to the active filter and search query."""
        # Determine filter parameters
        category = None
        is_unread = None
        is_starred = None

        if self.current_filter == "UNREAD":
            is_unread = True
        elif self.current_filter == "STARRED":
            is_starred = True
        elif self.current_filter != "ALL":
            category = self.current_filter

        # Determine active account for mailbox scoping
        account = repository.get_active_account()
        active_account_id = account.id if account else None

        emails = repository.get_inbox_emails(
            account_id=active_account_id,
            category=category,
            is_unread=is_unread,
            is_starred=is_starred,
            search_query=self.search_query if self.search_query else None,
            limit=100,
        )

        # Check if rendered controls already match the fetched emails to avoid rebuilding cards
        new_signatures = [(e.id, e.is_unread, getattr(e, "is_starred", False)) for e in emails]
        existing_signatures = [
            (getattr(e, "id", None), getattr(e, "is_unread", None), getattr(e, "is_starred", False))
            for e in getattr(self, "emails_data", [])
        ]
        if self.email_list_column.controls and new_signatures == existing_signatures:
            return

        self.emails_data = emails
        self.email_list_column.controls.clear()
        self.card_refs.clear()
        self.unread_dot_refs.clear()
        self.subj_text_refs.clear()
        self.sender_text_refs.clear()
        self.star_btn_refs.clear()

        count = len(emails)
        if count == 0:
            self.count_badge.value = "0 emails"
            self.email_list_column.controls.append(
                empty_state(
                    icon=ft.Icons.INBOX_OUTLINED,
                    title="No emails found",
                    subtitle="Try selecting a different filter or clearing search.",
                )
            )
            # Empty reader state
            self.detail_container.content = empty_state(
                icon=ft.Icons.MARK_EMAIL_READ_OUTLINED,
                title="No email selected",
                subtitle="Select an email from the left list to read messages and AI intelligence.",
            )
            safe_update(self.count_badge)
            safe_update(self.detail_container)
            safe_update(self.email_list_column)
            return

        self.count_badge.value = f"{count} email{'s' if count != 1 else ''}"
        safe_update(self.count_badge)

        # Build card controls
        for email in emails:
            card = self._build_email_card(email)
            self.email_list_column.controls.append(card)

        # Re-render detail pane
        matched = None
        if self.selected_email:
            matched = next((e for e in emails if e.id == self.selected_email.get("id")), None)

        if matched:
            self._render_email_detail(self._email_to_dict(matched))
        else:
            first = emails[0]
            self.selected_email = self._email_to_dict(first)
            # Highlight first card
            first_card = self.card_refs.get(first.id)
            if first_card:
                first_cat_color = get_category_color(first.category)
                first_card.bgcolor = COLORS["badge_bg"]
                first_card.border = border_only(
                    left=ft.BorderSide(3, first_cat_color),
                    top=ft.BorderSide(1, COLORS["primary"]),
                    right=ft.BorderSide(1, COLORS["primary"]),
                    bottom=ft.BorderSide(1, COLORS["primary"]),
                )
            self._render_email_detail(self.selected_email)

        safe_update(self.page_ref)

    def _email_to_dict(self, email: Any) -> Dict[str, Any]:
        """Serialises an EmailRecord model into a safe plain dictionary for views."""
        return {
            "id": email.id,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "sender_name": email.sender_name,
            "recipient": email.recipient,
            "subject": email.subject,
            "snippet": email.snippet,
            "body_plain": email.body_plain,
            "received_at": email.received_at,
            "is_unread": email.is_unread,
            "is_starred": email.is_starred,
            "is_archived": email.is_archived,
            "category": email.category,
            "importance_score": email.importance_score,
            "urgency_score": email.urgency_score,
            "risk_level": getattr(email, "risk_level", "LOW") or "LOW",
            "suggested_action": getattr(email, "suggested_action", "KEEP") or "KEEP",
            "reasoning": getattr(email, "ai_reasoning", None) or getattr(email, "reasoning", "") or "",
            "action_items": getattr(email, "action_items_json", None) or getattr(email, "action_items", "[]") or "[]",
            "has_attachments": getattr(email, "has_attachments", False),
        }

    def _build_email_card(self, email: Any) -> ft.Container:
        cat = email.category or "PERSONAL"
        cat_color = get_category_color(cat)
        importance = email.importance_score or 50
        is_unread = email.is_unread
        is_starred = getattr(email, "is_starred", False)
        is_selected = bool(self.selected_email and (self.selected_email.get("id") == email.id))

        clean_subj = clean_email_text(email.subject or "(No Subject)")
        clean_snip = clean_email_text(email.snippet or "")
        date_str = format_date_display(email.received_at)

        sender_display = email.sender_name or (email.sender.split("<")[0].strip() if email.sender else "Unknown")
        initials = get_sender_initials(email.sender_name, email.sender)
        avatar_bg = get_avatar_color(sender_display)

        # Unread dot indicator
        unread_dot = ft.Container(
            width=8,
            height=8,
            border_radius=4,
            bgcolor=COLORS["primary"] if is_unread else "transparent",
        )
        self.unread_dot_refs[email.id] = unread_dot

        # Sender & Subject text controls
        sender_text = ft.Text(
            sender_display,
            size=13,
            weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.W_500,
            color=COLORS["text_primary"],
            expand=True,
            no_wrap=True,
        )
        self.sender_text_refs[email.id] = sender_text

        subj_text = ft.Text(
            clean_subj,
            size=12,
            weight=ft.FontWeight.BOLD if is_unread else ft.FontWeight.NORMAL,
            color=COLORS["text_primary"] if is_unread else COLORS["text_secondary"],
            no_wrap=True,
        )
        self.subj_text_refs[email.id] = subj_text

        # Quick Star Button
        star_btn = ft.IconButton(
            icon=ft.Icons.STAR if is_starred else ft.Icons.STAR_BORDER,
            icon_size=18,
            icon_color=COLORS["warning"] if is_starred else COLORS["text_muted"],
            tooltip="Star email" if not is_starred else "Unstar email",
            on_click=lambda e, em=email: self._toggle_star_from_card(em),
        )
        self.star_btn_refs[email.id] = star_btn

        # Attachment Indicator
        attachment_icon = ft.Icon(
            ft.Icons.ATTACH_FILE,
            size=13,
            color=COLORS["text_muted"],
            visible=getattr(email, "has_attachments", False),
        )

        # Action items count badge
        action_items_raw = getattr(email, "action_items_json", None) or getattr(email, "action_items", None)
        task_count = 0
        if action_items_raw:
            try:
                tasks = json.loads(action_items_raw) if isinstance(action_items_raw, str) else action_items_raw
                if isinstance(tasks, list):
                    task_count = len(tasks)
            except Exception:
                task_count = 0

        urgency = getattr(email, "urgency_score", 0) or 0
        risk = getattr(email, "risk_level", "LOW") or "LOW"

        sub_badges = []
        if urgency >= 70 or risk in ("HIGH", "CRITICAL"):
            sub_badges.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.BOLT, size=10, color="#FFFFFF"),
                        ft.Text("URGENT", size=8, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    ], spacing=1, tight=True),
                    bgcolor=COLORS["danger"] if risk in ("HIGH", "CRITICAL") else COLORS["warning"],
                    padding=padding_symmetric(horizontal=4, vertical=1),
                    border_radius=3,
                    tooltip=f"Urgency score: {urgency}/100 • Risk: {risk}",
                )
            )
        if task_count > 0:
            sub_badges.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECKLIST, size=10, color=COLORS["primary"]),
                        ft.Text(f"{task_count}", size=8, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                    ], spacing=2, tight=True),
                    bgcolor=COLORS["badge_bg"],
                    padding=padding_symmetric(horizontal=4, vertical=1),
                    border_radius=3,
                    tooltip=f"{task_count} action item{'s' if task_count != 1 else ''}",
                )
            )

        right_col_controls = [
            ft.Row([
                ft.Container(
                    content=ft.Text(cat[:6], size=9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=cat_color,
                    padding=padding_symmetric(horizontal=5, vertical=2),
                    border_radius=4,
                ),
                star_btn,
            ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        ]
        if sub_badges:
            right_col_controls.append(
                ft.Row(sub_badges, spacing=3, tight=True, alignment=ft.MainAxisAlignment.END)
            )

        card = ft.Container(
            content=ft.Row([
                # Left indicator & Avatar
                unread_dot,
                ft.Container(
                    content=ft.Text(initials, size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=avatar_bg,
                    width=28,
                    height=28,
                    border_radius=14,
                    alignment=align_center(),
                ),

                # Middle Text Area
                ft.Column([
                    ft.Row([
                        sender_text,
                        ft.Row([
                            attachment_icon,
                            ft.Text(date_str, size=11, color=COLORS["text_muted"]),
                        ], spacing=3, tight=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                    subj_text,

                    ft.Text(
                        clean_snip,
                        size=11,
                        color=COLORS["text_muted"],
                        max_lines=1,
                        no_wrap=True,
                    ),
                ], expand=True, spacing=2),

                # Right: category badge + star + indicators
                ft.Column(
                    right_col_controls,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=2,
                ),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=7),
            bgcolor=COLORS["badge_bg"] if is_selected else COLORS["bg_card"],
            border=border_only(
                left=ft.BorderSide(3, cat_color),
                top=ft.BorderSide(1, COLORS["primary"] if is_selected else COLORS["border"]),
                right=ft.BorderSide(1, COLORS["primary"] if is_selected else COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["primary"] if is_selected else COLORS["border"]),
            ),
            border_radius=8,
            padding=padding_symmetric(horizontal=10, vertical=8),
            on_click=lambda e, em=email: self._on_email_clicked(em),
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )

        def on_card_hover(e):
            if not (self.selected_email and self.selected_email.get("id") == email.id):
                card.bgcolor = COLORS["bg_card_hover"] if e.data == "true" else COLORS["bg_card"]
                safe_update(card)

        card.on_hover = on_card_hover
        self.card_refs[email.id] = card
        return card

    def _on_email_clicked(self, email: Any):
        data = self._email_to_dict(email)
        prev_id = self.selected_email.get("id") if self.selected_email else None
        new_id = email.id

        # In-place style transition of previous card
        if prev_id and prev_id != new_id and prev_id in self.card_refs:
            prev_card = self.card_refs[prev_id]
            prev_email = next((em for em in self.emails_data if em.id == prev_id), None)
            prev_cat_color = get_category_color(prev_email.category) if prev_email else COLORS["border"]
            prev_card.bgcolor = COLORS["bg_card"]
            prev_card.border = border_only(
                left=ft.BorderSide(3, prev_cat_color),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            )
            safe_update(prev_card)

        # In-place style transition of active card
        if new_id in self.card_refs:
            active_card = self.card_refs[new_id]
            active_cat_color = get_category_color(email.category)
            active_card.bgcolor = COLORS["badge_bg"]
            active_card.border = border_only(
                left=ft.BorderSide(3, active_cat_color),
                top=ft.BorderSide(1, COLORS["primary"]),
                right=ft.BorderSide(1, COLORS["primary"]),
                bottom=ft.BorderSide(1, COLORS["primary"]),
            )
            safe_update(active_card)

        # Mark as read in repo & actions in-place
        if email.is_unread:
            try:
                gmail_actions.mark_as_read(
                    email.message_id,
                    sender=email.sender,
                    subject=email.subject or "",
                )
                email.is_unread = False
                data["is_unread"] = False
                learning_engine.record_read(email.sender)

                if new_id in self.unread_dot_refs:
                    dot = self.unread_dot_refs[new_id]
                    dot.bgcolor = "transparent"
                    safe_update(dot)
                if new_id in self.subj_text_refs:
                    st = self.subj_text_refs[new_id]
                    st.weight = ft.FontWeight.NORMAL
                    st.color = COLORS["text_secondary"]
                    safe_update(st)
                if new_id in self.sender_text_refs:
                    sndt = self.sender_text_refs[new_id]
                    sndt.weight = ft.FontWeight.W_500
                    safe_update(sndt)

                event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)
            except Exception as ex:
                self._show_action_error("Mark as read", ex)

        self.selected_email = data
        self._render_email_detail(data)

    def _toggle_star_from_card(self, email: Any):
        new_starred = not getattr(email, "is_starred", False)
        try:
            gmail_actions.set_starred(email.message_id, new_starred)
        except Exception as ex:
            self._show_action_error("Update star", ex)
            return
        email.is_starred = new_starred

        # Update card button in place
        if email.id in self.star_btn_refs:
            btn = self.star_btn_refs[email.id]
            btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
            btn.icon_color = COLORS["warning"] if new_starred else COLORS["text_muted"]
            btn.tooltip = "Unstar email" if new_starred else "Star email"
            safe_update(btn)

        # If currently opened in detail pane, update detail pane button
        if self.selected_email and self.selected_email.get("id") == email.id:
            self.selected_email["is_starred"] = new_starred
            if self.detail_star_btn:
                self.detail_star_btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
                self.detail_star_btn.icon_color = COLORS["warning"] if new_starred else COLORS["text_muted"]
                self.detail_star_btn.tooltip = "Unstar" if new_starred else "Star"
                safe_update(self.detail_star_btn)

        msg = "Email starred" if new_starred else "Email unstarred"
        try:
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["warning"] if new_starred else COLORS["text_secondary"]))
        except Exception:
            pass

    def _toggle_star_from_detail(self, data: Dict[str, Any]):
        new_starred = not data.get("is_starred", False)
        try:
            gmail_actions.set_starred(data["message_id"], new_starred)
        except Exception as ex:
            self._show_action_error("Update star", ex)
            return
        data["is_starred"] = new_starred

        email_id = data.get("id")
        if email_id and email_id in self.star_btn_refs:
            btn = self.star_btn_refs[email_id]
            btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
            btn.icon_color = COLORS["warning"] if new_starred else COLORS["text_muted"]
            btn.tooltip = "Unstar email" if new_starred else "Star email"
            safe_update(btn)

        if self.detail_star_btn:
            self.detail_star_btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
            self.detail_star_btn.icon_color = COLORS["warning"] if new_starred else COLORS["text_muted"]
            self.detail_star_btn.tooltip = "Unstar" if new_starred else "Star"
            safe_update(self.detail_star_btn)

        msg = "Email starred" if new_starred else "Email unstarred"
        try:
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["warning"] if new_starred else COLORS["text_secondary"]))
        except Exception:
            pass

    def _toggle_read_status(self, data: Dict[str, Any]):
        new_unread = not data.get("is_unread", False)
        try:
            gmail_actions.set_read_status(
                data["message_id"],
                new_unread,
                sender=data.get("sender", ""),
                subject=data.get("subject", ""),
            )
        except Exception as ex:
            self._show_action_error("Update read status", ex)
            return
        data["is_unread"] = new_unread

        email_id = data.get("id")
        if email_id and email_id in self.unread_dot_refs:
            dot = self.unread_dot_refs[email_id]
            dot.bgcolor = COLORS["primary"] if new_unread else "transparent"
            safe_update(dot)
        if email_id and email_id in self.subj_text_refs:
            st = self.subj_text_refs[email_id]
            st.weight = ft.FontWeight.BOLD if new_unread else ft.FontWeight.NORMAL
            st.color = COLORS["text_primary"] if new_unread else COLORS["text_secondary"]
            safe_update(st)
        if email_id and email_id in self.sender_text_refs:
            sndt = self.sender_text_refs[email_id]
            sndt.weight = ft.FontWeight.BOLD if new_unread else ft.FontWeight.W_500
            safe_update(sndt)

        if self.detail_read_btn:
            self.detail_read_btn.icon = ft.Icons.MARK_EMAIL_READ_OUTLINED if new_unread else ft.Icons.MARK_EMAIL_UNREAD_OUTLINED
            self.detail_read_btn.icon_color = COLORS["text_secondary"]
            self.detail_read_btn.tooltip = "Mark as Read" if new_unread else "Mark as Unread"
            safe_update(self.detail_read_btn)

        event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)
        msg = "Marked as unread" if new_unread else "Marked as read"
        try:
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["primary"]))
        except Exception:
            pass

    def _render_email_detail(self, data: Dict[str, Any]) -> None:
        """Renders the right-hand rich reading pane with full AI intelligence, sender chip, and HTML cleanup."""
        cat = data.get("category", "PERSONAL")
        cat_color = get_category_color(cat)
        importance = data.get("importance_score", 50)
        urgency = data.get("urgency_score", 40)
        action = data.get("suggested_action", "KEEP")
        is_starred = data.get("is_starred", False)
        is_unread = data.get("is_unread", False)
        reasoning = clean_email_text(data.get("reasoning") or "Email classified and scored according to sender priority and context.")
        date_full = format_full_date(data.get("received_at"))

        sender_name = data.get("sender_name") or data.get("sender", "Unknown")
        sender_email = data.get("sender", "")
        recipient = data.get("recipient") or "Me"
        initials = get_sender_initials(sender_name, sender_email)
        avatar_bg = get_avatar_color(sender_name)

        action_chips = []
        raw_actions = data.get("action_items") or []
        if isinstance(raw_actions, str):
            try:
                raw_actions = json.loads(raw_actions)
            except Exception:
                raw_actions = [raw_actions]
        if isinstance(raw_actions, list):
            for item in raw_actions:
                task_str = clean_email_text(str(item))
                if task_str:
                    action_chips.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=15, color=COLORS["success"]),
                                ft.Text(task_str, size=12, color=COLORS["text_primary"], expand=True),
                            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            bgcolor=COLORS["bg_card"],
                            border=border_all(1, COLORS["border"]),
                            padding=padding_symmetric(horizontal=12, vertical=8),
                            border_radius=8,
                        )
                    )

        body_content = data.get("body_plain") or data.get("snippet") or "(Empty message body)"

        # Pinned Toolbar action buttons
        star_btn = ft.IconButton(
            icon=ft.Icons.STAR if is_starred else ft.Icons.STAR_BORDER,
            icon_size=18,
            icon_color=COLORS["warning"] if is_starred else COLORS["text_muted"],
            tooltip="Star" if not is_starred else "Unstar",
            on_click=lambda e: self._toggle_star_from_detail(data),
        )
        read_btn = ft.IconButton(
            icon=ft.Icons.MARK_EMAIL_READ_OUTLINED if is_unread else ft.Icons.MARK_EMAIL_UNREAD_OUTLINED,
            icon_size=18,
            icon_color=COLORS["text_secondary"],
            tooltip="Mark as Read" if is_unread else "Mark as Unread",
            on_click=lambda e: self._toggle_read_status(data),
        )
        self.detail_star_btn = star_btn
        self.detail_read_btn = read_btn

        self.detail_container.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Pinned Toolbar (non-scrollable)
                ft.Container(
                    content=ft.Row([
                        ft.ElevatedButton(
                            "Reply with AI",
                            icon=ft.Icons.AUTO_AWESOME,
                            style=ft.ButtonStyle(
                                bgcolor=COLORS["primary"],
                                color="#FFFFFF",
                                shape=ft.RoundedRectangleBorder(radius=6),
                                padding=padding_symmetric(horizontal=12, vertical=6),
                            ),
                            tooltip="Open Full AI Auto-Reply Assistant Dialog",
                            on_click=lambda e: self._open_reply_dialog(data),
                        ),
                        ft.Container(width=1, height=18, bgcolor=COLORS["border"]),
                        star_btn,
                        read_btn,
                        ft.IconButton(
                            icon=ft.Icons.ARCHIVE_OUTLINED,
                            icon_size=18,
                            icon_color=COLORS["text_secondary"],
                            tooltip="Archive",
                            on_click=lambda e: self._archive_email(data),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            icon_color=COLORS["danger"],
                            tooltip="Move to Trash",
                            on_click=lambda e: self._trash_email(data),
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CONTENT_COPY,
                            icon_size=16,
                            icon_color=COLORS["text_muted"],
                            tooltip="Copy body to clipboard",
                            on_click=lambda e: self._copy_to_clipboard(body_content),
                        ),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    bgcolor=COLORS["surface_alt"],
                    border=border_only(bottom=ft.BorderSide(1, COLORS["border"])),
                    padding=padding_symmetric(horizontal=12, vertical=6),
                ),

                # Scrollable Content Area
                ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    spacing=12,
                    controls=[
                        # Subject Line
                        ft.Container(
                            content=ft.Text(data.get("subject") or "(No Subject)", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                            padding=padding_symmetric(horizontal=16, vertical=8),
                        ),

                        # Sender & Recipient Information Card
                        ft.Container(
                            content=ft.Row([
                                # Avatar
                                ft.Container(
                                    content=ft.Text(initials, size=14, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    bgcolor=avatar_bg,
                                    width=40,
                                    height=40,
                                    border_radius=20,
                                    alignment=align_center(),
                                ),

                                # Sender Info
                                ft.Column([
                                    ft.Text(sender_name, size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                                    ft.Text(f"{sender_email}  \u2022  To: {recipient}", size=11, color=COLORS["text_muted"]),
                                    ft.Text(date_full, size=11, color=COLORS["text_muted"]),
                                ], expand=True, spacing=2),

                                # Category & Score Badges
                                ft.Column([
                                    ft.Container(
                                        content=ft.Text(cat, size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                        bgcolor=cat_color,
                                        padding=padding_symmetric(horizontal=7, vertical=3),
                                        border_radius=4,
                                    ),
                                    ft.Text(
                                        f"{importance}/100",
                                        size=11,
                                        weight=ft.FontWeight.BOLD,
                                        color=COLORS["success"] if importance >= 75 else (COLORS["warning"] if importance >= 50 else COLORS["text_muted"]),
                                    ),
                                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=3),
                            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                            bgcolor=COLORS["bg_card"],
                            border=border_only(
                                left=ft.BorderSide(3, cat_color),
                                top=ft.BorderSide(1, COLORS["border"]),
                                right=ft.BorderSide(1, COLORS["border"]),
                                bottom=ft.BorderSide(1, COLORS["border"]),
                            ),
                            border_radius=8,
                            padding=12,
                            margin=padding_symmetric(horizontal=16),
                        ),

                        # AI Intelligence Insights Card
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.AUTO_AWESOME, size=12, color="#FFFFFF"),
                                        bgcolor=COLORS["primary"],
                                        padding=4,
                                        border_radius=5,
                                    ),
                                    ft.Text("AI Insights", size=12, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                                    ft.Container(expand=True),
                                    ft.Container(
                                        content=ft.Text(f"{action}", size=10, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"]),
                                        bgcolor=COLORS["badge_bg"],
                                        padding=padding_symmetric(horizontal=7, vertical=2),
                                        border_radius=5,
                                    ),
                                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Divider(height=1, color=COLORS["border"]),
                                ft.Text(reasoning, size=12, color=COLORS["text_secondary"]),
                                ft.Row([
                                    ft.Icon(ft.Icons.BOLT_OUTLINED, size=12, color=COLORS["warning"]),
                                    ft.Text(f"Urgency {urgency}", size=11, color=COLORS["text_muted"]),
                                    ft.Text("\u2022", color=COLORS["text_muted"], size=10),
                                    ft.Icon(ft.Icons.SHIELD_OUTLINED, size=12, color=COLORS["success"] if data.get("risk_level") == "LOW" else COLORS["danger"]),
                                    ft.Text(f"Risk: {data.get('risk_level', 'LOW')}", size=11, color=COLORS["success"] if data.get("risk_level") == "LOW" else COLORS["danger"]),
                                ], spacing=5),
                                ft.Column([
                                    ft.Text("Action Items:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"]),
                                    ft.Column(action_chips, spacing=4),
                                ], visible=len(action_chips) > 0, spacing=5),
                            ], spacing=8),
                            bgcolor=COLORS["surface_alt"],
                            border=border_only(
                                left=ft.BorderSide(3, COLORS["primary"]),
                                top=ft.BorderSide(1, COLORS["border"]),
                                right=ft.BorderSide(1, COLORS["border"]),
                                bottom=ft.BorderSide(1, COLORS["border"]),
                            ),
                            border_radius=8,
                            padding=14,
                            margin=padding_symmetric(horizontal=16),
                        ),

                        # Email Body Reader Container
                        ft.Container(
                            content=ft.Markdown(
                                body_content,
                                selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            ),
                            padding=16,
                            bgcolor=COLORS["bg_card"],
                            border=border_all(1, COLORS["border"]),
                            border_radius=8,
                            margin=padding_symmetric(horizontal=16, vertical=4),
                        ),

                        # Quick AI Auto-Reply Assistant Card
                        self._build_quick_reply_section(data),
                    ],
                ),
            ],
        )
        safe_update(self.detail_container)

    def _build_quick_reply_section(self, data: Dict[str, Any]) -> ft.Container:
        """Builds an embedded Quick AI Reply Assistant card directly below the email body."""
        current_tone = [ReplyTone.PROFESSIONAL.value]
        active_prompt = [""]

        tones = [
            (ReplyTone.PROFESSIONAL.value, "Professional", ft.Icons.BUSINESS_CENTER_OUTLINED),
            (ReplyTone.FRIENDLY.value, "Friendly", ft.Icons.SENTIMENT_SATISFIED_ALT),
            (ReplyTone.SHORT.value, "Concise", ft.Icons.SHORT_TEXT),
            (ReplyTone.DETAILED.value, "Detailed", ft.Icons.SUBJECT),
            (ReplyTone.FOLLOW_UP.value, "Follow-up", ft.Icons.UPDATE),
        ]

        prompt_presets = [
            "Confirm agreement & next steps",
            "Decline politely with thanks",
            "Request revised proposal / pricing",
            "Ask to schedule a 15-min sync",
        ]

        status_text = ft.Text(
            "Instant AI auto-reply ready \u2022 Select tone or prompt below",
            size=11,
            color=COLORS["text_muted"],
        )

        draft_field = ft.TextField(
            value="",
            multiline=True,
            min_lines=4,
            max_lines=9,
            border_color=COLORS["border"],
            focused_border_color=COLORS["primary"],
            bgcolor=COLORS["bg_card"],
            text_size=12,
            hint_text="AI auto-reply draft will appear here. You can edit directly...",
            content_padding=12,
        )

        save_draft_btn = ft.ElevatedButton(
            "Save as Draft",
            icon=ft.Icons.DRAFTS_OUTLINED,
            style=ft.ButtonStyle(
                bgcolor=COLORS["primary"],
                color="#FFFFFF",
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=padding_symmetric(horizontal=12, vertical=7),
            ),
        )

        copy_btn = ft.OutlinedButton(
            "Copy Text",
            icon=ft.Icons.COPY,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=padding_symmetric(horizontal=12, vertical=7),
                color=COLORS["text_primary"],
            ),
        )

        tone_pill_widgets = {}

        def update_tone_pills():
            for t_key, pill in tone_pill_widgets.items():
                is_active = (t_key == current_tone[0])
                pill.bgcolor = COLORS["badge_bg"] if is_active else "transparent"
                pill.border = border_all(1, COLORS["primary"] if is_active else COLORS["border"])
                row = pill.content
                row.controls[0].color = COLORS["primary"] if is_active else COLORS["text_muted"]
                row.controls[1].color = COLORS["primary"] if is_active else COLORS["text_secondary"]
                row.controls[1].weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500
                safe_update(pill)

        def run_generation(tone_name: str, custom_instruction: Optional[str] = None):
            current_tone[0] = tone_name
            if custom_instruction is not None:
                active_prompt[0] = custom_instruction
            update_tone_pills()

            status_text.value = f"Drafting {tone_name.replace('_', '-')} reply via AI..."
            status_text.color = COLORS["primary"]
            safe_update(status_text)

            def worker():
                try:
                    tone_val = ReplyTone(current_tone[0])
                    user_name = user_profile_manager.profile.name or "Alex"
                    reply, source = reply_generator.generate_reply_with_source(
                        sender_name=data.get("sender_name", ""),
                        sender_email=data.get("sender", ""),
                        subject=data.get("subject", ""),
                        original_body=data.get("body_plain", ""),
                        tone=tone_val,
                        user_name=user_name,
                        extra_instructions=active_prompt[0] if active_prompt[0] else None,
                    )
                    draft_field.value = reply
                    status_text.value = f"Draft ready \u2022 Source: {source.upper()}"
                    status_text.color = COLORS["success"]
                except Exception as ex:
                    status_text.value = f"Generation note: {ex}"
                    status_text.color = COLORS["warning"]
                safe_update(draft_field)
                safe_update(status_text)

            threading.Thread(target=worker, daemon=True).start()

        # Build tone pill controls
        tone_controls = []
        for key, label, icon in tones:
            is_active = (key == current_tone[0])
            pill = ft.Container(
                content=ft.Row([
                    ft.Icon(icon, size=12, color=COLORS["primary"] if is_active else COLORS["text_muted"]),
                    ft.Text(label, size=11, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500, color=COLORS["primary"] if is_active else COLORS["text_secondary"]),
                ], spacing=4, tight=True),
                bgcolor=COLORS["badge_bg"] if is_active else "transparent",
                border=border_all(1, COLORS["primary"] if is_active else COLORS["border"]),
                border_radius=100,
                padding=padding_symmetric(horizontal=8, vertical=4),
                ink=True,
                on_click=lambda e, k=key: run_generation(k),
            )
            tone_pill_widgets[key] = pill
            tone_controls.append(pill)

        # Build prompt chip controls
        prompt_controls = []
        for prompt_text in prompt_presets:
            p_chip = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=11, color=COLORS["warning"]),
                    ft.Text(prompt_text, size=10, color=COLORS["text_secondary"]),
                ], spacing=3, tight=True),
                bgcolor=COLORS["surface_alt"],
                border=border_all(1, COLORS["border"]),
                border_radius=100,
                padding=padding_symmetric(horizontal=8, vertical=3),
                ink=True,
                on_click=lambda e, pt=prompt_text: run_generation(current_tone[0], pt),
                tooltip=f"Draft with directive: {prompt_text}",
            )
            prompt_controls.append(p_chip)

        # Actions
        def on_copy(e):
            text = draft_field.value or ""
            if not text.strip():
                return
            try:
                self.page_ref.set_clipboard(text)
                copy_btn.text = "Copied!"
                copy_btn.icon = ft.Icons.CHECK
                copy_btn.style.color = COLORS["success"]
                safe_update(copy_btn)

                def revert():
                    import time
                    time.sleep(1.8)
                    copy_btn.text = "Copy Text"
                    copy_btn.icon = ft.Icons.COPY
                    copy_btn.style.color = COLORS["text_primary"]
                    safe_update(copy_btn)

                threading.Thread(target=revert, daemon=True).start()
            except Exception:
                pass

        def on_save_draft(e):
            text = draft_field.value or ""
            if not text.strip():
                status_text.value = "Draft is empty. Please enter text or click a tone."
                status_text.color = COLORS["warning"]
                safe_update(status_text)
                return

            save_draft_btn.disabled = True
            save_draft_btn.text = "Saving..."
            safe_update(save_draft_btn)

            def worker():
                try:
                    gmail_actions.create_draft(
                        recipient=data.get("sender", ""),
                        subject=data.get("subject", ""),
                        body_text=text,
                        thread_id=data.get("thread_id"),
                        message_id=data.get("message_id"),
                    )
                    status_text.value = "Draft successfully created in Gmail! (Audit logged)"
                    status_text.color = COLORS["success"]
                    try:
                        self.page_ref.show_dialog(
                            ft.SnackBar(ft.Text("Draft saved to Gmail!"), bgcolor=COLORS["success"])
                        )
                    except Exception:
                        pass
                except Exception as ex:
                    status_text.value = f"Failed to save draft: {ex}"
                    status_text.color = COLORS["danger"]
                finally:
                    save_draft_btn.disabled = False
                    save_draft_btn.text = "Save as Draft"
                    safe_update(save_draft_btn)
                    safe_update(status_text)

            threading.Thread(target=worker, daemon=True).start()

        copy_btn.on_click = on_copy
        save_draft_btn.on_click = on_save_draft

        # Automatically kick off initial generation so the draft is ready
        run_generation(current_tone[0])

        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.AUTO_AWESOME, size=14, color="#FFFFFF"),
                        bgcolor=COLORS["primary"],
                        padding=5,
                        border_radius=6,
                    ),
                    ft.Column([
                        ft.Text("Quick AI Auto-Reply Assistant", size=13, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        status_text,
                    ], spacing=2, expand=True),
                    ft.TextButton(
                        "Full Modal",
                        icon=ft.Icons.OPEN_IN_NEW,
                        icon_color=COLORS["primary"],
                        style=ft.ButtonStyle(color=COLORS["primary"]),
                        on_click=lambda e: self._open_reply_dialog(data),
                        tooltip="Open full dialog with direct sending and audit review",
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),

                ft.Divider(height=1, color=COLORS["border"]),

                # Tones
                ft.Row([
                    ft.Text("Tone:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"]),
                    ft.Row(tone_controls, spacing=6, wrap=True, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),

                # Prompt suggestions
                ft.Row([
                    ft.Text("Prompts:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_muted"]),
                    ft.Row(prompt_controls, spacing=6, wrap=True, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),

                # Draft text area
                draft_field,

                # Bottom actions row
                ft.Row([
                    save_draft_btn,
                    copy_btn,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=18,
                        icon_color=COLORS["text_secondary"],
                        tooltip="Regenerate Draft",
                        on_click=lambda e: run_generation(current_tone[0]),
                    ),
                    ft.Container(expand=True),
                    ft.Text("1-click safe draft \u2022 Human approval required before send", size=10, color=COLORS["text_muted"]),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            ], spacing=10),
            bgcolor=COLORS["surface_alt"],
            border=border_only(
                left=ft.BorderSide(3, COLORS["primary"]),
                top=ft.BorderSide(1, COLORS["border"]),
                right=ft.BorderSide(1, COLORS["border"]),
                bottom=ft.BorderSide(1, COLORS["border"]),
            ),
            border_radius=8,
            padding=14,
            margin=padding_symmetric(horizontal=16, vertical=6),
        )

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.page_ref.set_clipboard(text)
            self.page_ref.show_dialog(ft.SnackBar(ft.Text("Email body copied to clipboard!"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _open_reply_dialog(self, email_data: Dict[str, Any]) -> None:
        dialog = ReplyDialog(page=self.page_ref, email_data=email_data)
        try:
            self.page_ref.show_dialog(dialog)
        except Exception:
            pass

    def _archive_email(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.archive_message(
                email_data["message_id"],
                category=email_data.get("category", "PERSONAL"),
                sender=email_data.get("sender", ""),
                subject=email_data.get("subject", ""),
                user_approved=True,
            )
            event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)
            self.page_ref.show_dialog(ft.SnackBar(ft.Text("Email archived"), bgcolor=COLORS["success"]))
            self.load_emails()
        except Exception as e:
            try:
                self.page_ref.show_dialog(ft.SnackBar(ft.Text(f"Archive: {e}"), bgcolor=COLORS["warning"]))
            except Exception:
                pass

    def _trash_email(self, email_data: Dict[str, Any]) -> None:
        subject = email_data.get("subject") or "(No Subject)"
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Move email to trash?"),
            content=ft.Text(
                f'Confirm moving "{subject[:80]}" to Gmail Trash. '
                "This is the required second confirmation."
            ),
        )

        def cancel(e):
            self.page_ref.pop_dialog()

        def confirm(e):
            self.page_ref.pop_dialog()
            self._execute_trash(email_data)

        dialog.actions = [
            ft.TextButton("Cancel", on_click=cancel),
            ft.ElevatedButton(
                "Move to Trash",
                icon=ft.Icons.DELETE_OUTLINE,
                bgcolor=COLORS["danger"],
                color="#FFFFFF",
                on_click=confirm,
            ),
        ]
        self.page_ref.show_dialog(dialog)

    def _execute_trash(self, email_data: Dict[str, Any]) -> None:
        try:
            gmail_actions.trash_message(
                email_data["message_id"],
                category=email_data.get("category", "SPAM"),
                sender=email_data.get("sender", ""),
                subject=email_data.get("subject", ""),
                user_approved=True,
                double_confirmed=True,
            )
            event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)
            self.page_ref.show_dialog(ft.SnackBar(ft.Text("Email moved to trash"), bgcolor=COLORS["danger"]))
            self.load_emails()
        except Exception as e:
            self._show_action_error("Move to trash", e)

    def _show_action_error(self, action: str, error: Exception) -> None:
        try:
            self.page_ref.show_dialog(
                ft.SnackBar(ft.Text(f"{action} failed: {error}"), bgcolor=COLORS["danger"])
            )
        except Exception:
            pass
