"""Tests for Settings connection-status helpers."""
from unittest.mock import MagicMock

from ui.settings import evaluate_ollama_status


def test_ollama_status_reports_unreachable_server():
    client = MagicMock(base_url="http://localhost:11434")
    client.is_available.return_value = False

    success, message = evaluate_ollama_status(client, "qwen2.5:latest")

    assert not success
    assert "not reachable" in message
    client.is_available.assert_called_once_with(force_check=True)


def test_ollama_status_reports_missing_model():
    client = MagicMock(base_url="http://localhost:11434")
    client.is_available.return_value = True
    client.list_installed_models.return_value = []

    success, message = evaluate_ollama_status(client, "qwen2.5:latest")

    assert not success
    assert "no models are installed" in message
    assert "ollama pull qwen2.5:latest" in message


def test_ollama_status_accepts_latest_tag_alias():
    client = MagicMock(base_url="http://localhost:11434")
    client.is_available.return_value = True
    client.list_installed_models.return_value = ["qwen2.5:latest"]

    success, message = evaluate_ollama_status(client, "qwen2.5")

    assert success
    assert "is installed" in message
