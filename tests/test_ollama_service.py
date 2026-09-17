"""Tests for the Ollama process lifecycle controller."""

from unittest.mock import MagicMock, patch

from ai.ollama_service import OllamaServiceController


def test_start_returns_immediately_when_ollama_is_running():
    controller = OllamaServiceController()

    with (
        patch.object(controller, "is_running", return_value=True),
        patch.object(controller, "find_executable") as find_executable,
    ):
        success, message = controller.start("http://localhost:11434")

    assert success
    assert "already running" in message
    find_executable.assert_not_called()


def test_start_launches_server_and_waits_for_endpoint():
    controller = OllamaServiceController()
    process = MagicMock()
    process.poll.return_value = None

    with (
        patch.object(controller, "is_running", side_effect=[False, True]),
        patch.object(controller, "find_executable", return_value=r"C:\Ollama\ollama.exe"),
        patch("ai.ollama_service.subprocess.Popen", return_value=process) as popen,
    ):
        success, message = controller.start("http://localhost:11434")

    assert success
    assert "started successfully" in message
    assert popen.call_args.args[0] == [r"C:\Ollama\ollama.exe", "serve"]


def test_stop_targets_only_ollama_process_and_verifies_shutdown():
    controller = OllamaServiceController()
    completed = MagicMock(returncode=0, stdout="SUCCESS", stderr="")

    with (
        patch.object(controller, "is_running", side_effect=[True, False]),
        patch("ai.ollama_service.subprocess.run", return_value=completed) as run,
    ):
        success, message = controller.stop("http://localhost:11434")

    assert success
    assert "stopped successfully" in message
    assert run.call_args.args[0] == ["taskkill", "/IM", "ollama.exe", "/T", "/F"]


def test_stop_is_safe_when_ollama_is_already_offline():
    controller = OllamaServiceController()

    with (
        patch.object(controller, "is_running", return_value=False),
        patch("ai.ollama_service.subprocess.run") as run,
    ):
        success, message = controller.stop("http://localhost:11434")

    assert success
    assert "already stopped" in message
    run.assert_not_called()
