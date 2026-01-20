# job_agent
Job Search Agent
# Job Agent
## Project Status (Ground Truth — Do Not Relitigate)

This repository contains a **working v1 job-search agent** with the following **already-solved invariants**. These decisions are intentional and should not be reworked without explicit user direction.

### Solved & Locked Decisions

**Gmail ingestion**
- Gmail OAuth + message fetching works
- We do NOT use Gmail snippets
- Job URLs are extracted from the decoded `text/html` email body
- Extraction logic:
  - Walk `payload.parts`
  - Decode `text/html` MIME part (base64url)
  - Extract `<a href="...">` links
  - Filter to:
    - `linkedin.com/jobs/view/`
    - `linkedin.com/comm/jobs/view/`
  - Canonicalize by stripping everything after `?`
- This logic was previously debugged and confirmed working (≈20–30 URLs/run)

**LLM usage constraints (to avoid context-window errors)**
- LLM calls are batched
- Constants:
  - `MAX_JOBS_PER_LLM_CALL = 10`
  - `MAX_JOB_DESCRIPTION_CHARS = 6000`
- Jobs beyond the batch limit are processed in batches
- This is mandatory; do not remove batching

**Current limitation (known and intentional)**
- LLM currently receives only metadata + URLs
- Job page fetching has NOT been implemented yet
- As a result, scoring quality is expected to be low until job pages are fetched

### Source of Truth
- Google Sheet will be the source of truth for:
  - deduplication
  - fetch status
  - scoring outputs
- Local SQLite is for experimentation only

### What Comes Next (v1 continuation)
- Fetch job posting pages (LinkedIn first)
- Extract:
  - job_description
  - company
  - role_title
  - apply_url
- Respect:
  - per-URL timeout
  - overall run time budget
  - resume via Sheet (`fetch_status`)


An extensible, AI-powered job search agent designed to identify **high-leverage Product Operations / Technical Program Management / Chief of Staff–type roles** in ambiguous, growth-stage environments.

The agent prioritizes **system design, decision-making infrastructure, and workflow transformation**, not task execution or checklist enforcement.

---

## 🎯 Goal

Help identify roles where I can:
- Design, redesign, or significantly evolve **how product teams decide what to build**
- Improve **speed to customer value** by fixing decision systems
- Bring order to ambiguous environments
- Apply **product thinking to the organization itself**
- Leverage AI to change *how teams work*, not just what they ship

The agent produces two outputs:
- **True Matches**
- **Monitor / Adjacent** (worth a closer look)

---

## 🚫 Hard NOs (Non-Negotiable)

Roles are rejected if they are primarily about:
- Compliance, regulatory, legal, GRC, or risk
- Implementation, onboarding, professional services, or customer delivery
- Infrastructure, platform, migrations, architecture, SRE, or DevOps
- Checklist execution or status reporting **without authority to change systems**
- Analytics or reporting as the primary responsibility

Dashboards are acceptable **only when they are part of building or fixing a decision system**, not reporting theater.

---

## 🧭 What *Is* a Strong Match

Strong positives include:
- Org-level or multi-team scope
- Authority or mandate to design / fix operating models
- Ambiguous or broken systems that need clarity
- Focus on prioritization, planning, and execution systems
- AI-enabled transformation that improves SDLC / PDLC
- Titles like:
  - Product Operations
  - Technical Program Manager (Senior / Staff / Director)
  - Director of Project Management
  - Engineering or Product Chief of Staff  
  *(Titles are not determinative; scope and leverage matter more.)*

---

## 🌍 Work & Compensation Constraints

- Fully remote
- Must be open to **U.S.-based employees**
- Working hours must be **Eastern Time–friendly**
- Occasional travel (≤10%) is acceptable
- Avoid APAC-based companies or APAC hours  
  - *Exception: Atlassian*

**Compensation floor (when listed):**
- $170k base
- $240k total compensation

**Explicit large-company exceptions:**
- Atlassian
- Zillow *(ideal)*
- Stripe
- HubSpot
- Netflix

---

## 🧠 Architecture Overview

The system is intentionally split into three layers:

[ Ingestion (source-specific) ]
↓
[ Normalized Job objects ]
↓
[ Agent reasoning & scoring ]

yaml
Copy code

### Key design principles
- Ingestion is **dumb** (email, Ashby, Greenhouse, etc.)
- Reasoning is **centralized**
- The agent reasons only over **normalized Job objects**
- New sources can be added without changing the agent logic

---
## Job Page Fetching (v1)

Job page fetching is a required pipeline stage that runs after URL extraction and before scoring. The Google Sheet is the single source of truth and controls resume behavior across runs.

### fetch_status (v1 contract)

This enum is locked for v1 and must not be silently changed.

pending  
Discovered, not fetched yet.

fetched  
HTTP succeeded and at least one of `role_title` or `job_description` was extracted.

failed  
Fetch attempted but failed due to HTTP error, parse error, or empty parse.

timeout  
Per-URL timeout or overall run budget exceeded.

### Parse failure rule

If the HTTP request succeeds but neither `role_title` nor `job_description` is extracted, the row must be marked as `failed` with `fetch_error = "parse_empty"`.

### Retry semantics

MAX_FETCH_ATTEMPTS = 3

Rows in `pending`, `failed`, or `timeout` may be retried up to the attempt cap. `fetched` is terminal for v1.

### Required system-owned columns

fetch_status  
fetch_attempts  
last_fetch_at  
fetch_error (nullable)

### Scoring invariant

Scoring must only run for rows where `fetch_status == "fetched"`. Email-derived context must not be scored once job-page fetching is implemented.

---

## 📦 Core Data Model

All sources output a normalized `Job` object:

```python
class Job(BaseModel):
    source: str                 # gmail | ashby | greenhouse
    url: str
    title: str | None
    company: str | None
    location_text: str | None
    salary_text: str | None
    employment_type: str | None
    job_description: str | None
    metadata: dict
Missing fields are allowed. Ambiguity is handled by the agent, not ingestion.

📬 Current Ingestion Sources
Gmail (in progress)
Uses Gmail API

Extracts job URLs from job-alert emails

Outputs Job objects with raw email context

Currently parsing snippets; HTML body parsing is next

Planned
Ashby job boards

Greenhouse job boards

Direct company career pages

🧠 Agent Reasoning
The agent:

Applies hard eligibility gates (remote, location, comp when listed, hard NOs)

Reasons holistically using a True Match fingerprint

Assigns:

Score (0–100)

Bucket (True Match / Monitor / Reject)

Explanation of tradeoffs

The agent is guided, not scripted — it has autonomy within clear boundaries.

🚧 Current Status
Gmail authentication working

Job model implemented

Gmail ingestion refactored to output Job objects

Legacy URL/DB pipeline removed

Current blocker
Prompt still references {items} instead of {jobs}

Gmail ingestion extracts 0 jobs because only email snippets are parsed

Next steps
Update prompt input from {items} → {jobs}

Parse full Gmail email body (HTML parts) to extract job links

Add shared job-page enrichment (title, company, salary, etc.)

Add Ashby ingestion

Add Greenhouse ingestion

🛠 Local Setup
bash
Copy code
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_agent.py
Environment variables:

OPENAI_API_KEY

Gmail OAuth credentials (gmail_credentials.json)

📌 Notes
This project is intentionally exploratory. Requirements are expected to evolve as more data is gathered and feedback loops are added.

The goal is not to automate job applications — it is to surface the right opportunities worth deep consideration.

markdown




