# Job Agent

A job-search agent that ingests jobs from Gmail, startup aggregators (e.g. topstartups.io), and curated company job boards, deduplicates and tracks postings via a Google Sheet, fetches and parses job pages, and scores eligible roles against a candidate profile. Supports three pipelines: **Email** (Gmail job alerts), **Aggregator** (scraping + Swooped), and **Companies** (Company List with hosted ATS board URLs → Company Jobs).

The system is resumable, inspectable, and safe to run repeatedly without silent drops or duplicate work.

---

## Quick Start

### Prerequisites
- Python 3.9+ (use `python3` and `pip3` — on many systems `python` points to Python 2 or doesn't exist)
- Gmail API credentials (`gmail_credentials.json`) — for Email pipeline
- Google Service Account credentials (`credentials/service_account.json`)
- Google Sheet with two tabs: **Email**, **Aggregator**

### First-time setup

Before running the Email pipeline, you need Gmail API and Google Sheets credentials. See **[SETUP.md](SETUP.md)** for step-by-step instructions:

- Creating a Google Cloud project
- Enabling Gmail API and creating OAuth credentials
- Creating a service account for the Google Sheet
- Creating and sharing the Sheet
- First-run OAuth flow (browser opens to authorize Gmail access)

### Installation

```bash
pip3 install -r requirements.txt
# Aggregator pipeline uses Swooped (Playwright). Install Chromium:
playwright install chromium
```

### Configuration

**Profile:** Copy `data/profile.example.txt` to `data/profile.txt` and customize with your experience, salary range, preferences, and hard NOs. The profile is used for scoring and is never committed (gitignored).

**Aggregator tab:** Add a `source` column if you use Swooped (values: `greenhouse` | `swooped`).

Create a `.env` file:
```
OPENAI_API_KEY=your_openai_key
SHEET_ID=your_google_sheet_id

# Optional — defaults shown
GMAIL_QUERY=from:(jobalerts-noreply@linkedin.com) newer_than:3d
EMAIL_WORKSHEET=Email
AGGREGATOR_WORKSHEET=Aggregator
PROFILE_PATH=data/profile.txt
AGGREGATOR_SNAPSHOT_DIR=data/snapshots
```

For Aggregator discovery, copy `data/Startup_URLs.example.txt` to `data/Startup_URLs.txt` and `data/Swooped_URLs.example.txt` to `data/Swooped_URLs.txt`, then add your URLs. Use job listing pages that link directly to ATS job pages.

**Companies pipeline:** Create two tabs: **Company List** and **Company Jobs** (see SETUP). **Important:** In `career_site_url`, paste the **direct hosted job board URL** where open roles are listed—the ATS page (Ashby, Greenhouse, Lever, Gem, Workday, Darwinbox, etc.), e.g. `https://jobs.ashbyhq.com/yourcompany` or your Greenhouse/Lever board URL. **Do not** use the marketing site’s generic careers page (e.g. `company.com/careers`) as your primary input; those pages often only link to the real board and are harder to scrape reliably. Optionally fill `company_url` with the main website; the agent may use it as a **fallback** if the job board URL fails, but the supported default is: **job board link in `career_site_url`.**

### Run

```bash
# Email pipeline (Gmail → Sheet → Fetch → Score)
python3 run_email.py

# Aggregator pipeline (Aggregators + Swooped → Sheet → Fetch → Score)
python3 run_aggregator.py

# Companies pipeline (Company List → job board discovery → Company Jobs → Fetch → Score)
python3 run_companies.py

# Rescore Email sheet only (no discovery/fetch) — use when profile/config changed
python3 scripts/rescore.py

# Re-fetch Email sheet (reset fetched → pending, then fetch) — use after parser changes
python3 scripts/rerun_fetch.py

# Company Jobs only: delete rows scored as reject (keeps sheet to true_match + monitor + pending)
python3 scripts/prune_company_jobs_rejects.py

# Add feedback for the agent to learn (in Cursor: "add to feedback: I rejected Microsoft")
python3 scripts/add_feedback.py "I wouldn't work at Microsoft, it's too big"
```

---

## System overview

Three pipelines share the same Sheet and scoring logic (separate tabs where noted):

### Email pipeline (`run_email.py`)
1. **Discovery** — Gmail job alerts → extract URLs, strip `/comm/` tracking
2. **Storage** — Upsert to Email tab
3. **Fetch** → **Score** — Same as Aggregator

### Aggregator pipeline (`run_aggregator.py`)
1. **Discovery** — Scrape aggregator pages (e.g. topstartups.io/jobs) + Swooped → extract direct ATS job URLs
2. **Delta** — Compare vs previous snapshot; only new URLs are "fresh" (posted since last run)
3. **Storage** — Append new jobs to Aggregator tab
4. **Fetch** → **Score** — Same as Email

### Companies pipeline (`run_companies.py`)
1. **Read Company List** — `company`, `company_url`, `career_site_url`, `last_error` (see SETUP for how to fill these)
2. **Discovery** — Scrape the **job board** URL in `career_site_url` and extract individual job posting URLs. If that fails, optionally fall back to `company_url` to find a careers link (less reliable—prefer putting the board URL directly in `career_site_url`)
3. **Storage** — Append new jobs to Company Jobs tab (dedupe by job_url)
4. **Fetch** → **Score** — Same as Email/Aggregator
5. **Prune** — After scoring, rows with `agent_bucket=reject` are **deleted** from Company Jobs only (true_match, monitor, and pending rows stay). Email and Aggregator tabs are unchanged. Run `python3 scripts/prune_company_jobs_rejects.py` anytime to clean rejects without a full pipeline run.

### Shared
- **Storage & resume** — Google Sheet is the single source of truth; explicit fetch_status lifecycle
- **Fetching** — Job pages fetched with browser headers; parsing extracts title, company, location from LinkedIn title format ("Company hiring Role in Location | LinkedIn")
- **Scoring** — Bucketed: **True Match / Monitor / Reject**; profile hard NOs include defense, crypto, government, salary below $180k base

---

## Project Structure

```
job-agent/
├── run_email.py               # Email pipeline (Gmail → Fetch → Score)
├── run_aggregator.py          # Aggregator pipeline (Aggregators + Swooped → Fetch → Score)
├── run_companies.py           # Companies pipeline (Company List → job board → Fetch → Score)
├── config.py                  # Settings, PROFILE, worksheet names
├── models.py                  # Job, ScoredJob, AgentDigest
├── requirements.txt
├── .env
│
├── agent/
│   ├── company_discovery.py   # Scrape ATS job boards / career pages, extract job URLs
│   ├── discovery.py           # Gmail job discovery
│   ├── feedback_parser.py     # Parse free-form feedback into FeedbackPreference
│   ├── feedback_store.py      # Load/save learned_preferences.json
│   ├── greenhouse_discovery.py  # Scrape aggregators for ATS job URLs
│   ├── sheet_client.py
│   ├── fetch_manager.py
│   ├── fetch_client.py
│   ├── page_parser.py
│   └── scorer.py
│
├── data/
│   ├── Startup_URLs.txt       # Aggregator URLs for discovery
│   ├── Swooped_URLs.txt       # Swooped search URLs
│   ├── feedback_raw.txt       # Raw feedback (stored first, never lost)
│   ├── learned_preferences.json  # Structured preferences (reject/exception lists, notes)
│   └── snapshots/             # Aggregator delta snapshots (by run)
│
├── scripts/
│   ├── add_feedback.py    # Add feedback: parse → dedupe → store
│   ├── aggregator_snapshot.py
│   ├── aggregator_upsert.py
│   ├── company_upsert.py      # Append Company Jobs from discovery
│   ├── normalize_comm_urls.py
│   ├── rerun_fetch.py     # Reset fetched rows and re-fetch (e.g. after parser changes)
│   ├── rescore.py         # Rescore Email sheet (no discovery/fetch)
│   ├── run_fetch_once.py
│   ├── swooped_upsert.py
│   └── upsert_pending.py
│
└── credentials/
    └── service_account.json
```

---

## Fetch lifecycle and resume contract (v1)

The fetch lifecycle is a core system contract and is locked for v1.

Job pages are not fetched eagerly. Instead, each discovered job URL progresses through an explicit lifecycle that enables retries, resumability, and clear failure modes.

### fetch_status (v1, locked)

- `pending`  
  Discovered but not fetched yet.

- `fetched`  
  HTTP fetch succeeded and at least one of `role_title` or `job_description` was successfully extracted.

- `failed`  
  Fetch was attempted but failed due to an HTTP error, parse failure, or empty parse result.  
  Empty parses must record `fetch_error = "parse_empty"`.

- `timeout`  
  Fetch exceeded the per-URL timeout or the overall run time budget.

### Retry behavior

- Each fetch attempt increments `fetch_attempts`
- Fetching must stop once `fetch_attempts >= MAX_FETCH_ATTEMPTS`
- For v1:  
  `MAX_FETCH_ATTEMPTS = 3`

### Resume invariants

- No silent drops: every discovered URL must end in a defined `fetch_status`
- Resume across runs is driven solely by `fetch_status` and `fetch_attempts`
- Rows with `fetch_status = fetched` must never be refetched in v1

### Scoring contract

**Bucket-based scoring (v1):**

Jobs are categorized into three buckets (NO numeric scoring):

- `true_match` - Strong fit, apply immediately
  - 0-1/greenfield opportunities
  - Founding TPM/Product Ops roles
  - AI-enabled transformation
  - Operating model improvement

- `monitor` - Partial fit, keep watching
  - Some good signals but missing key elements
  - Worth tracking for updates

- `reject` - Not a good fit
  - Infrastructure/platform/architecture heavy
  - Professional services/implementation
  - Compliance/regulatory/GRC domains
  - Defense/military, crypto/blockchain/Web3, government sector
  - Posted salary below $180k base (see config PROFILE)
  - Large enterprise/big tech (Microsoft, Google, Amazon, Oracle, Meta, Apple, Salesforce, IBM, etc.) — except Netflix, Zillow
  - Reposted jobs (e.g. "Reposted 3 days ago" in location/date — too late to apply)
  - **Auto-rejected before LLM:** Job description or location contains "no longer accepting applications", "applications are closed", or "role is closed" — these are never sent to the scorer

**Rule precedence:** Entity-level preferences override category rules (e.g. "Netflix is exception" overrides "reject large enterprises" for Netflix).

**Scoring invariant:**

Scoring must only run for rows where: `fetch_status == "fetched"`

Email-derived context must not be scored once job-page fetching is implemented.

---

## Core data model

The Google Sheet is the system’s persistent data model and source of truth.

The Sheet has tabs: **Email** (Gmail), **Aggregator** (scraping + Swooped), **Company List** (your curated companies—**put the hosted job board URL in `career_site_url`**), **Company Jobs** (output from Company List). Each job row = one job URL. Aggregator uses `first_seen` and `company` (board slug); Email uses `date_received`, `last_seen_at`.

**Discovery & Tracking:**
- `job_url` - Canonicalized job URL (tracking params stripped)
- `source` - Where the URL was discovered (e.g. gmail, greenhouse, swooped, **companies** for Company Jobs)
- `date_received` - When the URL was first discovered
- `last_seen_at` - Last time the URL was seen in Gmail query

**Fetch Lifecycle:**
- `fetch_status` - pending / fetched / failed / timeout
- `fetch_attempts` - Number of fetch attempts (max 3)
- `last_fetch_at` - Timestamp of last fetch attempt
- `fetch_error` - Error message if fetch failed

**Job Content:**
- `company` - Company name (parsed from LinkedIn title)
- `role_title` - Job title (parsed from LinkedIn title)
- `location` - Job location (parsed from LinkedIn title)
- `apply_url` - Application URL (if different from job_url)
- `job_description` - Full job description text
- `job_summary` - Brief summary (if provided)

**Scoring:**
- `agent_bucket` - true_match / monitor / reject
- `agent_reasoning` - Why the job was placed in this bucket

---

## How It Works

**Email** (`run_email.py`): Gmail → discover URLs → upsert to Sheet → fetch → score

**Aggregator** (`run_aggregator.py`): Scrape aggregators + Swooped → delta vs previous snapshot → append new jobs → fetch → score. Run every 48h to capture fresh postings.

**Companies** (`run_companies.py`): Company List (**`career_site_url` = hosted job board**) → discover job URLs → Company Jobs tab → fetch → score → prune rejects. See SETUP for tab setup.

All pipelines share fetch and score logic. The system is **resumable** — safe to run repeatedly.

---

## Key Features

- **Three pipelines** — Email (Gmail), Aggregator (scraping + Swooped), Companies (curated list + job boards); separate tabs where noted, shared fetch/score
- **Aggregator freshness** — Delta-based discovery (run every 48h; new URLs = fresh jobs)
- **Profile hard NOs** — Defense, crypto, government excluded from true_match
- **URL Normalization** — Strips `/comm/` from LinkedIn URLs
- **Batch Updates** — Avoids Sheets API rate limits
- **Explicit State** — pending/fetched/failed/timeout lifecycle
- **Column-order flexible** — Sheet writes use header names (A1 notation); you can reorder columns and writes still target the correct cells
- **Auto-reject closed roles** — Jobs with "no longer accepting applications" (or similar) are rejected before LLM scoring
- **Sheet append fix** — `table_range="A1"` ensures new rows append from column A even when the sheet has many empty columns
- **Human-in-the-loop feedback** — Add preferences via `add_feedback.py` or in Cursor; learned preferences (reject/exception lists, role-level notes) are included in scoring

---

## Learned preferences (feedback)

The agent learns from your feedback. Add company-level or role-level preferences:

- **Company reject/exception:** `python3 scripts/add_feedback.py "I won't work at Microsoft"` or `"Netflix is an exception"`
- **Role-level notes:** Tell Cursor "add to feedback: [your note]" — omit company name when the rejection is about the role type (e.g. project-level not program-level, hands-on data flows) so the pattern applies broadly

Feedback is stored in `data/learned_preferences.json` (reject list, exception list, notes). Raw feedback is always stored first in `data/feedback_raw.txt`. Entity rules override category rules (e.g. Netflix overrides "reject large enterprises").

---

## Design principles

- Explicit state over implicit behavior
- Safe retries instead of best-effort execution
- Idempotent operations wherever possible
- Contracts documented before implementation
- Google Sheet as single source of truth

---

## Non-goals (v1)

- No background scheduling
- No concurrent fetching
- No auto-refetch of fetched rows
- No schema evolution beyond documented fields
