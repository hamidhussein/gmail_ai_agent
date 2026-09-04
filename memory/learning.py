"""
GmailAI Assistant - Active User Learning & Feedback Loop
"""
import logging
from typing import Optional

from database.repository import repository
from app.constants import EmailCategory

logger = logging.getLogger("GmailAI.Learning")


class ActiveLearningEngine:
    """Updates internal memory models based on user approval, rejection, and manual correction."""

    @staticmethod
    def on_user_categorization_override(sender_email: str, new_category: str) -> None:
        """Called when user manually overrides the AI-assigned category."""
        repository.record_sender_interaction(
            email=sender_email,
            override_category=new_category,
        )
        logger.info(f"Learned category override for {sender_email} -> {new_category}")

    @staticmethod
    def on_user_suggestion_decision(sender_email: str, was_approved: bool) -> None:
        """
        Called when a user approves or rejects an AI cleanup suggestion.

        Uses repository.update_sender_importance() to atomically update the
        sender's importance score within a properly managed session — avoids
        the detached-object bug of the previous implementation.
        """
        if was_approved:
            # If user regularly approves archiving/deleting from this sender, reduce learned importance
            delta = -5
        else:
            # If user rejected cleanup, increase sender importance to protect future emails
            delta = +15

        repository.update_sender_importance(sender_email, delta)
        logger.info(f"Updated sender importance for {sender_email} (delta: {delta:+d})")

    @staticmethod
    def on_user_email_opened(sender_email: str) -> None:
        """Tracks when a user opens an email."""
        repository.record_sender_interaction(email=sender_email, opened=True)

    @staticmethod
    def on_user_email_replied(sender_email: str) -> None:
        """Tracks when a user replies to an email."""
        repository.record_sender_interaction(email=sender_email, replied=True)

    # ------------------------------------------------------------------
    # Convenience aliases used by the UI layer
    # ------------------------------------------------------------------
    @staticmethod
    def record_read(sender_email: str) -> None:
        """Alias for on_user_email_opened(): called when the user opens an email."""
        ActiveLearningEngine.on_user_email_opened(sender_email)

    @staticmethod
    def on_user_approved_action(sender_email: str, action_type: str = "") -> None:
        """
        Called when the user approves an AI cleanup suggestion (archive/trash/etc.).

        Records the approval as positive feedback via on_user_suggestion_decision().
        The action_type is accepted for call-site compatibility and logging context.
        """
        logger.info(f"User approved '{action_type or 'cleanup'}' action for {sender_email}")
        ActiveLearningEngine.on_user_suggestion_decision(sender_email, was_approved=True)


learning_engine = ActiveLearningEngine()
