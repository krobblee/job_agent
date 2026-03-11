# Job Agent — Handoff V2

This document captures solved, locked invariants for the job agent system.

Anything documented here must not be silently changed or re-litigated in later handoffs.

---

## Solved invariants (locked — do not change)

### System structure

- Gmail is used only for discovery
- Google Sheet is the single source of truth
- Job-page fetching is a distinct phase from discovery and scoring
- Scoring must operate only on fetched job pages

---

### Job-page fetch lifecycle (v1)

The job-page fetch lifecycle is explicitly defined and locked for v1.

The Google Sheet is authoritative for fetch state and resume behavior.

#### fetch_status enum

- `pending`  
  Job URL has been discovered but not fetched yet.

- `fetched`  
  HTTP fetch succeeded and at least one of `role_title` or `job_description` was extracted.

- `failed`  
  Fetch was attempted but failed (HTTP error, parse failure, or empty parse).  
  Empty parses must record `fetch_error = "parse_empty"`.

- `timeout`  
  Fetch exceeded per-URL timeout or overall run time budget.

#### Retry contract

- Each fetch attempt increments `fetch_attempts`
- Fetching must stop once `fetch_attempts >= MAX_FETCH_ATTEMPTS`
- For v1:  
  `MAX_FETCH_ATTEMPTS = 3`

#### Resume and safety guarantees

- No silent drops: every URL must terminate in a defined fetch_status
- Resume across runs is driven solely by fetch_status and fetch_attempts
- Rows with `fetch_status = fetched` are immutable for v1 and must not be refetched

#### Scoring gate

Scoring is contractually gated on fetch completion.

Only rows where:

`fetch_status == "fetched"`

are eligible to be scored.

#### Pre-filter: closed roles

Before LLM scoring, jobs are auto-rejected if `job_description` or `location_text` contains any of:

- "no longer accepting applications"
- "applications are closed"
- "role is closed"

These jobs are never sent to the LLM and are bucketed as `reject` with reason "Role is closed: no longer accepting applications".

#### Scoring robustness (LLM JSON parse)

If the LLM returns invalid or truncated JSON, the scorer:
1. Extracts the JSON object (between first `{` and last `}`) to handle trailing prose
2. Retries once with a stricter prompt
3. If retry fails, buckets all jobs in that batch as `reject` with reason "Scoring failed: LLM returned invalid JSON" — the pipeline does not crash

---

## Gmail ingestion

- Gmail is queried using explicit search strings
- Discovery is idempotent
- Gmail-derived context is for discovery only and must not influence scoring

---

## Google Sheet storage

- The Sheet is the system’s source of truth
- All state transitions are written explicitly
- Resume logic must read from the Sheet, not memory
- `append_row` uses `table_range="A1"` so new rows always start at column A; without it, the Sheets API may detect a "table" starting at the first column with data (e.g. column O) and write there instead

---

## Known, intentional limitations (v1)

- Single-threaded execution
- No background workers
- No concurrent fetches
- No schema migration logic

---

## Purpose of this handoff

This document exists to prevent re-litigation of core contracts while enabling focused, incremental implementation work in later handoffs.
