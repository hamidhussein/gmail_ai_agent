"""Lifecycle controls for the local Ollama service."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

from ai.local_model import LocalOllamaClient


class OllamaServiceController:
    """Start and stop the local Ollama server without blocking the UI."""

    def __init__(self) -> None:
        self._operation_lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None

    @staticmethod
    def find_executable() -> Optional[str]:
        configured = os.environ.get("GMAILAI_OLLAMA_EXECUTABLE", "").strip()
        candidates = [
            configured,
            shutil.which("ollama") or "",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
            str(Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe"),
        ]
        return next((path for path in candidates if path and Path(path).is_file()), None)

    @staticmethod
    def is_running(base_url: str) -> bool:
        return LocalOllamaClient(base_url=base_url).is_available(force_check=True)

    def start(self, base_url: str, timeout: float = 15.0) -> Tuple[bool, str]:
        """Start ``ollama serve`` and wait until its HTTP endpoint is ready."""
        with self._operation_lock:
            if self.is_running(base_url):
                return True, "Ollama is already running."

            executable = self.find_executable()
            if not executable:
                return False, "Ollama is not installed or ollama.exe could not be found."

            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

            try:
                self._process = subprocess.Popen(
                    [executable, "serve"],
                    cwd=str(Path(executable).parent),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
            except OSError as exc:
                return False, f"Could not start Ollama: {exc}"

            deadline = time.monotonic() + max(1.0, timeout)
            while time.monotonic() < deadline:
                if self.is_running(base_url):
                    return True, "Ollama started successfully."
                if self._process.poll() is not None:
                    return False, f"Ollama exited during startup (code {self._process.returncode})."
                time.sleep(0.25)

            return False, f"Ollama did not become ready within {timeout:.0f} seconds."

    def stop(self, base_url: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Stop the Ollama service and confirm that its endpoint is offline."""
        with self._operation_lock:
            if not self.is_running(base_url):
                return True, "Ollama is already stopped."

            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["taskkill", "/IM", "ollama.exe", "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=timeout,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        check=False,
                    )
                    if result.returncode not in (0, 128):
                        detail = (result.stderr or result.stdout or "unknown error").strip()
                        return False, f"Could not stop Ollama: {detail}"
                elif self._process and self._process.poll() is None:
                    self._process.terminate()
                else:
                    result = subprocess.run(
                        ["pkill", "-TERM", "-x", "ollama"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=timeout,
                        check=False,
                    )
                    if result.returncode not in (0, 1):
                        return False, "Could not stop the Ollama process."
            except (OSError, subprocess.SubprocessError) as exc:
                return False, f"Could not stop Ollama: {exc}"

            deadline = time.monotonic() + max(1.0, timeout)
            while time.monotonic() < deadline:
                if not self.is_running(base_url):
                    self._process = None
                    return True, "Ollama stopped successfully."
                time.sleep(0.25)

            return False, "Ollama is still responding after the stop request."


ollama_service_controller = OllamaServiceController()
