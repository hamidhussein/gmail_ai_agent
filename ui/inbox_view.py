"""
GmailAI Assistant - Polished Intelligence Inbox & Reader for Flet
"""
import re
import html
import json
import datetime
import flet as ft
from typing import Dict, Any, List, Optional
from resources.styles.theme import (
    COLORS,
    get_category_color,
    border_all,
    padding_all,
    padding_symmetric,
    safe_update,
    align_center,
)
from ui.components.reply_modal import ReplyDialog
from database.repository import repository
from gmail.actions import gmail_actions
from memory.learning import learning_engine
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
        self.detail_star_btn: Optional[ft.OutlinedButton] = None
        self.detail_read_btn: Optional[ft.OutlinedButton] = None

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
                        size=14,
                        color="#FFFFFF" if is_active else COLORS["text_secondary"],
                    ),
                    ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500,
                        color="#FFFFFF" if is_active else COLORS["text_secondary"],
                    ),
                ], spacing=6, tight=True),
                bgcolor=COLORS["primary"] if is_active else COLORS["bg_card"],
                border=border_all(1, COLORS["primary"] if is_active else COLORS["border"]),
                border_radius=20,
                padding=padding_symmetric(horizontal=12, vertical=6),
                on_click=lambda e, k=key: self._on_filter_click(k),
                animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            self.chip_controls.append((key, chip))

        self.filter_chips_row = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
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
            content=ft.Column([
                ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, size=56, color=COLORS["text_muted"]),
                ft.Text(
                    "Select an email to view full conversation and AI intelligence",
                    size=15,
                    color=COLORS["text_secondary"],
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
            bgcolor=COLORS["bg_card"],
            border=border_all(1, COLORS["border"]),
            border_radius=12,
            padding=20,
            expand=14,
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
                    # Email List (10 parts)
                    ft.Container(
                        content=self.email_list_column,
                        expand=10,
                    ),
                    # Email Detail Reader (14 parts)
                    self.detail_container,
                ], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
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
            chip.bgcolor = COLORS["primary"] if is_active else COLORS["bg_card"]
            chip.border = border_all(1, COLORS["primary"] if is_active else COLORS["border"])
            row = chip.content
            row.controls[0].color = "#FFFFFF" if is_active else COLORS["text_secondary"]
            row.controls[1].color = "#FFFFFF" if is_active else COLORS["text_secondary"]
            row.controls[1].weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.W_500
        safe_update(self.filter_chips_row)
        self.load_emails()

    def load_emails(self) -> None:
        """Loads emails from repository according to the active filter and search query."""
        self.email_list_column.controls.clear()
        self.card_refs.clear()
        self.unread_dot_refs.clear()
        self.subj_text_refs.clear()
        self.sender_text_refs.clear()
        self.star_btn_refs.clear()

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

        emails = repository.get_inbox_emails(
            category=category,
            is_unread=is_unread,
            is_starred=is_starred,
            search_query=self.search_query if self.search_query else None,
            limit=100,
        )
        self.emails_data = emails

        count = len(emails)
        if count == 0:
            self.count_badge.value = "0 emails"
            self.email_list_column.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.INBOX_OUTLINED, size=52, color=COLORS["text_muted"]),
                        ft.Text("No emails found", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                        ft.Text("Try selecting a different filter or clearing search.", size=12, color=COLORS["text_secondary"]),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    alignment=align_center(),
                    padding=40,
                )
            )
            # Empty reader state
            self.detail_container.content = ft.Column([
                ft.Icon(ft.Icons.MARK_EMAIL_READ_OUTLINED, size=56, color=COLORS["text_muted"]),
                ft.Text("No email selected", size=15, color=COLORS["text_secondary"]),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
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
                first_card.bgcolor = COLORS["badge_bg"]
                first_card.border = border_all(1, COLORS["primary"])
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

        card = ft.Container(
            content=ft.Row([
                # Left indicator & Avatar
                unread_dot,
                ft.Container(
                    content=ft.Text(initials, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor=avatar_bg,
                    width=32,
                    height=32,
                    border_radius=16,
                    alignment=align_center(),
                ),

                # Middle Text Area
                ft.Column([
                    ft.Row([
                        sender_text,
                        ft.Row([
                            attachment_icon,
                            ft.Text(date_str, size=11, color=COLORS["text_muted"]),
                        ], spacing=4, tight=True),
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

                # Right Badges Column & Star
                ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(cat, size=9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            bgcolor=cat_color,
                            padding=padding_symmetric(horizontal=6, vertical=2),
                            border_radius=4,
                        ),
                        star_btn,
                    ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                    ft.Text(
                        f"Score: {importance}",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["success"] if importance >= 75 else (COLORS["warning"] if importance >= 50 else COLORS["text_muted"]),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            bgcolor=COLORS["badge_bg"] if is_selected else COLORS["bg_card"],
            border=border_all(1, COLORS["primary"] if is_selected else COLORS["border"]),
            border_radius=10,
            padding=padding_symmetric(horizontal=12, vertical=10),
            on_click=lambda e, em=email: self._on_email_clicked(em),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        self.card_refs[email.id] = card
        return card

    def _on_email_clicked(self, email: Any):
        data = self._email_to_dict(email)
        prev_id = self.selected_email.get("id") if self.selected_email else None
        new_id = email.id

        # In-place style transition of previous card
        if prev_id and prev_id != new_id and prev_id in self.card_refs:
            prev_card = self.card_refs[prev_id]
            prev_card.bgcolor = COLORS["bg_card"]
            prev_card.border = border_all(1, COLORS["border"])
            safe_update(prev_card)

        # In-place style transition of active card
        if new_id in self.card_refs:
            active_card = self.card_refs[new_id]
            active_card.bgcolor = COLORS["badge_bg"]
            active_card.border = border_all(1, COLORS["primary"])
            safe_update(active_card)

        # Mark as read in repo & actions in-place
        if email.is_unread:
            repository.update_email_flags(email.message_id, is_unread=False)
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

            # Inform other views to update badge counts
            event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)

        self.selected_email = data
        self._render_email_detail(data)

    def _toggle_star_from_card(self, email: Any):
        new_starred = not getattr(email, "is_starred", False)
        email.is_starred = new_starred
        repository.update_email_flags(email.message_id, is_starred=new_starred)

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
                self.detail_star_btn.text = "Starred" if new_starred else "Star"
                self.detail_star_btn.style.color = COLORS["warning"] if new_starred else COLORS["text_secondary"]
                safe_update(self.detail_star_btn)

        msg = "Email starred" if new_starred else "Email unstarred"
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["warning"] if new_starred else COLORS["text_secondary"]))
        except Exception:
            pass

    def _toggle_star_from_detail(self, data: Dict[str, Any]):
        new_starred = not data.get("is_starred", False)
        data["is_starred"] = new_starred
        repository.update_email_flags(data["message_id"], is_starred=new_starred)

        email_id = data.get("id")
        if email_id and email_id in self.star_btn_refs:
            btn = self.star_btn_refs[email_id]
            btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
            btn.icon_color = COLORS["warning"] if new_starred else COLORS["text_muted"]
            btn.tooltip = "Unstar email" if new_starred else "Star email"
            safe_update(btn)

        if self.detail_star_btn:
            self.detail_star_btn.icon = ft.Icons.STAR if new_starred else ft.Icons.STAR_BORDER
            self.detail_star_btn.text = "Starred" if new_starred else "Star"
            self.detail_star_btn.style.color = COLORS["warning"] if new_starred else COLORS["text_secondary"]
            safe_update(self.detail_star_btn)

        msg = "Email starred" if new_starred else "Email unstarred"
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["warning"] if new_starred else COLORS["text_secondary"]))
        except Exception:
            pass

    def _toggle_read_status(self, data: Dict[str, Any]):
        new_unread = not data.get("is_unread", False)
        data["is_unread"] = new_unread
        repository.update_email_flags(data["message_id"], is_unread=new_unread)

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
            self.detail_read_btn.text = "Mark as Read" if new_unread else "Mark as Unread"
            safe_update(self.detail_read_btn)

        event_bus.publish(EVT_SUGGESTION_ACTIONED, 1)
        msg = "Marked as unread" if new_unread else "Marked as read"
        try:
            self.page_ref.open(ft.SnackBar(ft.Text(msg), bgcolor=COLORS["primary"]))
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

        # Detail Star Button
        self.detail_star_btn = ft.OutlinedButton(
            "Starred" if is_starred else "Star",
            icon=ft.Icons.STAR if is_starred else ft.Icons.STAR_BORDER,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                color=COLORS["warning"] if is_starred else COLORS["text_secondary"],
            ),
            on_click=lambda e: self._toggle_star_from_detail(data),
        )

        # Detail Read/Unread Button
        self.detail_read_btn = ft.OutlinedButton(
            "Mark as Read" if is_unread else "Mark as Unread",
            icon=ft.Icons.MARK_EMAIL_READ_OUTLINED if is_unread else ft.Icons.MARK_EMAIL_UNREAD_OUTLINED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=lambda e: self._toggle_read_status(data),
        )

        self.detail_container.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                # Top Action Bar
                ft.Row([
                    ft.ElevatedButton(
                        "AI Reply Assistant",
                        icon=ft.Icons.AUTO_AWESOME,
                        bgcolor=COLORS["primary"],
                        color="#FFFFFF",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._open_reply_dialog(data),
                    ),
                    self.detail_star_btn,
                    self.detail_read_btn,
                    ft.OutlinedButton(
                        "Archive",
                        icon=ft.Icons.ARCHIVE_OUTLINED,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda e: self._archive_email(data),
                    ),
                    ft.OutlinedButton(
                        "Trash",
                        icon=ft.Icons.DELETE_OUTLINE,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), color=COLORS["danger"]),
                        on_click=lambda e: self._trash_email(data),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY,
                        tooltip="Copy body to clipboard",
                        icon_color=COLORS["text_secondary"],
                        on_click=lambda e: self._copy_to_clipboard(body_content),
                    ),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),

                # Subject Line
                ft.Text(data.get("subject") or "(No Subject)", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),

                # Sender & Recipient Information Card
                ft.Container(
                    content=ft.Row([
                        # Avatar
                        ft.Container(
                            content=ft.Text(initials, size=15, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            bgcolor=avatar_bg,
                            width=44,
                            height=44,
                            border_radius=22,
                            alignment=align_center(),
                        ),

                        # Sender Info
                        ft.Column([
                            ft.Row([
                                ft.Text(sender_name, size=14, weight=ft.FontWeight.BOLD, color=COLORS["text_primary"]),
                                ft.Text(f"<{sender_email}>", size=12, color=COLORS["text_muted"]),
                            ], spacing=6, wrap=True),
                            ft.Row([
                                ft.Text(f"To: {recipient}", size=12, color=COLORS["text_secondary"]),
                                ft.Text("•", color=COLORS["text_muted"], size=12),
                                ft.Text(date_full, size=12, color=COLORS["text_secondary"]),
                            ], spacing=6),
                        ], expand=True, spacing=3),

                        # Category & Score Badges
                        ft.Column([
                            ft.Container(
                                content=ft.Text(cat, size=10, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                bgcolor=cat_color,
                                padding=padding_symmetric(horizontal=8, vertical=3),
                                border_radius=4,
                            ),
                            ft.Text(
                                f"Score: {importance}/100",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=COLORS["success"] if importance >= 75 else (COLORS["warning"] if importance >= 50 else COLORS["text_muted"]),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4),
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                    bgcolor=COLORS["bg_card"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                    padding=14,
                ),

                # AI Intelligence Insights Card
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color=COLORS["badge_text"]),
                            ft.Text("AI Intelligence & Insights", size=13, weight=ft.FontWeight.BOLD, color=COLORS["badge_text"]),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Text(f"Action: {action}", size=10, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                                bgcolor=COLORS["bg_card"],
                                border=border_all(1, COLORS["primary"]),
                                padding=padding_symmetric(horizontal=8, vertical=2),
                                border_radius=6,
                            ),
                        ]),
                        ft.Divider(height=1, color=COLORS["border"]),
                        ft.Text(reasoning, size=12, color=COLORS["text_primary"]),
                        ft.Row([
                            ft.Text(f"⚡ Urgency: {urgency}/100", size=11, color=COLORS["text_secondary"], weight=ft.FontWeight.W_500),
                            ft.Text("•", color=COLORS["text_muted"]),
                            ft.Text(f"🛡️ Safety: {data.get('risk_level', 'LOW')}", size=11, color=COLORS["success"] if data.get("risk_level") == "LOW" else COLORS["danger"], weight=ft.FontWeight.W_500),
                        ], spacing=8),
                        ft.Column([
                            ft.Text("Action Items Detected:", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                            ft.Column(action_chips, spacing=6),
                        ], visible=len(action_chips) > 0, spacing=6),
                    ], spacing=10),
                    bgcolor=COLORS["badge_bg"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                    padding=16,
                ),

                # Email Body Reader Container
                ft.Container(
                    content=ft.Markdown(
                        body_content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    ),
                    padding=20,
                    bgcolor=COLORS["bg_card"],
                    border=border_all(1, COLORS["border"]),
                    border_radius=10,
                ),
            ],
        )
        safe_update(self.detail_container)

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.page_ref.set_clipboard(text)
            self.page_ref.open(ft.SnackBar(ft.Text("Email body copied to clipboard!"), bgcolor=COLORS["success"]))
        except Exception:
            pass

    def _open_reply_dialog(self, email_data: Dict[str, Any]) -> None:
        dialog = ReplyDialog(page=self.page_ref, email_data=email_data)
        try:
            self.page_ref.open(dialog)
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
            self.page_ref.open(ft.SnackBar(ft.Text("Email archived"), bgcolor=COLORS["success"]))
            self.load_emails()
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Archive: {e}"), bgcolor=COLORS["warning"]))
            except Exception:
                pass

    def _trash_email(self, email_data: Dict[str, Any]) -> None:
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
            self.page_ref.open(ft.SnackBar(ft.Text("Email moved to trash"), bgcolor=COLORS["danger"]))
            self.load_emails()
        except Exception as e:
            try:
                self.page_ref.open(ft.SnackBar(ft.Text(f"Trash: {e}"), bgcolor=COLORS["warning"]))
            except Exception:
                pass
