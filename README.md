# Job Agent

A job-search agent that ingests jobs from Gmail and startup aggregators (e.g. topstartups.io), deduplicates and tracks postings via a Google Sheet, fetches and parses job pages, and scores eligible roles against a candidate profile. Supports separate pipelines for LinkedIn (Gmail) and Greenhouse (ATS) jobs.

The system is resumable, inspectable, and safe to run repeatedly without silent drops or duplicate work.

---

## Quick Start

### Prerequisites
- Python 3.9+
- Gmail API credentials (`gmail_credentials.json`) — for LinkedIn pipeline
- Google Service Account credentials (`credentials/service_account.json`)
- Google Sheet with two tabs: LinkedIn, Greenhouse

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:
```
OPENAI_API_KEY=your_openai_key
SHEET_ID=your_google_sheet_id

# Optional — defaults shown
GMAIL_QUERY=from:(jobalerts-noreply@linkedin.com) newer_than:3d
LINKEDIN_WORKSHEET=Sheet1
GREENHOUSE_WORKSHEET=Greenhouse
```

For Greenhouse discovery, add aggregator URLs to `data/Startup_URLs.txt` (one per line). Use job listing pages that link directly to ATS job pages — e.g. `https://topstartups.io/jobs`.

### Run

```bash
# LinkedIn pipeline (Gmail → Sheet → Fetch → Score)
python run_agent.py

# Greenhouse pipeline (Aggregators → Sheet → Fetch → Score)
python run_greenhouse.py

# Rescore only (no discovery/fetch) — use when profile/config changed
python scripts/rescore.py

# Re-fetch all (reset fetched → pending, then fetch) — use after parser changes
python scripts/rerun_fetch.py

# Add feedback for the agent to learn (in Cursor: "add to feedback: I rejected Microsoft")
python scripts/add_feedback.py "I wouldn't work at Microsoft, it's too big"
```

---

## System overview

Two pipelines share the same Sheet and scoring logic:

### LinkedIn pipeline (`run_agent.py`)
1. **Discovery** — Gmail job alerts → extract URLs, strip `/comm/` tracking
2. **Storage** — Upsert to LinkedIn tab
3. **Fetch** → **Score** — Same as Greenhouse

### Greenhouse pipeline (`run_greenhouse.py`)
1. **Discovery** — Scrape aggregator pages (e.g. topstartups.io/jobs) → extract direct Greenhouse job URLs
2. **Delta** — Compare vs previous snapshot; only new URLs are "fresh" (posted since last run)
3. **Storage** — Append new jobs to Greenhouse tab
4. **Fetch** → **Score** — Same as LinkedIn

### Shared
- **Storage & resume** — Google Sheet is the single source of truth; explicit fetch_status lifecycle
- **Fetching** — Job pages fetched with browser headers; parsing extracts title, company, location from LinkedIn title format ("Company hiring Role in Location | LinkedIn")
- **Scoring** — Bucketed: **True Match / Monitor / Reject**; profile hard NOs include defense, crypto, government, salary below $180k base

---

## Project Structure

```
job-agent/
├── run_agent.py              # LinkedIn pipeline (Gmail → Fetch → Score)
├── run_greenhouse.py         # Greenhouse pipeline (Aggregators → Fetch → Score)
├── config.py                 # Settings, PROFILE, worksheet names
├── models.py                 # Job, ScoredJob, AgentDigest
├── requirements.txt
├── .env
│
├── agent/
│   ├── discovery.py          # Gmail job discovery
│   ├── feedback_parser.py    # Parse free-form feedback into FeedbackPreference
│   ├── feedback_store.py     # Load/save learned_preferences.json
│   ├── greenhouse_discovery.py  # Scrape aggregators for Greenhouse job URLs
│   ├── sheet_client.py
│   ├── fetch_manager.py
│   ├── fetch_client.py
│   ├── page_parser.py
│   └── scorer.py
│
├── data/
│   ├── Startup_URLs.txt        # Aggregator URLs for Greenhouse discovery
│   ├── feedback_raw.txt         # Raw feedback (stored first, never lost)
│   ├── learned_preferences.json  # Structured preferences (reject/exception lists, notes)
│   └── snapshots/            # Greenhouse delta snapshots (by run)
│
├── scripts/
│   ├── add_feedback.py    # Add feedback: parse → dedupe → store
│   ├── greenhouse_upsert.py
│   ├── greenhouse_snapshot.py
│   ├── normalize_comm_urls.py
│   ├── rerun_fetch.py     # Reset fetched rows and re-fetch (e.g. after parser changes)
│   ├── rescore.py         # Rescore all fetched jobs without discovery/fetch
│   ├── run_fetch_once.py
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
  - Large enterprise/big tech (Microsoft, Google, Amazon, etc.) — except Netflix, Zillow
  - Reposted jobs (e.g. "Reposted 3 days ago" in location/date — too late to apply)
  - Job description includes "No longer accepting applications" (role is closed)

**Rule precedence:** Entity-level preferences override category rules (e.g. "Netflix is exception" overrides "reject large enterprises" for Netflix).

**Scoring invariant:**

Scoring must only run for rows where: `fetch_status == "fetched"`

Email-derived context must not be scored once job-page fetching is implemented.

---

## Core data model

The Google Sheet is the system’s persistent data model and source of truth.

The Sheet has two tabs: **LinkedIn** (Gmail) and **Greenhouse** (aggregators). Each row = one job URL. Greenhouse uses `first_seen` and `company` (board slug); LinkedIn uses `date_received`, `last_seen_at`.

**Discovery & Tracking:**
- `job_url` - Canonicalized job URL (tracking params stripped)
- `source` - Where the URL was discovered (Gmail, LinkedIn)
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

**LinkedIn** (`run_agent.py`): Gmail → discover URLs → upsert to Sheet → fetch → score

**Greenhouse** (`run_greenhouse.py`): Scrape aggregators → delta vs previous snapshot → append new jobs → fetch → score. Run every 48h to capture fresh postings.

Both pipelines share fetch and score logic. The system is **resumable** — safe to run repeatedly.

---

## Key Features

- **Dual pipelines** — LinkedIn (Gmail) and Greenhouse (aggregator scraping); separate tabs, shared fetch/score
- **Greenhouse freshness** — Delta-based discovery (run every 48h; new URLs = fresh jobs)
- **Profile hard NOs** — Defense, crypto, government excluded from true_match
- **URL Normalization** — Strips `/comm/` from LinkedIn URLs
- **Batch Updates** — Avoids Sheets API rate limits
- **Explicit State** — pending/fetched/failed/timeout lifecycle
- **Column-order flexible** — Sheet writes use header names (A1 notation); you can reorder columns and writes still target the correct cells
- **Human-in-the-loop feedback** — Add preferences via `add_feedback.py` or in Cursor; learned preferences (reject/exception lists, role-level notes) are included in scoring

---

## Learned preferences (feedback)

The agent learns from your feedback. Add company-level or role-level preferences:

- **Company reject/exception:** `python scripts/add_feedback.py "I won't work at Microsoft"` or `"Netflix is an exception"`
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
