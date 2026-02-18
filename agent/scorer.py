from __future__ import annotations

from config import PROFILE, client
from models import AgentDigest, ScoredJob, Job


def build_prompt(jobs: list[Job]) -> str:
    return f"""
You are a job-search agent analyzing job postings for a candidate.

Profile:
{PROFILE}

Decision rules:
- TRUE MATCH: Strong fit for 0-1/greenfield, founding TPM/Product Ops, operating model transformation, SDLC/PDLC improvement, AI adoption/enablement
- MONITOR: Partial fit, some good signals but missing key elements
- REJECT: Infrastructure, platform, architecture, migrations, SRE/DevOps, implementation, onboarding, professional services, compliance/regulatory/legal/GRC, defense/military, crypto/blockchain/Web3, government sector

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
"""


def rank_jobs(jobs: list[Job]) -> tuple[AgentDigest, str]:
    MAX_JOBS_PER_LLM_CALL = 10
    MAX_JOB_DESCRIPTION_CHARS = 6000

    # v1 contract: only score rows that have been fetched from the job page
    eligible = [j for j in jobs if j.metadata.get("fetch_status") == "fetched"]

    skipped = len(jobs) - len(eligible)
    if skipped:
        print(f"[rank_jobs] Skipping {skipped} jobs not fetched yet (fetch_status != 'fetched').")

    if not eligible:
        empty = AgentDigest(
            true_matches=[],
            monitor=[],
            rejects=[],
            notes=["No fetched jobs available to score yet."]
        )
        return empty, ""

    all_true_matches = []
    all_monitor = []
    all_rejects = []
    all_notes = []
    last_raw = ""

    for i in range(0, len(eligible), MAX_JOBS_PER_LLM_CALL):
        batch = []
        for j in eligible[i : i + MAX_JOBS_PER_LLM_CALL]:
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
