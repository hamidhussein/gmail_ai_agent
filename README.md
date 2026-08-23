# GmailAI Assistant — Commercial AI Desktop Email Platform

<div align="center">

![GmailAI Status](https://img.shields.io/badge/GmailAI-v1.0.0%20Release-6366F1?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![UI](https://img.shields.io/badge/UI-Flet%20(Flutter%20Engine)-02569B?style=for-the-badge&logo=flutter)
![Security](https://img.shields.io/badge/Security-AES%20%2B%20OAuth%202.0-10B981?style=for-the-badge)
![AI Stack](https://img.shields.io/badge/Hybrid%20AI-Ollama%20%2B%20OpenAI-F59E0B?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**Privacy-First Hybrid AI Email Assistant for Windows**

</div>

---

## 🌟 Executive Overview

**GmailAI Assistant** is a commercial-grade desktop application that triages, analyzes, and drafts intelligent responses for your Gmail inbox. It combines an **on-device Local AI Engine (Ollama)** with a **Cloud AI Engine (OpenAI)** and a **Heuristic Rule Engine** with strict safety guardrails.

### 🔑 Key Features

- **⚡ 1-Click Google Sign-In**: Authenticate securely in your default browser and auto-sync with zero configuration.
- **📥 Intelligence Inbox**: Automatic multi-category classification across 11 standard enterprise categories (`CLIENT`, `WORK`, `BANK`, `FINANCE`, `LEGAL`, `NEWSLETTER`, `PROMOTION`, `SOCIAL`, `ADVERTISEMENT`, `SPAM`, `PERSONAL`).
- **🧠 Hybrid AI Router**:
  - Queries **Local AI (Ollama)** for zero latency & complete on-device privacy.
  - If confidence is $< 85\%$ or Ollama is offline, gracefully routes to **Cloud AI (OpenAI GPT-4o-mini)**.
  - Falls back to a deterministic **Heuristic Rule Engine** with 40+ domain maps for $100\%$ zero-crash reliability.
- **🎨 Light & Dark Themes**: Choose between Clean Slate Light Mode (Default) and Obsidian Midnight Dark Mode (`#060913`).
- **🧹 Smart Cleanup**: Batch-review and approve cleanup recommendations to archive newsletters and promotional spam in 1 click.
- **💬 AI Reply Assistant**: Context-aware drafting in 6 distinct tones (*Professional, Friendly, Short, Detailed, Apology, Follow-up*) with automatic Gmail draft synchronization.
- **📋 Daily Briefings**: Executive summaries, pending deadlines, and VIP requests aggregated into daily briefings.
- **🛡️ Privacy & Safety Guardrails**: Sensitive categories (Banking, Legal, Work VIPs) are protected from accidental modifications. Trashing and permanent deletions require explicit user confirmation.
- **💾 Local Encrypted Storage**: SQLite database with machine-salted AES encryption for tokens and 1-click encrypted backup export.

---

## 🚀 Quickstart

### Prerequisites
- Python **3.10+** (Python 3.12 recommended)
- (Optional) [Ollama](https://ollama.com/) running locally with `qwen2.5:latest` or `llama3.1:latest`
- (Optional) OpenAI API Key for cloud fallback

### Installation

```powershell
# 1. Clone the repository
git clone https://github.com/hamidhussein/gmail_ai_agent.git
cd gmail_ai_agent

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the application
python run.py
```

---

## 🔐 Google Cloud OAuth 2.0 Setup Guide

To connect your real Gmail account with Google's official OAuth 2.0 flow:

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/projectcreate) and create a new project (e.g. `Gmail AI Assistant`).

2. **Enable Gmail API**:
   - In your project, go to **APIs & Services** → **Library**, search for **Gmail API**, and click **Enable**.

3. **Configure OAuth Consent Screen**:
   - Go to **APIs & Services** → **OAuth consent screen**.
   - Select **External**, fill in the App name (`GmailAI`) and your email address.
   - **Important**: Under **Test users**, click **`+ ADD USERS`** and add your Gmail address (e.g., `youremail@gmail.com`).

4. **Create OAuth Client ID**:
   - Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth Client ID**.
   - Choose **Desktop app** as the Application type, name it `GmailAI`, and click **Create**.
   - Click **Download JSON** (⬇).

5. **Connect in App**:
   - In GmailAI, go to **Settings & AI** → **Step 5: Paste credentials.json content**, paste the JSON, and click **Save Credentials & Connect Gmail**!

> [!TIP]
> **Google Verification Warning**: When testing your app, Google may display *"Google hasn't verified this app"*. Click **Advanced** → **Go to Gmail AI Assistant (unsafe)** → **Continue** to grant permissions.

---

## 📦 Building Standalone Windows Executable (.exe)

Compile the entire application into a standalone Windows `.exe` using PyInstaller:

```powershell
python installer/build_exe.py
```

The compiled standalone executable will be generated in the `dist/` directory:
```
dist/
└── GmailAI Assistant/
    └── GmailAI Assistant.exe
```

---

## ⚙️ Configuration & Architecture

```
gmail_ai_agent/
├── app/
│   ├── main.py                  # Flet application shell & navigation coordinator
│   ├── config.py                # Persistent user configuration
│   └── constants.py             # Enums: Categories, ActionTypes, Risk, Tones
├── core/
│   ├── logger.py                # Rotating structured audit logger
│   ├── security.py              # Cryptography (AES-GCM/Fernet) & Safety policies
│   ├── exceptions.py            # Typed domain exceptions
│   └── events.py                # Thread-safe bidirectional event bus
├── authentication/
│   ├── oauth_manager.py         # Google OAuth 2.0 background threaded flow
│   ├── token_manager.py         # Encrypted token persistence
│   └── credential_manager.py    # Google Cloud credentials parser & validator
├── gmail/
│   ├── client.py                # Gmail API client with retry backoff
│   ├── reader.py                # Batch message synchronizer & fetcher
│   ├── parser.py                # Multi-part MIME decoding & HTML entity sanitizer
│   └── actions.py               # Safe Gmail modifications & draft creator
├── ai/
│   ├── router.py                # Hybrid AI Router (Local -> Cloud -> Heuristic)
│   ├── local_model.py           # Fast-offline Ollama REST client
│   ├── cloud_model.py           # OpenAI API client
│   ├── classifier.py            # 11-category classifier & 40+ domain heuristic engine
│   ├── summarizer.py            # Email & thread summarizer
│   └── reply_generator.py       # Context-aware 6-tone reply assistant
├── database/
│   ├── models.py                # SQLAlchemy ORM models
│   ├── repository.py            # Thread-safe database repository
│   └── migrations.py            # Auto-migrations & demo dataset seeder
├── ui/
│   ├── dashboard.py             # Executive overview & real-time metrics
│   ├── inbox_view.py            # Intelligence Inbox with Markdown reader & avatars
│   ├── review_screen.py         # Smart cleanup batch review screen
│   ├── digests_view.py          # Daily executive morning briefings
│   ├── audit_view.py            # Complete security & action audit logs
│   ├── settings.py              # Settings, AI model switcher, & OAuth wizard
│   └── components/
│       ├── google_auth_modal.py # 1-Click Google Sign-In dialog
│       ├── reply_modal.py       # AI Reply assistant modal
│       └── stat_card.py         # Glassmorphic statistic cards
└── run.py                       # Modern Flet application runner
```

---

## 🛡️ Security & Privacy Architecture

1. **Zero Data Telemetry**: Your emails never leave your machine unless you explicitly enable Cloud AI.
2. **Encrypted Token Vault**: OAuth tokens are salted and encrypted on disk using machine-level AES-256 keys.
3. **Double Verification Policy**: Trashing and deletion actions are never automated.
4. **Offline First**: Runs completely offline using local Ollama models or heuristic classification when no internet connection is available.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
