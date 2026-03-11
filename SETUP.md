# Job Agent — First-time Setup

This guide walks you through setting up Google Cloud credentials and a Google Sheet so you can run the Job Agent. You only need to do this once.

---

## Overview

The agent needs:

1. **Gmail API** (Email pipeline) — OAuth credentials to read job alert emails
2. **Google Sheets API** (both pipelines) — Service account to read/write the job tracking sheet

---

## Before you start

1. **Complete the [Installation](README.md#installation) section in the README first** — Python 3.9+, `pip3 install -r requirements.txt`, and `playwright install chromium` (optional if you only use Email)

2. **Create `.env`** — Copy `.env.example` to `.env` and fill in the required values (see Part 5)

---

## Part 1: Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one):
   - Click the project dropdown at the top
   - Click **New Project**
   - Name it (e.g. "Job Agent") and click **Create**

---

## Part 2: Gmail API (Email Pipeline)

### Enable the API

1. In the Cloud Console, go to **APIs & Services** → **Library**
2. Search for **Gmail API**
3. Click it and click **Enable**

### Create OAuth credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted to configure the OAuth consent screen:
   - Choose **External** (unless you have a Google Workspace org)
   - Fill in App name (e.g. "Job Agent") and your email
   - Add your email under Test users
   - Click **Save and Continue** through the steps
4. Back at **Create OAuth client ID**:
   - Application type: **Desktop app**
   - Name: e.g. "Job Agent Desktop"
   - Click **Create**
5. Click **Download JSON** (or copy the JSON from the dialog)
6. Save the file as `gmail_credentials.json` in your job-agent project root (same folder as `run_email.py`)

### First run

When you run `python3 run_email.py` for the first time:

- A browser window will open
- Sign in with the Google account that receives job alert emails
- Click **Allow** to grant read-only access to Gmail
- A `gmail_token.json` file will be created (stores the refresh token; no need to re-authenticate unless you revoke access)

---

## Part 3: Google Sheets (Service Account)

### Enable the APIs

1. In the Cloud Console, go to **APIs & Services** → **Library**
2. Search for and enable **Google Sheets API**
3. Search for and enable **Google Drive API**

### Create a service account

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **Service account**
3. Name it (e.g. "job-agent-sheets") and click **Create and Continue**
4. Skip optional steps (roles, etc.) and click **Done**
5. Click the service account you just created
6. Open the **Keys** tab

### Download the key

1. Click **Add Key** → **Create new key**
2. Choose **JSON** and click **Create**
3. The JSON file downloads automatically
4. Save it as `credentials/service_account.json` in your project folder

   - Create the `credentials/` folder if it doesn't exist
   - This file is gitignored (never commit it)

### Get the service account email

1. In the service account details, copy the **Client email** (e.g. `job-agent-sheets@your-project.iam.gserviceaccount.com`)
2. You'll need this to share your Google Sheet

---

## Part 4: Google Sheet

### Create the sheet

1. Go to [Google Sheets](https://sheets.google.com/) and create a new spreadsheet
2. Rename it (e.g. "Job Agent")
3. Create two tabs: **Email** and **Aggregator**
4. Add the required headers in row 1 (see below)

### Share with the service account

1. Click **Share**
2. Paste the service account email (from Part 3)
3. Set permission to **Editor**
4. Uncheck "Notify people" (the service account doesn't read email)
5. Click **Share**

### Get the Sheet ID

The Sheet ID is in the URL when you have the sheet open:

```
https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit
```

Copy this ID for your `.env` file.

### Required columns

**Email tab** (row 1):

| job_url | source | date_received | fetch_status | fetch_attempts | fetch_error | last_fetch_at | last_seen_at | company | role_title | location | apply_url | job_description | job_summary | agent_bucket | agent_reasoning |

**Aggregator tab** (row 1):

| source | first_seen | company | role_title | job_url | location | department | fetch_status | fetch_attempts | last_fetch_at | fetch_error | job_description | job_summary | agent_bucket | agent_reasoning |

You can add more columns; the agent uses header names to find the right cells.

---

## Part 5: Verify

### OpenAI API key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Create an account or sign in
3. Go to **API Keys** → **Create new secret key**
4. Copy the key and add it to `.env` as `OPENAI_API_KEY=...`

> **Note:** OpenAI may require a billing method (credit card) for API access. Usage is pay-per-token; scoring typically costs a few cents per run.

### Environment variables (.env)

Copy `.env.example` to `.env` and fill in:

**Required:**
| Variable | Description |
|----------|--------------|
| `SHEET_ID` | From your Google Sheet URL (the long ID between `/d/` and `/edit`) |
| `OPENAI_API_KEY` | From platform.openai.com → API Keys |

**Optional** (defaults shown in `.env.example`):
| Variable | Description |
|----------|--------------|
| `GMAIL_QUERY` | Gmail search for job alerts (default: LinkedIn, newer_than:3d). Can be changed for other sources (Indeed, Glassdoor, etc.) — uses [Gmail search syntax](https://support.google.com/mail/answer/7190) |
| `GMAIL_MAX_RESULTS` | Max messages to fetch from Gmail (default: 50) |
| `EMAIL_WORKSHEET` | Tab name for Email pipeline (default: Email) |
| `AGGREGATOR_WORKSHEET` | Tab name for Aggregator pipeline (default: Aggregator) |
| `PROFILE_PATH` | Path to your profile file (default: data/profile.txt) |
| `STARTUP_URLS_PATH` | Aggregator URLs file (default: data/Startup_URLs.txt) |
| `SWOOPED_URLS_PATH` | Swooped search URLs (default: data/Swooped_URLs.txt) |
| `AGGREGATOR_SNAPSHOT_DIR` | For delta freshness (default: data/snapshots) |

### Profile

1. Copy `data/profile.example.txt` to `data/profile.txt`
2. Customize with your experience, salary range, preferences, and hard NOs
3. See **Profile optimization** below for best matches

### Run

```bash
python3 run_email.py
```

- First run: browser opens for Gmail OAuth
- After auth: job URLs from Gmail are written to the Google Sheet

---

## Profile optimization

The profile drives scoring. Structure it for better matches:

- **Experience** — Years, role type, domain. Be specific so the LLM can match job descriptions.
- **Salary** — State your minimum. Jobs with posted salary below this are auto-rejected.
- **Preferences** — What you want (0-1, greenfield, remote, etc.). Positive signals for true_match.
- **Hard NOs** — Domains, role types, work arrangements you won't consider. Be explicit.
- **Exceptions** — Companies that override category rules (e.g. "reject large enterprises" but "Netflix is exception").

**Tips:** Entity rules override category rules. Use `add_feedback.py` to refine over time; the agent learns from your feedback.

---

## Optional: Aggregator pipeline

The Aggregator pipeline discovers jobs from startup aggregators and Swooped (no Gmail needed). To use it:

1. **Chromium** — Ensure you ran `playwright install chromium` (see Before you start)

2. **Startup URLs** — Copy `data/Startup_URLs.example.txt` to `data/Startup_URLs.txt` and add aggregator URLs (e.g. topstartups.io, Wellfound, YC jobs)

3. **Swooped URLs** — Copy `data/Swooped_URLs.example.txt` to `data/Swooped_URLs.txt`. Go to [swooped.co](https://swooped.co), build a search with your filters, and paste the full URL

4. **Run:** `python3 run_aggregator.py`

---

## Feedback

The agent learns from your preferences. Give feedback in two ways:

**Terminal:**
```bash
python3 scripts/add_feedback.py "I won't work at Microsoft"
python3 scripts/add_feedback.py "Netflix is an exception"
```

**AI-powered code editor (e.g. Cursor):** Say "add to feedback: [your preference]" — the AI can run the script for you.

Feedback is stored in `data/feedback_raw.txt` and `data/learned_preferences.json` (created automatically). Entity rules override category rules.

---

## Troubleshooting

**"gmail_credentials.json not found"**  
- Save the OAuth client JSON as `gmail_credentials.json` in the project root. See Part 2.

**"Permission denied" or "Access not configured"**  
- Ensure Gmail API and Sheets API are enabled in the Cloud Console
- Ensure the Sheet is shared with the service account email (Editor access)

**"SHEET_ID must be set"**  
- Add `SHEET_ID=your_sheet_id` to your `.env` file

**"Profile file not found"**  
- Copy `data/profile.example.txt` to `data/profile.txt` and customize

**OAuth token expired**  
- Delete `gmail_token.json` and run `run_email.py` again to re-authenticate

---

## FAQ

**Why do I need both Gmail OAuth and a service account?**  
Gmail OAuth lets the agent read *your* inbox (job alerts). The service account lets the agent read/write a shared Google Sheet. Different APIs, different auth.

**Can I use job alerts from Indeed or Glassdoor instead of LinkedIn?**  
Yes. Set `GMAIL_QUERY` in `.env` to a Gmail search that finds those emails. Use [Gmail search syntax](https://support.google.com/mail/answer/7190) (e.g. `from:indeed.com` or `from:glassdoor.com`).

**Where does my profile go?**  
`data/profile.txt` is gitignored — it stays on your machine and is never committed. The profile is sent to OpenAI when scoring; see README for details.

**Can I put credentials outside the project folder?**  
`gmail_credentials.json` and `gmail_token.json` are currently expected in the project root. The service account path is fixed at `credentials/service_account.json`. Custom paths are not yet supported via env vars.

**Why does the Aggregator pipeline need Playwright?**  
Swooped is a JavaScript-heavy site; Playwright runs a real browser to capture job data. The Email pipeline does not need it.

**How do I rescore jobs after changing my profile?**  
Run `python3 scripts/rescore.py` to re-score the Email sheet without re-fetching.
