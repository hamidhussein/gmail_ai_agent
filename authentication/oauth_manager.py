"""
GmailAI Assistant - Google OAuth 2.0 Manager
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import config_manager
from authentication.token_manager import token_manager
from authentication.credential_manager import credential_manager
from database.repository import repository
from core.exceptions import AuthenticationError

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

    def get_credentials(self, email: str) -> Optional[Credentials]:
        """Loads and refreshes OAuth credentials for a specific account email."""
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
        except Exception as e:
            logger.error(f"Error loading/refreshing credentials for {email}: {e}")
            return None

    def start_oauth_flow(self, credentials_path: Optional[str] = None) -> Optional[str]:
        """
        Launches local web browser for OAuth 2.0 authentication.
        Returns the authenticated user email on success.
        """
        client_config = credential_manager.get_client_config(credentials_path)
        if not client_config:
            raise AuthenticationError(
                "Google OAuth credentials.json not found. Please provide a valid credentials file in Settings."
            )

        try:
            flow = InstalledAppFlow.from_client_config(client_config, scopes=self.scopes)
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="Please complete Google login in your browser...",
                success_message="Authentication successful! You may close this tab.",
            )

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

            logger.info(f"Successfully authenticated account: {user_email}")
            return user_email
        except Exception as e:
            logger.error(f"OAuth authorization flow failed: {e}")
            raise AuthenticationError(f"OAuth flow failed: {e}")

    def logout(self, email: str) -> bool:
        """Deletes account credentials and sets active account to none or fallback."""
        success = token_manager.delete_token(email)
        accounts = repository.list_accounts()
        for acc in accounts:
            if acc.email == email:
                acc.is_active = False
                break
        return success


oauth_manager = OAuthManager()
