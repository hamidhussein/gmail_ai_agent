"""
Unit Tests - Structured Error Reporting & Bulk Operation Recovery
"""
import pytest
from core.error_reporter import sanitize_error, format_user_error, BulkOperationResult
from core.exceptions import GmailAPIError, SafetyViolationError, AuthenticationError


def test_sanitize_error_strips_sensitive_data():
    raw_error = Exception(
        "Failed reading token at C:\\Users\\Administrator\\AppData\\token.json "
        "for user test.user+label@gmail.com with token ya29.a0AfH6SMB_secret_oauth_token_12345"
    )
    sanitized = sanitize_error(raw_error, context="auth_test")

    assert "test.user+label@gmail.com" not in sanitized
    assert "<email>" in sanitized
    assert "C:\\Users\\Administrator\\AppData\\token.json" not in sanitized
    assert "<path>" in sanitized
    assert "ya29.a0AfH6SMB_secret_oauth_token_12345" not in sanitized
    assert "<token>" in sanitized
    assert sanitized.startswith("[auth_test]")


def test_sanitize_error_redacts_long_quoted_body():
    raw_error = Exception(
        "Invalid message content: 'This is a very long confidential email body containing financial records and private customer discussions.'"
    )
    sanitized = sanitize_error(raw_error)
    assert "financial records" not in sanitized
    assert "'<content>'" in sanitized


def test_format_user_error_friendly_messages():
    gmail_err = GmailAPIError("Raw internal error with server stacktrace 503")
    assert "Gmail could not complete the archive" in format_user_error(gmail_err, "archive")

    safety_err = SafetyViolationError("Blocked action on VIP domain")
    assert "blocked by a safety rule" in format_user_error(safety_err, "delete")

    auth_err = AuthenticationError("Token expired")
    assert "Authentication required" in format_user_error(auth_err)

    unknown_err = ValueError("Unexpected internal state")
    msg = format_user_error(unknown_err, "sync")
    assert "Could not complete sync" in msg
    assert "Unexpected internal state" not in msg


def test_bulk_operation_result_tracking():
    result = BulkOperationResult()
    assert result.total == 0
    assert not result.has_failures
    assert not result.all_succeeded

    # Record 3 successes
    result.record_success(1)
    result.record_success(2)
    result.record_success(3)
    assert result.success_count == 3
    assert result.failure_count == 0
    assert result.all_succeeded
    assert "Successfully cleaned 3 emails!" in result.summary_message("cleaned")

    # Record 1 failure
    result.record_failure(4, GmailAPIError("Failed for user@example.com"))
    assert result.total == 4
    assert result.success_count == 3
    assert result.failure_count == 1
    assert result.has_failures
    assert not result.all_succeeded

    summary = result.summary_message("cleaned")
    assert "3/4 emails" in summary
    assert "1 failed" in summary

    # Verify error was sanitized in result.errors
    item_id, sanitized_err = result.errors[0]
    assert item_id == 4
    assert "user@example.com" not in sanitized_err
    assert "<email>" in sanitized_err


def test_bulk_operation_all_failed():
    result = BulkOperationResult()
    result.record_failure(10, Exception("Connection refused"))
    assert result.success_count == 0
    assert result.failure_count == 1
    assert "Could not clean any emails" in result.summary_message("cleaned")
