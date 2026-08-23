"""
GmailAI Assistant - Gmail API Service Client & Factory
"""
import time
import logging
from typing import Optional, Any
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
    def execute_with_retry(cls, request: Any, max_retries: int = 3) -> Any:
        """Executes a Google API request with exponential backoff on rate limits."""
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return request.execute()
            except HttpError as err:
                status_code = err.resp.status
                if status_code in [429, 500, 503] and attempt < max_retries - 1:
                    logger.warning(f"Gmail API HTTP {status_code}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Gmail API HttpError: {err}")
                    raise GmailAPIError(f"Gmail API Error: {err}")
            except Exception as e:
                logger.error(f"Unexpected error executing Gmail API request: {e}")
                raise GmailAPIError(f"Gmail request failed: {e}")
