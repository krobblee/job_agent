# Job Agent

This repository implements a job-search agent that ingests job alerts from Gmail, deduplicates and tracks job postings via a Google Sheet, fetches and parses job pages, and scores eligible roles against a candidate profile.

The system is designed to be resumable, inspectable, and safe to run repeatedly without silent drops or duplicate work.

---

## System overview

The job agent operates as a staged pipeline:

1. **Discovery**
   - Gmail is queried for job alert emails
   - Job URLs are extracted from email HTML bodies
   - URLs are canonicalized and deduplicated

2. **Storage & resume**
   - A Google Sheet is the single source of truth
   - Each job URL is tracked with explicit state
   - All stages resume safely across runs

3. **Fetching**
   - Job pages are fetched with per-URL timeouts
   - Parsing extracts structured job information
   - Failures are recorded explicitly

4. **Scoring**
   - Only successfully fetched job pages are scored
   - Scoring uses bounded, cleaned job-page input
   - Email-derived context is never scored once fetching exists

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

### Scoring invariant

Scoring must only run for rows where:

`fetch_status == "fetched"`

Email-derived context must not be scored once job-page fetching is implemented.

---

## Core data model

The Google Sheet is the system’s persistent data model and source of truth.

Each row represents a unique job URL and includes:

- job_url
- source
- date_received
- company
- role_title
- location
- apply_url
- job_description
- job_summary
- fetch_status
- fetch_attempts
- last_fetch_at
- fetch_error
- last_seen_at

---

## Design principles

- Explicit state over implicit behavior
- Safe retries instead of best-effort execution
- Idempotent operations wherever possible
- Contracts documented before implementation

---

## Non-goals (v1)

- No background scheduling
- No concurrent fetching
- No auto-refetch of fetched rows
- No schema evolution beyond documented fields
