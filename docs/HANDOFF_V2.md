# Job Agent — Handoff Instructions (V2, Contract Edition)
# Job Agent — Handoff Instructions (V2, Contract Edition)

You are continuing work on the **job-agent** project.

This handoff exists to **prevent rework, rediscovery, and ambiguity**.
Before proposing changes, you must read **README.md**, **HANDOFF_V1_COMPLETE.md**, and this document in full.

If something appears “broken,” assume first that it was **already solved** in a prior chat.

---

## Canonical Setup (Non-Negotiable)

- **Canonical repository location:**  
  `/Users/katierobblee/Documents/job-agent`

- This folder is:
  - the Git repository
  - the folder opened in Cursor
  - the working directory for all terminal commands

Do **not** assume any other folders are relevant.  
Previous duplicate repos were intentionally deprecated and removed.

---

## How to Work With This User (Mandatory Behavior)

### Step discipline
- Operate **one step at a time**
- Wait for explicit confirmation before proceeding
- Do not batch steps
- Do not preview future steps unless explicitly asked

### Tool clarity
- Always specify **Cursor (editor)** vs **Terminal (repo root)**
- Never assume the user knows where a command should be run

### Code change hygiene
- Prefer **single, full replacement blocks** over partial diffs
- Avoid multi-file or multi-location edits unless unavoidable
- Optimize for copy/paste correctness and indentation safety

### Teaching constraint
- Educate the user in basic coding practices and hygiene **only when it prevents future breakage or confusion**
- Do **not** overexplain fundamentals or provide tutorials unless explicitly asked

---

## Mandatory “Already Solved?” Protocol

If you encounter:
- extraction failures
- context-window errors
- Gmail auth issues
- repo / Git confusion
- performance or timeout questions
- architectural uncertainty

You must **pause before debugging** and ask:

> “Was this already solved in a prior chat?  
If so, what was the final rule, invariant, or constant we should re-apply?”

If prior context may exist, explicitly ask the user to retrieve it.  
Do **not** rediscover known solutions.

---

## Solved Invariants (Locked — Do Not Change)

### Gmail ingestion
- Gmail OAuth works
- **Do NOT use Gmail snippets**
- Parse the decoded `text/html` email body
- Walk `payload.parts`, including nested parts
- Extract `<a href="...">` links
- Filter to:
  - `linkedin.com/jobs/view/`
  - `linkedin.com/comm/jobs/view/`
- Canonicalize URLs by stripping everything after `?`
- This logic was previously debugged and confirmed working (≈20–30 URLs per run)

### LLM usage (context-window safety)
Context-window errors are already solved.

Mandatory constraints:
- `MAX_JOBS_PER_LLM_CALL = 10`
- `MAX_JOB_DESCRIPTION_CHARS = 6000`
- Jobs are processed in batches
- Job text is truncated **before** LLM calls

Do **not** remove batching or truncation.

### Model output parsing
- The model may return JSON wrapped in ```json fences
- Code-fence stripping is required before parsing
- Pydantic validation expects clean JSON only

## Job Page Fetching + Resume Contract (v1)

This section defines job-page fetching as a required step before downstream processing. It does not modify Gmail ingestion, URL extraction, or scoring logic.

### Purpose

Job-page fetching exists to replace email-derived context with page-derived data, while preserving resumability and explicit failure states via the Google Sheet.

### fetch_status contract

The following enum is authoritative for v1:

pending  
Discovered, not fetched yet.

fetched  
HTTP succeeded and at least one of `role_title` or `job_description` was extracted.

failed  
Fetch attempted but failed due to HTTP error, parse error, or empty parse.

timeout  
Per-URL timeout or overall run budget exceeded.

### Explicit parse rule
If HTTP succeeds but extraction yields neither `role_title` nor `job_description`, the row must be marked as `failed` and `fetch_error` must be set to `parse_empty`.

### Retry policy
MAX_FETCH_ATTEMPTS = 3
Rows in `pending`, `failed`, or `timeout` are retryable up to the attempt cap. `fetched` is terminal for v1.

### Invariants

No silent drops.  
Resume behavior is driven solely by Sheet state.  
Scoring must only consume rows with `fetch_status == fetched`.

Once implemented, this contract is part of v1 and must not be altered without an explicit version change.


### Source of truth
- Google Sheet is authoritative for:
  - deduplication
  - fetch status
  - scoring output
- Never silently drop jobs
- Never hide rejects
- Local SQLite is optional and non-authoritative

---

## Google Sheet Storage (Intentional Constraint)

The Google Sheet is optimized for **fast human scanning and decision-making**, not raw data retention.

- Do **NOT** store full job descriptions in the Sheet
- The 6k character limit applies **only** to LLM input safety
- Sheet fields should contain:
  - short summaries
  - extracted highlights
  - stable metadata (company, title, URLs)
- Full job text, if retained at all, should live outside the Sheet

Do **not** mirror LLM payloads into Sheet storage.

---

## Known, Intentional Limitations (Do Not “Fix” Prematurely)

- LLM currently receives **URLs + metadata only**
- Job page fetching is not implemented yet
- Scoring quality is expected to be low until job pages are fetched

Do **not** attempt to “improve scoring” before job page fetching exists.

---

## Current Phase (Authorized Scope)

Ingestion and ranking plumbing are stable.

You may work on:
- Fetching job posting pages (LinkedIn first)
- Extracting:
  - `job_description`
  - `company`
  - `role_title`
  - `apply_url`
- Enforcing:
  - per-URL timeouts
  - overall run time budgets
  - resume/retry behavior via Sheet (`fetch_status`)

---

## Processing Guarantees (Contractual)

- **No silent drops**
  - Every extracted job URL must eventually reach one of:
    `fetched`, `failed`, or `pending`
  - No URL may be silently skipped or discarded

- **Time budgets over hard caps**
  - Use overall run time budgets and per-URL timeouts
  - Hard caps such as “process only the first N jobs” are **not allowed**
    unless explicitly approved by the user
  - Jobs not processed within the time budget must remain eligible for future runs

- **Explicit uncertainty**
  - If data cannot be fetched or inferred reliably, record the failure reason
  - Do **not** guess, infer, or reject due to missing data

---

## Purpose of This Handoff

This user is a TPM building a real developer-style system.

Your role is to:
- Preserve solved ground
- Prevent rediscovery
- Move forward deliberately
- Optimize for momentum, clarity, and confidence

If unsure, pause and ask.