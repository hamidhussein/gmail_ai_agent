"""
GmailAI Assistant - Google OAuth 2.0 Manager

Manages the full lifecycle of Google OAuth 2.0 authentication:
  - Browser-based OAuth flow with account selection
  - Credential refresh and revocation handling
  - Multi-account switching and disconnection
  - Async wrappers for non-blocking UI integration
"""
import os
import json
import logging
import threading
from typing import Optional, Dict, Any, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import config_manager
from authentication.token_manager import token_manager
from authentication.credential_manager import credential_manager
from database.repository import repository
from core.exceptions import AuthenticationError
from core.events import event_bus, EVT_ACCOUNT_CHANGED, EVT_AUTH_REQUIRED

logger = logging.getLogger("GmailAI.OAuthManager")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


class OAuthManager:
    """Manages Google OAuth 2.0 flow, token refreshing, and account authentication."""

    def __init__(self):
        self.scopes = GMAIL_SCOPES
        self._invalid_accounts = set()
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Token validation / refresh
    # ------------------------------------------------------------------
    def _mark_reauthentication_required(self, email: str, reason: str) -> None:
        """Remove an unusable token and notify the UI once per account."""
        with self._state_lock:
            first_notice = email not in self._invalid_accounts
            self._invalid_accounts.add(email)

        token_manager.delete_token(email)
        repository.deactivate_account(email)
        if first_notice:
            event_bus.publish(EVT_AUTH_REQUIRED, {"email": email, "reason": reason})

    def get_credentials(self, email: str) -> Optional[Credentials]:
        """Loads and refreshes OAuth credentials for a specific account email."""
        with self._state_lock:
            if email in self._invalid_accounts:
                return None

        token_data = token_manager.load_token(email)
        if not token_data:
            return None

        try:
            creds = Credentials.from_authorized_user_info(token_data, self.scopes)
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Refreshing expired token for {email}...")
                creds.refresh(Request())
                # Persist refreshed token
                token_manager.save_token(email, json.loads(creds.to_json()))
            return creds
        except RefreshError as e:
            error_text = str(e)
            if "invalid_grant" in error_text.lower():
                logger.warning("Google authorization expired or was revoked for %s.", email)
                self._mark_reauthentication_required(
                    email,
                    "Your Google authorization expired or was revoked. Sign in again to reconnect Gmail.",
                )
            else:
                logger.error(f"Error refreshing credentials for {email}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading/refreshing credentials for {email}: {e}")
            return None

    # ------------------------------------------------------------------
    # OAuth flow
    # ------------------------------------------------------------------
    def start_oauth_flow(
        self,
        credentials_path: Optional[str] = None,
        login_hint: Optional[str] = None,
    ) -> Optional[str]:
        """
        Launches local web browser for OAuth 2.0 authentication.
        Uses prompt="select_account" so Google always allows picking
        or adding a different account.
        Returns the authenticated user email on success.
        """
        client_config = credential_manager.get_client_config(credentials_path)
        if not client_config:
            raise AuthenticationError(
                "Google OAuth credentials not found. Please check Settings."
            )

        try:
            flow = InstalledAppFlow.from_client_config(client_config, scopes=self.scopes)
            auth_options = dict(
                port=0,
                prompt="select_account",
                authorization_prompt_message="Please complete Google login in your browser...",
                success_message="Authentication successful! You may close this tab.",
            )
            if login_hint:
                auth_options["login_hint"] = login_hint
            creds = flow.run_local_server(**auth_options)

            # Retrieve user info
            userinfo_service = build("oauth2", "v2", credentials=creds)
            user_info = userinfo_service.userinfo().get().execute()
            user_email = user_info.get("email")
            display_name = user_info.get("name", user_email)

            if not user_email:
                raise AuthenticationError("Could not retrieve email from Google OAuth response.")

            # Save encrypted token
            token_dict = json.loads(creds.to_json())
            token_manager.save_token(user_email, token_dict)

            # Save account in DB
            repository.get_or_create_account(email=user_email, display_name=display_name)
            repository.set_active_account(user_email)
            with self._state_lock:
                self._invalid_accounts.discard(user_email)

            logger.info(f"Successfully authenticated account: {user_email}")
            return user_email
        except Exception as e:
            error_text = str(e)
            logger.error(f"OAuth authorization flow failed: {e}")
            if "access_denied" in error_text.lower():
                raise AuthenticationError(
                    "Google denied access. Add this account under Google Auth Platform "
                    "→ Audience → Test users, or sign in with an approved test account."
                ) from e
            raise AuthenticationError(f"OAuth flow failed: {e}") from e

    # ------------------------------------------------------------------
    # Account switching
    # ------------------------------------------------------------------
    def switch_active_account(self, email: str) -> bool:
        """Switches the active account to an already-authenticated email.

        Verifies the token is still valid, sets the account as active,
        and publishes EVT_ACCOUNT_CHANGED.  Returns True on success.
        """
        # Check if the account exists in the DB
        account = repository.get_account_by_email(email)
        if not account:
            logger.warning(f"Cannot switch — account {email} not found in database.")
            return False

        # Check token is present (and attempt a refresh if needed)
        creds = self.get_credentials(email)
        if not creds or not creds.valid:
            logger.warning(f"Cannot switch — token for {email} is invalid or missing.")
            return False

        repository.set_active_account(email)
        with self._state_lock:
            self._invalid_accounts.discard(email)

        logger.info(f"Switched active account to {email}")
        event_bus.publish(EVT_ACCOUNT_CHANGED, email)
        return True

    # ------------------------------------------------------------------
    # Account disconnection
    # ------------------------------------------------------------------
    def disconnect_account(self, email: str) -> bool:
        """Disconnects a single account: deletes token, deactivates in DB.

        If the disconnected account was active, promotes the next available
        authenticated account automatically.  Returns True if successful.
        """
        was_active = False
        current = repository.get_active_account()
        if current and current.email == email:
            was_active = True

        token_deleted = token_manager.delete_token(email)
        account_deactivated = repository.deactivate_account(email)
        with self._state_lock:
            self._invalid_accounts.discard(email)

        # Auto-promote another authenticated account if the active one was removed
        if was_active:
            promoted = self._promote_next_account()
            if promoted:
                event_bus.publish(EVT_ACCOUNT_CHANGED, promoted)

        return token_deleted or account_deactivated

    def _promote_next_account(self) -> Optional[str]:
        """Finds and activates the next account that has a valid token on disk."""
        accounts = repository.list_accounts()
        for acc in accounts:
            if token_manager.load_token(acc.email):
                repository.set_active_account(acc.email)
                logger.info(f"Auto-promoted account {acc.email} to active.")
                return acc.email
        return None

    def logout(self, email: str) -> bool:
        """Deletes account credentials and persists account deactivation."""
        token_deleted = token_manager.delete_token(email)
        account_deactivated = repository.deactivate_account(email)
        with self._state_lock:
            self._invalid_accounts.discard(email)
        return token_deleted or account_deactivated

    # ------------------------------------------------------------------
    # Multi-account listing
    # ------------------------------------------------------------------
    def list_authenticated_accounts(self) -> List[Dict[str, Any]]:
        """Returns a list of all accounts that have valid local tokens.

        Each entry: {"email": str, "display_name": str, "is_active": bool,
                      "last_synced_at": datetime|None, "has_valid_token": bool}
        """
        accounts = repository.list_accounts()
        result = []
        for acc in accounts:
            has_token = token_manager.load_token(acc.email) is not None
            result.append({
                "email": acc.email,
                "display_name": acc.display_name or acc.email,
                "is_active": acc.is_active,
                "last_synced_at": acc.last_synced_at,
                "has_valid_token": has_token,
            })
        return result

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------
    def start_oauth_flow_async(
        self,
        on_success=None,
        on_error=None,
        credentials_path: Optional[str] = None,
        login_hint: Optional[str] = None,
    ) -> None:
        """Runs the OAuth authorization flow in a background thread to prevent UI freezing."""
        def _worker():
            try:
                email = self.start_oauth_flow(credentials_path, login_hint=login_hint)
                if email:
                    event_bus.publish(EVT_ACCOUNT_CHANGED, email)
                    if on_success:
                        on_success(email)
            except Exception as e:
                logger.error(f"Async OAuth failed: {e}")
                if on_error:
                    on_error(str(e))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def start_auth_flow(self, credentials_path: Optional[str] = None) -> Optional[str]:
        """Alias for start_oauth_flow for backward compatibility."""
        return self.start_oauth_flow(credentials_path)


oauth_manager = OAuthManager()
