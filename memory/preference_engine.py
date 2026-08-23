"""
GmailAI Assistant - Preference Engine & Sender Scoring
"""
import logging
from typing import Dict, Any, Optional

from database.repository import repository
from database.models import SenderProfile
from memory.user_profile import user_profile_manager

logger = logging.getLogger("GmailAI.PreferenceEngine")


class PreferenceEngine:
    """Calculates learned importance weights and overrides based on user behavioral history."""

    @staticmethod
    def adjust_email_importance(
        sender_email: str,
        initial_importance: int,
        initial_category: str,
        repo=None,
    ) -> tuple[int, str]:
        """
        Adjusts raw AI importance score and category based on learned user behavior:
        - If sender is VIP, boost importance to at least 90
        - If sender domain is in user's VIP domains, boost importance
        - If sender has high historical open/reply rate, adjust score upwards
        - If user previously set a category override for this sender, apply it
        """
        from database import repository as repo_module
        active_repo = repo or repo_module.repository

        clean_sender = sender_email.strip().lower()
        domain = clean_sender.split("@")[-1] if "@" in clean_sender else ""

        profile = active_repo.get_or_create_sender_profile(clean_sender)
        category = profile.override_category or initial_category
        importance = initial_importance

        # Check User Profile VIP Domains
        if domain in user_profile_manager.profile.vip_domains or profile.is_vip:
            importance = max(importance, 92)
            logger.debug(f"Boosted importance for VIP sender/domain: {clean_sender} ({importance})")
            return importance, category

        # Use learned sender importance
        if (profile.total_received or 0) >= 3:
            learned = profile.learned_importance or 50
            importance = int((importance * 0.6) + (learned * 0.4))

        return importance, category


preference_engine = PreferenceEngine()
