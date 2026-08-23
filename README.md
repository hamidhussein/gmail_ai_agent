# GmailAI Assistant — Commercial Desktop AI Email Management Platform

<div align="center">

![GmailAI Header](https://img.shields.io/badge/GmailAI-Production%20Ready-6366F1?style=for-the-badge)
![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![UI](https://img.shields.io/badge/Desktop%20UI-CustomTkinter-blueviolet?style=for-the-badge)
![Security](https://img.shields.io/badge/Security-AES%20%2B%20OAuth%202.0-emerald?style=for-the-badge)
![AI Stack](https://img.shields.io/badge/Hybrid%20AI-Ollama%20%2B%20OpenAI-orange?style=for-the-badge)

**Privacy-First Hybrid AI Email Assistant for Windows**

</div>

---

## 🌟 Executive Overview

**GmailAI Assistant** is a commercial-grade Windows desktop application built to safely analyze, organize, triage, and draft responses for Gmail accounts. It combines an **on-device Local AI Engine (Ollama)** with a **Cloud AI Engine (OpenAI)** and a **Safety Verification Policy Guardrail** that prevents automated destruction of sensitive emails.

### 🔑 Key Capabilities
- **📥 Inbox Intelligence Engine**: Multi-category classification across 11 standard enterprise categories (`CLIENT`, `WORK`, `BANK`, `FINANCE`, `LEGAL`, `NEWSLETTER`, `PROMOTION`, `SOCIAL`, `ADVERTISEMENT`, `SPAM`, `PERSONAL`).
- **🧠 Hybrid AI Router**:
  - Automatically queries **Local AI (Ollama)** for low latency & complete data privacy.
  - If confidence is $< 85\%$ or Local AI is offline, seamlessly escalates to **Cloud AI (OpenAI GPT-4o-mini)**.
  - Features a resilient **Heuristic Rule Engine** fallback to ensure $100\%$ zero-crash uptime.
- **🛡️ Strict Safety Guardrails**: Permanent deletion and trashing are **never automatic** and require double user verification. Sensitive categories (Banking, Legal, Government, Work VIPs) cannot be modified without authorization.
- **🧹 Smart Cleanup Review Screen**: Batch review and approve suggestions to archive old newsletters and marketing spam in 1-click.
- **💬 Executive Reply Assistant**: Drafts replies in 6 distinct tones (*Professional, Friendly, Short, Detailed, Apology, Follow-up*) and saves directly into your Gmail drafts.
- **📋 Daily AI Morning Briefing**: Summarizes incoming trends, VIP requests, and pending deadlines into an executive markdown briefing.
- **💾 Local SQLite Database with Encryption**: AES-encrypted token storage, machine-salted keys, and 1-click disaster recovery backup (`gmailai_backup.zip`).

---

## 🏗️ Architecture Overview

```
                          USER
                           |
                           v
               Desktop UI (CustomTkinter)
                           |
             -----------------------------
             |                           |
             v                           v
     Gmail OAuth 2.0             Hybrid AI Router
     (Encrypted Tokens)                  |
             |             -----------------------------
             v             |                           |
         Gmail API         v                           v
             |        Local AI Engine           Cloud AI Engine
             |         (Ollama Local)            (OpenAI API)
             v             |                           |
   Email Parsing Engine    -----------------------------
             |                           |
             -----------------------------
                           |
                           v
                Decision & Safety Engine
                (Mandatory User Approvals)
                           |
                           v
                Action & Draft Executor
```

---

## 📁 Repository Structure

```
gmail_ai_agent/
├── app/
│   ├── main.py                  # CustomTkinter GUI orchestrator & lifecycle
│   ├── config.py                # Configuration & persistent settings
│   └── constants.py             # Enums: Categories, ActionTypes, Risk, Tones
├── core/
│   ├── logger.py                # Rotating structured file & audit logger
│   ├── security.py              # Cryptography (AES-GCM/Fernet) & Safety policies
│   ├── exceptions.py            # Custom exception classes
│   └── events.py                # Thread-safe event bus
├── authentication/
│   ├── oauth_manager.py         # Google OAuth 2.0 flow & token refresh
│   ├── token_manager.py         # Encrypted on-disk token persistence
│   └── credential_manager.py    # Google Cloud credentials validator
├── gmail/
│   ├── client.py                # Gmail API client wrapper & retry backoff
│   ├── reader.py                # Batch message synchronizer & fetcher
│   ├── parser.py                # Multi-part MIME decoding & HTML stripper
│   ├── actions.py               # Safe Gmail modification & draft executor
│   └── labels.py                # Gmail label synchronizer
├── ai/
│   ├── router.py                # Hybrid AI Router (>85% local -> local decision)
│   ├── local_model.py           # Ollama REST client (Qwen 2.5, Llama 3.1)
│   ├── cloud_model.py           # OpenAI API client (GPT-4o, GPT-4o-mini)
│   ├── classifier.py            # 11-category classifier & heuristic engine
│   ├── summarizer.py            # Email & thread summarizer
│   ├── reply_generator.py       # Context-aware 6-tone reply assistant
│   └── confidence.py            # Uncertainty & confidence calculator
├── memory/
│   ├── user_profile.py          # User preferences & signature settings
│   ├── preference_engine.py     # Sender importance & VIP scoring
│   └── learning.py              # Feedback loop learning from user approvals
├── database/
│   ├── models.py                # SQLAlchemy ORM models
│   ├── repository.py            # Thread-safe query & CRUD operations
│   └── migrations.py            # Database initialization & demo seeder
├── automation/
│   ├── scheduler.py             # Background daemon thread scheduler
│   ├── daily_digest.py          # Daily executive briefing compiler
│   └── reminders.py             # Deadline & follow-up detector
├── ui/
│   ├── dashboard.py             # Main dashboard: metrics, health, AI status
│   ├── inbox_view.py            # Inbox explorer with split-detail drawer
│   ├── review_screen.py         # Safe cleanup batch review screen
│   ├── digests_view.py          # Historical daily briefings browser
│   ├── audit_view.py            # Action audit trail viewer
│   ├── settings.py              # AI model, OAuth, safety, backup controls
│   └── components/
│       ├── navigation.py        # Modern sidebar with active badges
│       ├── stat_card.py         # Glassmorphic KPI metric widget
│       ├── email_card.py        # Interactive email row card
│       ├── action_dialog.py     # Double-confirmation safety dialog
│       ├── reply_modal.py       # AI reply composer modal
│       └── toast.py             # Non-blocking floating notifications
├── installer/
│   ├── build_exe.py             # PyInstaller automated packaging script
│   ├── gmailai.spec             # Spec file for standalone binary
│   └── inno_setup.iss           # Windows Setup Installer script
├── tests/                       # Automated pytest test suite (18 tests)
├── run.py                       # Top-level application runner
├── requirements.txt             # Python dependencies
├── README.md                    # Documentation
└── LICENSE                      # MIT License
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.12+**
- (Optional for Local AI): **[Ollama](https://ollama.com/)** installed and running (`ollama run qwen2.5` or `ollama run llama3.1`)
- (Optional for Live Gmail): Google Cloud OAuth 2.0 `credentials.json` (Desktop app type)

### 2. Installation
Clone the repository and install requirements:
```bash
git clone https://github.com/gmailai/assistant.git
cd gmail_ai_agent
python -m pip install -r requirements.txt
```

### 3. Run the Application
Launch the desktop application:
```bash
python run.py
```

> **Demo Mode Available Out-of-the-Box**:
> When first launched, GmailAI Assistant automatically seeds realistic demo emails across multiple categories (Banking, Legal NDA, Client Quotations, Newsletters, Spam) so you can immediately experience the UI, AI classification, Reply Assistant, and Safety features without needing an active Google Cloud project.

---

## ⚙️ Configuration & Setup

### Setting Up Live Gmail OAuth
1. Open Google Cloud Console: [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**.
3. Configure the OAuth Consent Screen and create an **OAuth 2.0 Client ID** (Application Type: *Desktop App*).
4. Download the `credentials.json` file.
5. In GmailAI Assistant, go to **⚙️ Settings > Gmail Authentication**, click **📁 Browse File...**, select your `credentials.json`, and click **🔑 Google Login**.

### Setting Up Local AI (Ollama)
1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull your model of choice:
   ```bash
   ollama pull qwen2.5:latest
   ```
3. In GmailAI Assistant under **⚙️ Settings > Hybrid AI Router**, confirm the URL is `http://localhost:11434` and click **⚡ Test Local AI**.

### Setting Up Cloud AI (OpenAI)
1. In **⚙️ Settings > Hybrid AI Router**, paste your `sk-...` API key into the OpenAI Key field.
2. Select your model (`gpt-4o-mini` or `gpt-4o`) and click **☁️ Save & Test Cloud**.
3. All API keys are securely AES-encrypted before being stored on disk.

---

## 🧪 Testing

Run the comprehensive automated unit and integration test suite:
```bash
python -m pytest tests/ -v
```

Tests cover:
- Cryptographic token encryption & machine-tied key derivation
- SQLite SQLAlchemy CRUD transactions & aggregations
- Multi-part MIME decoding and HTML entity conversion
- Hybrid AI Router confidence threshold escalation
- Rule-based Heuristic Engine & Phishing detection
- Safety policies, protected domains, and double-confirmation checks
- Preference memory engine and sender VIP weighting

---

## 📦 Packaging for Windows

### Build Standalone Executable (.exe)
```bash
python installer/build_exe.py
```
The compiled single-file standalone executable will be generated at:
```
dist/GmailAI Assistant.exe
```

### Build Windows Installer (.msi / setup.exe)
Open `installer/inno_setup.iss` in **Inno Setup** and click **Compile** to generate `GmailAI_Setup_v1.0.0.exe`.

---

## 🛡️ Production Security Checklist

- [x] **OAuth 2.0 Standard**: No user passwords ever touched or stored.
- [x] **AES Token Encryption**: All OAuth refresh tokens and API keys are stored in AES-encrypted binary files.
- [x] **Local-First Privacy**: Sensitive emails can be classified entirely locally using Ollama on the user's computer.
- [x] **Safety Guardrails**: Hard deletion requires double confirmation; protected institutions (Banking, Legal, Medical) cannot be auto-archived.
- [x] **Audit Trail**: Every action taken is logged immutably in `ActionAuditLog` with timestamps and authorization rationale.
- [x] **1-Click Backup**: Easy disaster recovery export (`gmailai_backup.zip`) and restore.

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
