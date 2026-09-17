"""
GmailAI Assistant - Gmail API Service Client & Factory
"""
import time
import random
import logging
from typing import Optional, Any
from google.auth.exceptions import TransportError
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from authentication.oauth_manager import oauth_manager
from app.config import config_manager
from core.exceptions import GmailAPIError

logger = logging.getLogger("GmailAI.Client")


class GmailClientFactory:
    """Creates authenticated Gmail API Resource instances with retry policies."""

    @classmethod
    def get_service(cls, email: Optional[str] = None) -> Optional[Resource]:
        """Builds a Gmail API Resource service for the requested or active account."""
        if not email:
            from database.repository import repository
            acc = repository.get_active_account()
            if not acc:
                logger.warning("No active account found for Gmail API client.")
                return None
            email = acc.email

        creds = oauth_manager.get_credentials(email)
        if not creds:
            logger.warning(f"No valid credentials found for account {email}")
            return None

        try:
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            return service
        except Exception as e:
            logger.error(f"Failed to build Gmail service for {email}: {e}")
            raise GmailAPIError(f"Could not connect to Gmail API: {e}")

    @classmethod
    def execute_with_retry(cls, request: Any, max_retries: int = 4) -> Any:
        """Execute a Gmail request with bounded exponential backoff and jitter."""
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        attempts = max(1, max_retries)
        delay = 1.0

        for attempt in range(attempts):
            try:
                return request.execute()
            except HttpError as err:
                status_code = getattr(err.resp, "status", None)
                if status_code not in retryable_statuses or attempt >= attempts - 1:
                    logger.error(f"Gmail API HttpError: {err}")
                    raise GmailAPIError(f"Gmail API Error: {err}") from err

                retry_after = None
                try:
                    retry_after = float(err.resp.get("retry-after"))
                except (TypeError, ValueError, AttributeError):
                    pass
                sleep_for = min(60.0, retry_after if retry_after is not None else delay)
                sleep_for += random.uniform(0.0, min(1.0, sleep_for * 0.25))
                logger.warning(
                    f"Gmail API HTTP {status_code}; retry {attempt + 1}/{attempts - 1} "
                    f"in {sleep_for:.1f}s."
                )
                time.sleep(sleep_for)
                delay = min(30.0, delay * 2)
            except (TransportError, TimeoutError, ConnectionError, OSError) as err:
                if attempt >= attempts - 1:
                    logger.error(f"Gmail transport failed after {attempts} attempts: {err}")
                    raise GmailAPIError(f"Gmail request failed: {err}") from err
                sleep_for = delay + random.uniform(0.0, min(1.0, delay * 0.25))
                logger.warning(
                    f"Transient Gmail transport error; retry {attempt + 1}/{attempts - 1} "
                    f"in {sleep_for:.1f}s: {err}"
                )
                time.sleep(sleep_for)
                delay = min(30.0, delay * 2)
            except Exception as err:
                logger.error(f"Unexpected error executing Gmail API request: {err}")
                raise GmailAPIError(f"Gmail request failed: {err}") from err

        raise GmailAPIError("Gmail request failed after exhausting retries.")
