"""
GmailAI Assistant - Background Task Scheduler
"""
import time
import threading
import datetime
import logging
from typing import Optional, Callable

from app.config import config_manager
from core.events import event_bus, EVT_SYNC_STARTED, EVT_SYNC_COMPLETED, EVT_SYNC_ERROR
from database.repository import repository
from gmail.reader import GmailReader
from ai.router import hybrid_router
from memory.preference_engine import preference_engine
from automation.daily_digest import daily_digest_generator

logger = logging.getLogger("GmailAI.Scheduler")


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class BackgroundScheduler:
    """Threaded background scheduler for background email synchronization and AI processing."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_digest_date: Optional[str] = None
        self._is_syncing = False

    def start(self) -> None:
        """Starts background scheduler thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="GmailAISchedulerThread", daemon=True)
        self._thread.start()
        logger.info("Background scheduler started.")

    def stop(self) -> None:
        """Stops background scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            logger.info("Background scheduler stopped.")

    def run_sync_now_async(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        """Triggers an immediate asynchronous synchronization in a worker thread."""
        threading.Thread(target=self._execute_sync_task, args=(on_complete,), daemon=True).start()

    def _run_loop(self) -> None:
        """Main periodic loop."""
        while not self._stop_event.is_set():
            cfg = config_manager.config
            if cfg.auto_sync_enabled:
                self._execute_sync_task()

            # Check daily digest
            if cfg.daily_digest_enabled:
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                if self._last_digest_date != today_str:
                    try:
                        daily_digest_generator.generate_digest_for_today()
                        self._last_digest_date = today_str
                    except Exception as e:
                        logger.error(f"Error auto-generating daily digest: {e}")

            # Sleep in small increments for responsive shutdown
            interval_sec = max(60, cfg.auto_sync_interval_minutes * 60)
            for _ in range(int(interval_sec / 2)):
                if self._stop_event.is_set():
                    break
                time.sleep(2)

    def _execute_sync_task(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        """Performs email fetch, hybrid AI analysis, and suggestion creation."""
        if self._is_syncing:
            logger.debug("Sync already in progress, skipping.")
            return

        self._is_syncing = True
        event_bus.publish(EVT_SYNC_STARTED)

        try:
            account = repository.get_active_account()
            if not account:
                logger.debug("No active account for sync.")
                return

            account_email = account.email
            reader = GmailReader(email=account_email)
            max_emails = config_manager.config.max_emails_per_sync

            try:
                raw_emails = reader.fetch_and_parse_inbox(account_id=account.id, max_count=max_emails)
            except Exception as e:
                logger.warning(f"Could not fetch live Gmail emails ({e}). Running in offline/demo mode.")
                raw_emails = []

            for email_dict in raw_emails:
                # Run through Hybrid AI Router (output is already validated)
                classification, source = hybrid_router.classify_email(email_dict)

                raw_importance = classification.get("importance_score", 50)
                raw_category = classification.get("category", "PERSONAL")

                # Apply learned preferences & VIP adjustments
                final_importance, final_category = preference_engine.adjust_email_importance(
                    sender_email=email_dict["sender"],
                    initial_importance=raw_importance,
                    initial_category=raw_category,
                )

                email_dict["category"] = final_category
                email_dict["importance_score"] = final_importance
                email_dict["urgency_score"] = classification.get("urgency_score", 50)
                email_dict["risk_level"] = classification.get("risk_level", "LOW")
                email_dict["ai_source"] = source.value
                email_dict["ai_confidence"] = classification.get("confidence", 0.8)
                email_dict["ai_reasoning"] = classification.get("reasoning", "")
                email_dict["suggested_action"] = classification.get("suggested_action", "KEEP")
                email_dict["action_items_json"] = str(classification.get("action_items", []))

                # Save email to DB
                saved = repository.save_or_update_email(email_dict)

                # If cleanup suggested, create suggestion record
                if saved.suggested_action in ["ARCHIVE", "MOVE_TRASH", "LABEL"]:
                    repository.create_suggestion(
                        email_id=saved.id,
                        action_type=saved.suggested_action,
                        category=saved.category,
                        reason=saved.ai_reasoning,
                        confidence=saved.ai_confidence,
                    )

            # Update last_synced_at via the repository (no detached-object access)
            repository.update_account_synced_at(account_email)

            event_bus.publish(EVT_SYNC_COMPLETED, len(raw_emails))
            logger.info(f"Sync complete. Processed {len(raw_emails)} emails.")

        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            event_bus.publish(EVT_SYNC_ERROR, str(e))
        finally:
            self._is_syncing = False
            if on_complete:
                try:
                    on_complete()
                except Exception as e:
                    logger.error(f"Error in on_complete callback: {e}")


scheduler = BackgroundScheduler()
