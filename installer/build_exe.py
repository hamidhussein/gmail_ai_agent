"""
GmailAI Assistant - PyInstaller Automated Build Script
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def build_executable():
    """Compiles the application into a standalone Windows executable using PyInstaller."""
    print("=== Building GmailAI Assistant Standalone Executable ===")
    
    spec_file = ROOT_DIR / "installer" / "gmailai.spec"
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    
    if result.returncode == 0:
        print("\n[SUCCESS] GmailAI Assistant.exe built successfully in 'dist/' folder!")
    else:
        print("\n[ERROR] PyInstaller build failed.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_executable()
