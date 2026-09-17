"""Tests for resilient Gmail API request execution."""

from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import GmailAPIError
from gmail.client import GmailClientFactory


def test_gmail_request_retries_transient_transport_error():
    request = MagicMock()
    request.execute.side_effect = [OSError("temporary network failure"), {"ok": True}]

    with (
        patch("gmail.client.time.sleep") as sleep,
        patch("gmail.client.random.uniform", return_value=0.0),
    ):
        result = GmailClientFactory.execute_with_retry(request, max_retries=3)

    assert result == {"ok": True}
    assert request.execute.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_gmail_request_raises_after_transport_retries_exhausted():
    request = MagicMock()
    request.execute.side_effect = OSError("network unavailable")

    with (
        patch("gmail.client.time.sleep"),
        patch("gmail.client.random.uniform", return_value=0.0),
        pytest.raises(GmailAPIError, match="network unavailable"),
    ):
        GmailClientFactory.execute_with_retry(request, max_retries=2)

    assert request.execute.call_count == 2
