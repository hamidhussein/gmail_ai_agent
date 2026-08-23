"""
GmailAI Assistant - Desktop Application Runner
"""
import sys
import os

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import main

if __name__ == "__main__":
    main()
