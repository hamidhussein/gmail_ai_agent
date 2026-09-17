"""
GmailAI Assistant - Background Task Scheduler
"""
import time
import json
import threading
import datetime
import logging
from dataclasses import dataclass
from typing import Optional, Callable

from app.config import config_manager
from core.events import (
    event_bus,
    EVT_SYNC_STARTED,
    EVT_SYNC_PROGRESS,
    EVT_SYNC_COMPLETED,
    EVT_SYNC_ERROR,
)
from database.repository import repository
from gmail.reader import GmailReader
from ai.router import hybrid_router
from memory.preference_engine import preference_engine
from automation.daily_digest import daily_digest_generator

logger = logging.getLogger("GmailAI.Scheduler")


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def should_create_cleanup_suggestion(action: str, confidence: float, threshold: float) -> bool:
    """Allow only supported cleanup actions that meet the configured confidence floor."""
    return action in {"ARCHIVE", "MOVE_TRASH"} and (confidence or 0.0) >= threshold


@dataclass(frozen=True)
class SyncResult:
    """Immutable summary of one synchronization attempt."""

    success: bool
    account_email: Optional[str] = None
    fetched: int = 0
    processed: int = 0
    refreshed: int = 0
    failed: int = 0
    skipped: bool = False
    error: Optional[str] = None

    @property
    def summary(self) -> str:
        if self.skipped:
            return self.error or "A sync is already in progress."
        if not self.success:
            return self.error or "Sync failed."
        details = f"{self.processed} analyzed, {self.refreshed} refreshed"
        if self.failed:
            details += f", {self.failed} failed"
        return f"Sync complete: {details}."


class BackgroundScheduler:
    """Threaded background scheduler for background email synchronization and AI processing."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_digest_date: Optional[str] = None
        self._is_syncing = False
        self._sync_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._last_result: Optional[SyncResult] = None

    @property
    def is_syncing(self) -> bool:
        return self._is_syncing

    @property
    def last_result(self) -> Optional[SyncResult]:
        with self._result_lock:
            return self._last_result

    def _store_result(self, result: SyncResult) -> None:
        with self._result_lock:
            self._last_result = result

    @staticmethod
    def _run_callback(callback: Optional[Callable[[], None]]) -> None:
        if not callback:
            return
        try:
            callback()
        except Exception as exc:
            logger.error(f"Error in on_complete callback: {exc}")

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

    def trigger_sync_now(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        """Convenience alias for run_sync_now_async()."""
        self.run_sync_now_async(on_complete=on_complete)

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

    def _execute_sync_task(self, on_complete: Optional[Callable[[], None]] = None) -> SyncResult:
        """Performs email fetch, hybrid AI analysis, and suggestion creation."""
        if not self._sync_lock.acquire(blocking=False):
            result = SyncResult(
                success=False,
                skipped=True,
                error="A sync is already in progress.",
            )
            self._store_result(result)
            logger.info(result.error)
            self._run_callback(on_complete)
            return result

        self._is_syncing = True
        result = SyncResult(success=False, error="Sync did not complete.")

        try:
            account = repository.get_active_account()
            if not account:
                result = SyncResult(success=False, error="No active Gmail account is connected.")
                event_bus.publish(EVT_SYNC_ERROR, result.error)
                return result

            account_email = account.email
            event_bus.publish(EVT_SYNC_STARTED, {"account_email": account_email})
            reader = GmailReader(email=account_email)
            max_emails = config_manager.config.max_emails_per_sync

            try:
                raw_emails = reader.fetch_and_parse_inbox(account_id=account.id, max_count=max_emails)
            except Exception as e:
                if config_manager.config.demo_mode:
                    logger.info(f"Demo mode sync skipped Gmail fetch ({e}).")
                    raw_emails = []
                else:
                    raise

            processed = 0
            refreshed = 0
            failed = 0
            total = len(raw_emails)

            for index, email_dict in enumerate(raw_emails, start=1):
                if self._stop_event.is_set():
                    logger.info("Sync interrupted during application shutdown.")
                    break

                message_id = email_dict.get("message_id", "unknown")
                try:
                    existing = repository.get_email_by_message_id(message_id)
                    already_classified = bool(
                        existing
                        and existing.account_id == account.id
                        and existing.category
                        and existing.ai_source
                    )

                    if already_classified:
                        # Gmail flags and message content can change even when the
                        # AI classification does not. Update only the fetched raw
                        # fields and preserve the existing intelligence columns.
                        repository.save_or_update_email(email_dict)
                        refreshed += 1
                    else:
                        classification, source = hybrid_router.classify_email(email_dict)
                        raw_importance = classification.get("importance_score", 50)
                        raw_category = classification.get("category", "PERSONAL")
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
                        email_dict["action_items_json"] = json.dumps(classification.get("action_items", []))

                        saved = repository.save_or_update_email(email_dict)
                        processed += 1

                        if should_create_cleanup_suggestion(
                            saved.suggested_action,
                            saved.ai_confidence,
                            config_manager.config.hybrid_confidence_threshold,
                        ):
                            repository.create_suggestion(
                                email_id=saved.id,
                                action_type=saved.suggested_action,
                                category=saved.category,
                                reason=saved.ai_reasoning,
                                confidence=saved.ai_confidence,
                            )
                except Exception as email_error:
                    failed += 1
                    logger.error(
                        f"Could not process Gmail message {message_id}: {email_error}",
                        exc_info=True,
                    )

                event_bus.publish(
                    EVT_SYNC_PROGRESS,
                    {
                        "account_email": account_email,
                        "current": index,
                        "total": total,
                        "processed": processed,
                        "refreshed": refreshed,
                        "failed": failed,
                    },
                )

            # Update last_synced_at via the repository (no detached-object access)
            repository.update_account_synced_at(account_email)

            result = SyncResult(
                success=True,
                account_email=account_email,
                fetched=total,
                processed=processed,
                refreshed=refreshed,
                failed=failed,
                error=f"{failed} message(s) could not be processed." if failed else None,
            )
            event_bus.publish(EVT_SYNC_COMPLETED, result)
            logger.info(result.summary)

        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            result = SyncResult(success=False, error=str(e))
            event_bus.publish(EVT_SYNC_ERROR, result.error)
        finally:
            self._store_result(result)
            self._is_syncing = False
            self._sync_lock.release()
            self._run_callback(on_complete)

        return result


scheduler = BackgroundScheduler()
