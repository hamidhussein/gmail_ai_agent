"""OAuth recovery and reconnect regression tests."""
import json
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from authentication.oauth_manager import OAuthManager
from core.events import EVT_AUTH_REQUIRED


def test_revoked_token_is_invalidated_and_not_retried():
    manager = OAuthManager()
    credentials = MagicMock(expired=True, refresh_token="refresh-token")
    credentials.refresh.side_effect = RefreshError("invalid_grant: Token has been expired or revoked.")

    with (
        patch("authentication.oauth_manager.token_manager.load_token", return_value={"token": "old"}) as load_token,
        patch("authentication.oauth_manager.Credentials.from_authorized_user_info", return_value=credentials),
        patch("authentication.oauth_manager.token_manager.delete_token") as delete_token,
        patch("authentication.oauth_manager.repository.deactivate_account") as deactivate,
        patch("authentication.oauth_manager.event_bus.publish") as publish,
    ):
        assert manager.get_credentials("user@example.com") is None
        assert manager.get_credentials("user@example.com") is None

    load_token.assert_called_once_with("user@example.com")
    delete_token.assert_called_once_with("user@example.com")
    deactivate.assert_called_once_with("user@example.com")
    publish.assert_called_once()
    assert publish.call_args.args[0] == EVT_AUTH_REQUIRED
    assert publish.call_args.args[1]["email"] == "user@example.com"


def test_reconnect_uses_account_hint_and_reactivates_account():
    manager = OAuthManager()
    manager._invalid_accounts.add("user@example.com")
    credentials = MagicMock()
    credentials.to_json.return_value = json.dumps({"token": "new-token"})
    flow = MagicMock()
    flow.run_local_server.return_value = credentials
    userinfo = MagicMock()
    userinfo.userinfo.return_value.get.return_value.execute.return_value = {
        "email": "user@example.com",
        "name": "Test User",
    }

    with (
        patch("authentication.oauth_manager.credential_manager.get_client_config", return_value={"installed": {}}),
        patch("authentication.oauth_manager.InstalledAppFlow.from_client_config", return_value=flow),
        patch("authentication.oauth_manager.build", return_value=userinfo),
        patch("authentication.oauth_manager.token_manager.save_token") as save_token,
        patch("authentication.oauth_manager.repository.get_or_create_account"),
        patch("authentication.oauth_manager.repository.set_active_account") as set_active,
    ):
        result = manager.start_oauth_flow(login_hint="user@example.com")

    assert result == "user@example.com"
    assert flow.run_local_server.call_args.kwargs["login_hint"] == "user@example.com"
    save_token.assert_called_once()
    set_active.assert_called_once_with("user@example.com")
    assert "user@example.com" not in manager._invalid_accounts
