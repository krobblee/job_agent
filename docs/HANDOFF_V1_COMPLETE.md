Job Agent v1 — COMPLETE CONTINUITY HANDOFF

This document exists so work on this project can continue without re-asking foundational questions, re-litigating decisions, or rediscovering “what good looks like.”
Treat this as authoritative for v1 unless explicitly revised.

1. User context (who this is for)

Senior Technical Program Manager / Product Operations leader.

Repeated career pattern: first or early TPM/Product Ops hire brought in to reduce chaos, build operating systems, and raise execution quality at scale.

Job search goal: avoid structurally low-leverage roles, even when they look senior or prestigious.

Strong preferences:

High autonomy

Deep work over constant coordination

Owning ambiguity

Building reusable mechanisms instead of permanent firefighting

Precision > recall. Noise is worse than missing edge cases.

Rejects must be visible; hidden filtering erodes trust.

Human judgment is the learning signal; the system should not override it.

2. System goal (what this project is trying to do)

Build a job search agent that:

Consistently surfaces a small, high-signal shortlist of roles worth deep consideration

Reliably filters out roles that are structurally misaligned with scope, leverage, and work preferences

Uses a Google Sheet as the source of truth for decisions and learning

Improves over time via human feedback, without auto-retraining in v1

This is not a job board scraper.
It is a taste-aligned filtering and sensemaking system.

3. V1 definition of “worth deep consideration” (locked)

A job is “worth deep consideration” in v1 when the shape of the role matches how the user creates value.

3.1 True Match (high-signal roles)

Roles that are predominantly:

High-leverage TPM / Product Ops work

Owning ambiguity rather than just tracking it

Creating operating mechanisms (cadence, metrics, decision frameworks, interfaces)

Cross-team or org-level in scope (not single-team delivery coordination)

Focused on consequential problems (platform shifts, AI integration, regulated workflows, operational transformation)

Structured so leverage increases over time (less firefighting, more system-building)

3.2 Structural misalignment (not worth deep consideration)

Roles that are predominantly:

Low-authority coordination or status herding

Meeting glue without mandate to fix systems

Infra-heavy execution without operating ownership

Delivery manager roles dressed up as strategy

Reactive support/custom request roles with no path to system-level fixes

3.3 V1 stance

The agent does not need perfect classification.
The primary constraint is:

The shortlist must stay small and high-signal, and the user must see what is being rejected.

4. Product decisions (do not revisit in v1)
4.1 Ingestion

Source: Gmail inbox

V1 ingestion: LinkedIn job alert / recommendation emails

Gmail query:

from:linkedin.com (subject:"job alert" OR subject:"recommended jobs")


Email content is used only to extract links.

All job data must come from the actual job posting page, never from the email body.

4.2 Output

Output is written to a Google Sheet

Sheet is the source of truth

Append-only rows

One row per job, immutable in v1

4.3 Deduplication

Prefer canonical job ID when available

Fallback to canonical URL

Canonical URLs strip all query / tracking parameters

Dedup occurs before writing to the sheet

4.4 Scoring and bucketing contract

Agent outputs:

agent_bucket: True Match / Monitor / Reject

agent_score: 0–100

Reasoning rules:

True Match + Reject: bucket + score only

Monitor: bucket + score + one-line explanation

Rejects are written to the sheet with scores.

4.5 Hard NOs

Only enforce hard NOs that are explicitly documented

No invented or inferred hard filters in v1

Everything else remains soft and learnable via feedback

5. Google Sheet semantics (locked)
5.1 Sheet URL

https://docs.google.com/spreadsheets/d/1mGVfJZuQzfIEtIbqnpxyh9UajHZ8b9JA77lXpR2hOgo/edit?gid=0#gid=0

5.2 Required columns

Identity & dedupe

job_id

job_url

apply_url

source

company

role_title

first_seen_date

Agent output

agent_bucket

agent_score

agent_reasoning (Monitor only)

agent_flags

Human judgment

human_decision (Apply / Skip / Maybe)

confidence (High / Medium / Low)

decision_reason

misclassification_type (False positive / False negative / Correct)

timestamp_reviewed

Structured signals

scope_fit (Strong / Medium / Weak)

ambiguity_level (High / Medium / Low)

leverage_level (Org / Multi-team / Team)

dealbreaker

notes

Operational

run_id

fetch_status (OK / DEAD_LINK / LOGIN_WALL / TOO_THIN / ERROR)

5.3 Sheet rules

Append-only

No rescoring or updating existing rows in v1

Sheet is not a workflow tracker

Used for dedupe, learning, and trust calibration

6. Reliability and safety rules (locked)

Fetch job posting pages and classify fetch_status

Extract apply_url when possible for quick human verification

fetch_status=OK requires a real job description page with sufficient content

Do not chase infinite redirects

Detect and label login walls and expired jobs

Canonicalize LinkedIn job URLs by stripping all query parameters

7. Current implementation state (as of handoff)
7.1 Repo

Private GitHub repo: job_agent

Entrypoint: run_agent.py

7.2 Gmail OAuth

Working

Credentials stored outside the repo

~/google_credentials/gmail_credentials.json

~/google_credentials/gmail_token.json

Required environment variables:

GMAIL_CREDENTIALS_PATH

GMAIL_TOKEN_PATH

7.3 What works

Gmail service builds successfully

LinkedIn alert emails are fetched

HTML parsing uses text/html payload part

Hrefs are extracted from email HTML

Job posting URLs are filtered correctly

URLs are canonicalized (tracking params removed)

Job(source="linkedin", url=...) objects created

~30 jobs extracted successfully per run

7.4 Known resolved issues (do not reintroduce)

get_gmail_service was accidentally deleted once → restored

OAuth files were mistakenly stored in __pycache__ → corrected

Pydantic validation failed when source was missing → fixed

Multiple function definitions caused confusion → resolved by full replacement

8. Next implementation phase (proceed without re-asking)

The next assistant should proceed directly to:

Dedup gate against Google Sheet

Fetch job posting pages (LinkedIn, ATS, company sites)

Extract:

job_description

role_title

company

apply_url

Set fetch_status

Score and bucket per v1 contract

Append rows to Google Sheet

9. Guidance for future assistants

Do not ask foundational questions already answered here

Default to visibility over automation

Never hide rejects

Treat the user’s sheet decisions as ground truth

Be decisive and concrete; avoid philosophical reframing unless explicitly requested

10. Continuation instruction

When continuing work:

Read README.md and docs/HANDOFF_V1_COMPLETE.md first.
Then proceed with job-page fetching and Google Sheet writing per this document.