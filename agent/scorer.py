from __future__ import annotations

from pathlib import Path

from config import LEARNED_PREFERENCES_PATH, PROFILE, client
from agent.feedback_store import load_preferences
from models import AgentDigest, ScoredJob, Job

# Phrases that indicate a role is closed; auto-reject before LLM scoring
CLOSED_ROLE_PHRASES = ("no longer accepting applications", "applications are closed", "role is closed")


def _is_closed_role(job: Job) -> bool:
    """Return True if job description indicates the role is closed."""
    text = (job.job_description or "") + " " + (job.location_text or "")
    lower = text.lower()
    return any(phrase in lower for phrase in CLOSED_ROLE_PHRASES)


def _format_learned_preferences() -> str:
    """Load learned preferences and format for prompt. Cap at 30 entries to avoid bloat."""
    prefs = load_preferences(Path(LEARNED_PREFERENCES_PATH))
    reject = prefs.get("reject", [])[:15]
    exception = prefs.get("exception", [])[:15]
    notes = prefs.get("notes", [])[:10]
    if not reject and not exception and not notes:
        return ""
    lines = []
    if reject:
        lines.append(f"Reject these companies: {', '.join(reject)}")
    if exception:
        lines.append(f"Exceptions (override category rules): {', '.join(exception)}")
    if notes:
        for n in notes:
            lines.append(f"- {n}")
    return "Learned from your feedback:\n" + "\n".join(lines) + "\n\n"


def build_prompt(jobs: list[Job]) -> str:
    learned = _format_learned_preferences()
    return f"""
You are a job-search agent analyzing job postings for a candidate.

Profile:
{PROFILE}
{learned}
Decision rules:
- TRUE MATCH: Strong fit for 0-1/greenfield, founding TPM/Product Ops, operating model transformation, SDLC/PDLC improvement, AI adoption/enablement
- MONITOR: Partial fit, some good signals but missing key elements
- REJECT: Infrastructure, platform, architecture, migrations, SRE/DevOps, implementation, onboarding, professional services, compliance/regulatory/legal/GRC, defense/military, crypto/blockchain/Web3, government sector, employer Remote Hunter, posted salary significantly below candidate minimum (see profile), large enterprise/big tech (Microsoft, Google, Amazon, Oracle, Meta, Apple, Salesforce, IBM, etc.) — EXCEPT Netflix, Zillow (see profile), reposted jobs (e.g. "Reposted 3 days ago" in location/date — too late to apply), job description includes "No longer accepting applications" (role is closed). ALSO REJECT any role that matches the patterns in "Learned from your feedback" above — apply those patterns even when the job has other positive signals.

Jobs to analyze:
{jobs}

Return ONLY valid JSON in this EXACT format:
{{
  "true_matches": [
    {{
      "url": "https://...",
      "bucket": "true_match",
      "why": ["reason 1", "reason 2"],
      "what_to_do_next": "Apply immediately"
    }}
  ],
  "monitor": [
    {{
      "url": "https://...",
      "bucket": "monitor",
      "why": ["partial fit reason"],
      "what_to_do_next": "Watch for updates"
    }}
  ],
  "rejects": [
    {{
      "url": "https://...",
      "bucket": "reject",
      "why": ["rejection reason"],
      "what_to_do_next": "Skip"
    }}
  ],
  "notes": ["observation 1", "observation 2"]
}}

IMPORTANT:
- bucket: MUST be exactly "true_match", "monitor", or "reject"
- why: array of 2-4 strings explaining the decision
- what_to_do_next: short action recommendation
- Put ALL jobs into one of the three buckets (no numeric scoring)
- Entity rules override category rules: e.g. "reject large enterprises" (category) vs "Netflix is exception" (entity) — for Netflix, the entity exception wins
- If a job matches a rejection pattern in "Learned from your feedback" (e.g. project-level not program-level, hands-on data flows/SQL/JSON), REJECT it — do not override with positive signals like salary or AI focus
"""


def rank_jobs(jobs: list[Job]) -> tuple[AgentDigest, str]:
    MAX_JOBS_PER_LLM_CALL = 10
    MAX_JOB_DESCRIPTION_CHARS = 6000

    # v1 contract: only score rows that have been fetched from the job page
    eligible = [j for j in jobs if j.metadata.get("fetch_status") == "fetched"]

    skipped = len(jobs) - len(eligible)
    if skipped:
        print(f"[rank_jobs] Skipping {skipped} jobs not fetched yet (fetch_status != 'fetched').")

    # Auto-reject closed roles (e.g. "No longer accepting applications") before LLM
    closed, to_score = [], []
    for j in eligible:
        if _is_closed_role(j):
            closed.append(j)
        else:
            to_score.append(j)
    if closed:
        print(f"[rank_jobs] Auto-rejecting {len(closed)} closed roles (no longer accepting applications).")

    # Build auto-rejects for closed roles
    auto_rejects = [
        ScoredJob(
            url=j.url,
            bucket="reject",
            why=["Role is closed: no longer accepting applications"],
            what_to_do_next="Skip",
        )
        for j in closed
    ]

    if not to_score:
        empty = AgentDigest(
            true_matches=[],
            monitor=[],
            rejects=auto_rejects,
            notes=["No fetched jobs available to score yet."] if not closed else [],
        )
        return empty, ""

    all_true_matches = []
    all_monitor = []
    all_rejects = list(auto_rejects)
    all_notes = []
    last_raw = ""

    for i in range(0, len(to_score), MAX_JOBS_PER_LLM_CALL):
        batch = []
        for j in to_score[i : i + MAX_JOBS_PER_LLM_CALL]:
            j_copy = j.model_copy()
            if j_copy.job_description:
                j_copy.job_description = j_copy.job_description[:MAX_JOB_DESCRIPTION_CHARS]
            batch.append(j_copy)

        prompt = build_prompt(batch)

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        raw = resp.output_text
        last_raw = raw
        cleaned = raw.strip()

        # Handle ```json ... ``` wrappers
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()

        # Remove control characters that break JSON parsing
        import re
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)

        digest = AgentDigest.model_validate_json(cleaned)
        if isinstance(digest.notes, str):
            digest.notes = [digest.notes]

        all_true_matches.extend(digest.true_matches)
        all_monitor.extend(digest.monitor)
        all_rejects.extend(digest.rejects)
        all_notes.extend(digest.notes)

    merged = AgentDigest(
        true_matches=all_true_matches,
        monitor=all_monitor,
        rejects=all_rejects,
        notes=all_notes,
    )

    return merged, last_raw
