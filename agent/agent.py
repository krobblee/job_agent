from __future__ import annotations

from agent.config import PROFILE, client
from agent.models import AgentDigest, Job


def build_prompt(jobs: list[Job]) -> str:
    # Intentionally preserving the existing v0 prompt verbatim.
    return f"""
You are a job-search agent.

From noisy email-alert links, identify which URLs are real job postings
and rank the best matches for the candidate.
Decision rules:
- Immediately reject roles that are primarily: infrastructure, platform, architecture, migrations, SRE/DevOps, cloud migrations.
- Immediately reject roles that are primarily: implementation, onboarding, professional services, customer delivery, integrations as a service.
- Immediately reject compliance-heavy / regulatory / legal / GRC / risk roles.

Strong positives:
- Mentions of: 0-1, greenfield, new product build, ambiguous environment, founding TPM/Product Ops, operating model, workflow transformation, SDLC/PDLC improvement, AI adoption, agents, AI tooling enablement, org design/RACI.

Profile:
{PROFILE}

Inputs:
{jobs}

Return valid JSON with:
- top: up to 10 ranked roles
- rejects: URLs rejected
- notes: suggestions to improve results
"""


def rank_jobs(jobs: list[Job]) -> tuple[AgentDigest, str]:
    MAX_JOBS_PER_LLM_CALL = 10
    MAX_JOB_DESCRIPTION_CHARS = 6000

    # v1 contract: only score rows that have been fetched from the job page
    eligible = [j for j in jobs if getattr(j, "fetch_status", None) == "fetched"]

    skipped = len(jobs) - len(eligible)
    if skipped:
        print(f"[rank_jobs] Skipping {skipped} jobs not fetched yet (fetch_status != 'fetched').")

    if not eligible:
        empty = AgentDigest(top=[], rejects=[], notes=["No fetched jobs available to score yet."])
        return empty, ""

    all_top = []
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

        digest = AgentDigest.model_validate_json(cleaned)
        if isinstance(digest.notes, str):
            digest.notes = [digest.notes]

        all_top.extend(digest.top)
        all_rejects.extend(digest.rejects)
        all_notes.extend(digest.notes)

    merged = AgentDigest(
        top=all_top[:10],
        rejects=list(dict.fromkeys(all_rejects)),
        notes=all_notes,
    )

    return merged, last_raw

