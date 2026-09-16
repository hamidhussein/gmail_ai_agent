"""
GmailAI Assistant - Desktop Application Runner for Flet
"""
import sys
import os
import flet as ft

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import main

if __name__ == "__main__":
    view = ft.AppView.WEB_BROWSER if "--web" in sys.argv or os.environ.get("FLET_VIEW") == "web" else ft.AppView.FLET_APP
    ft.run(main, view=view)
