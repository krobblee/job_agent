# Job Agent

This repository implements a job-search agent that ingests job alerts from Gmail, deduplicates and tracks job postings via a Google Sheet, fetches and parses job pages, and scores eligible roles against a candidate profile.

The system is designed to be resumable, inspectable, and safe to run repeatedly without silent drops or duplicate work.

---

## Quick Start

### Prerequisites
- Python 3.9+
- Gmail API credentials (`gmail_credentials.json`)
- Google Service Account credentials (`credentials/service_account.json`)
- Google Sheet for job tracking

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Then edit .env with your values
```

### Configuration

Create a `.env` file with:
```
OPENAI_API_KEY=your_openai_key
GMAIL_QUERY=from:(jobalerts-noreply@linkedin.com) newer_than:3d
SHEET_ID=your_google_sheet_id
```

### Run

```bash
python run_agent.py
```

---

## System overview

The job agent operates as a staged pipeline:

1. **Discovery**
   - Gmail is queried for job alert emails
   - Job URLs are extracted from email HTML bodies
   - URLs are canonicalized and deduplicated (strips `/comm/` tracking paths)

2. **Storage & resume**
   - A Google Sheet is the single source of truth
   - Each job URL is tracked with explicit state
   - All stages resume safely across runs

3. **Fetching**
   - Job pages are fetched with enhanced browser headers
   - Parsing extracts structured job information (title, company, description)
   - Failures are recorded explicitly with retry logic

4. **Scoring**
   - Only successfully fetched job pages are scored
   - Jobs are bucketed: **True Match / Monitor / Reject**
   - Results written back to Sheet with reasoning

---

## Project Structure

```
job-agent/
├── run_agent.py              # Main orchestrator - runs full pipeline
├── config.py                 # Settings, constants, API clients
├── models.py                 # Data classes (Job, ScoredJob, AgentDigest)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
│
├── agent/                    # Core modules
│   ├── discovery.py          # GmailDiscoverySource - job discovery from Gmail
│   ├── sheet_client.py       # SheetClient - Google Sheet read/write
│   ├── fetch_manager.py      # FetchManager - fetch lifecycle & retry logic
│   ├── fetch_client.py       # HttpFetcher - URL fetching with headers
│   ├── page_parser.py        # HTML parsing functions
│   └── scorer.py             # Job scoring and bucketing
│
├── scripts/                  # Utility scripts
│   ├── normalize_comm_urls.py  # Clean up /comm/ tracking URLs
│   ├── run_fetch_once.py       # Run fetch step only
│   └── upsert_pending.py       # Manual URL insertion
│
└── credentials/              # API credentials (not in git)
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

**Scoring invariant:**

Scoring must only run for rows where: `fetch_status == "fetched"`

Email-derived context must not be scored once job-page fetching is implemented.

---

## Core data model

The Google Sheet is the system’s persistent data model and source of truth.

Each row represents a unique job URL and includes:

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
- `company` - Company name
- `role_title` - Job title
- `location` - Job location
- `apply_url` - Application URL (if different from job_url)
- `job_description` - Full job description text
- `job_summary` - Brief summary (if provided)

**Scoring:**
- `agent_bucket` - true_match / monitor / reject
- `agent_reasoning` - Why the job was placed in this bucket

---

## How It Works

When you run `python run_agent.py`, the agent executes this pipeline:

1. **Connect to Google Sheet** - Establishes connection to your tracking sheet
2. **Discover jobs from Gmail** - Queries Gmail for job alert emails, extracts URLs
3. **Write to Sheet** - Upserts new URLs as "pending", updates last_seen_at for existing
4. **Fetch job pages** - Fetches up to 25 pending jobs per run with retry logic
5. **Score jobs** - Buckets fetched jobs into true_match/monitor/reject with reasoning
6. **Update Sheet** - Writes buckets and reasoning back to Sheet

The system is **resumable** - you can run it multiple times and it will pick up where it left off.

---

## Key Features

- **URL Normalization** - Strips tracking parameters and `/comm/` paths from LinkedIn URLs
- **Batch Updates** - Writes to Sheet in batches to avoid API rate limits
- **Retry Logic** - Up to 3 fetch attempts per URL with exponential backoff
- **Explicit State** - Every job has clear status (pending/fetched/failed/timeout)
- **Clean Separation** - Modular design with clear responsibilities

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
