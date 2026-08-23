"""
GmailAI Assistant - Thread-safe Event Dispatcher
"""
import logging
import threading
from typing import Any, Callable, Dict, List

logger = logging.getLogger("GmailAI.Events")


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
                cls._instance._sub_lock = threading.Lock()
            return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Register a callback handler for an event type."""
        with self._sub_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Remove a callback handler."""
        with self._sub_lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, event_type: str, data: Any = None) -> None:
        """Publish an event to all registered subscribers."""
        handlers = []
        with self._sub_lock:
            if event_type in self._subscribers:
                handlers = list(self._subscribers[event_type])

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for '{event_type}': {e}", exc_info=True)


# Event name constants
EVT_SYNC_STARTED = "sync:started"
EVT_SYNC_PROGRESS = "sync:progress"
EVT_SYNC_COMPLETED = "sync:completed"
EVT_SYNC_ERROR = "sync:error"

EVT_AI_ANALYSIS_STARTED = "ai:analysis:started"
EVT_AI_ANALYSIS_PROGRESS = "ai:analysis:progress"
EVT_AI_ANALYSIS_COMPLETED = "ai:analysis:completed"

EVT_SUGGESTION_CREATED = "suggestion:created"
EVT_SUGGESTION_ACTIONED = "suggestion:actioned"

EVT_ACCOUNT_CHANGED = "account:changed"
EVT_SETTINGS_CHANGED = "settings:changed"
EVT_THEME_CHANGED = "theme:changed"
EVT_TOAST_MESSAGE = "ui:toast"

event_bus = EventBus()

