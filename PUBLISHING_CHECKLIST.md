# GmailAI Assistant — Google OAuth & Production Publishing Checklist

This document details the configuration, verification, and security requirements needed to publish and distribute **GmailAI Assistant** beyond local development and private testing.

---

## 1. OAuth Consent Screen Configuration

### A. General Information
- [ ] **Google Cloud Project**: Dedicated GCP project created (e.g., `gmailai-assistant-prod`).
- [ ] **User Type**: Set to **External** (allows any Google account to sign in).
- [ ] **App Name**: `GmailAI Assistant`
- [ ] **User Support Email**: Verified support email address.
- [ ] **Application Logo**: 120x120px PNG with transparent background.
- [ ] **Application Home Page**: Public HTTPS website explaining the app.
- [ ] **Privacy Policy Link**: Public HTTPS link (must explicitly disclose email handling).
- [ ] **Terms of Service Link**: Public HTTPS link.
- [ ] **Authorized Domains**: Add your root domain (e.g., `gmailai.app`).
- [ ] **Developer Contact Information**: Primary maintainer email address.

---

## 2. OAuth Scopes & Google Classification

GmailAI Assistant uses the following scopes declared in `authentication/oauth_manager.py`:

| Scope URI | Classification | Purpose in GmailAI Assistant |
|-----------|----------------|------------------------------|
| `openid` | Non-sensitive | OpenID Connect identity verification |
| `.../auth/userinfo.email` | Non-sensitive | Display active email in UI |
| `.../auth/userinfo.profile` | Non-sensitive | Display user name/avatar |
| `.../auth/gmail.readonly` | **Restricted** | Read inbox messages for AI classification |
| `.../auth/gmail.modify` | **Restricted** | Archive messages and move spam/trash to Trash |
| `.../auth/gmail.send` | **Sensitive** | Create or send drafts upon user approval |

### Scope Justification for Google Review
When submitting for verification, you must provide clear justifications:
- **`gmail.readonly`**: *"Needed to fetch user's incoming emails and headers for local AI categorization, VIP detection, and daily digest generation."*
- **`gmail.modify`**: *"Needed to apply archive labels and move junk/newsletter emails to Trash strictly when explicitly approved by the user."*
- **`gmail.send`**: *"Needed to save generated reply drafts directly into the user's Gmail Drafts folder upon user request."*

---

## 3. Private Beta vs. Public Release Paths

### Path A: Private Beta (Up to 100 Users)
- **Publishing Status**: *Testing*
- **Google Verification**: **Not required**.
- **User Access**: Specific users must be added to the **Test Users** list in the Google Cloud Console.
- **Limitations**:
  - Maximum 100 test accounts.
  - Refresh tokens expire after 7 days if the app is in "Testing" mode and not verified.

### Path B: Broad Production Release
- **Publishing Status**: *In Production*
- **Google Verification**: **Mandatory**.
- **Requirements**:
  1. **Public Privacy Policy**: Must adhere to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the **Limited Use** requirements.
  2. **Demo Video**: Unlisted YouTube video demonstrating:
     - The OAuth consent screen with client ID visible in the browser address bar.
     - Permission grant flow.
     - Each requested scope being used in the app (reading emails, archiving, drafting).
  3. **Domain Ownership**: Domain ownership verified in [Google Search Console](https://search.google.com/search-console).
  4. **CASA Tier 2 Security Assessment**: Restricted scopes (`gmail.readonly`, `gmail.modify`) may require a Cloud Application Security Assessment (CASA) through an authorized lab or automated scanning.

---

## 4. Windows Binary Distribution & Code Signing

- [ ] **Executable Build**: Build with `installer/gmailai.spec` using Python 3.12 64-bit.
- [ ] **Smoke Test**: Run `scripts/verify_exe.ps1` to ensure startup in a fresh environment.
- [ ] **Code Signing**:
  - Sign `GmailAI Assistant.exe` with a Microsoft Authenticode standard or EV Code Signing Certificate (`signtool.exe`).
  - Without code signing, Windows SmartScreen will display an "Unknown Publisher" warning on first launch.
- [ ] **Installer Package**: (Optional) Package into an Inno Setup or WiX MSI installer for standard `%LOCALAPPDATA%\Programs` installation and desktop shortcuts.

---

## 5. Security & Privacy Controls Checklist

- [ ] **Token Encryption**: Master key generated with machine-specific entropy or user password via `core/security.py`.
- [ ] **Error Sanitization**: Ensure all UI toasts and non-audit logs use `core.error_reporter.sanitize_error()`.
- [ ] **Database Upgrades**: Schema version tracked via `database.migration_runner.run_migrations()`.
- [ ] **Thread Safety**: All background scheduler and OAuth events marshalled via `page.run_task` / `_dispatch_ui`.
- [ ] **Revocation Recovery**: When a user revokes permissions from Google Account Security, `EVT_AUTH_REQUIRED` automatically prompts reconnection without crashing.

---

## 6. Pre-Release Verification Commands

```powershell
# 1. Run all unit and regression tests
.\venv\Scripts\pytest.exe -v

# 2. Verify git status is clean
git status --short

# 3. Test executable packaging
powershell -ExecutionPolicy Bypass -File scripts\verify_exe.ps1
```
