"""
Swooped-specific upsert to the Greenhouse tab.

Swooped jobs arrive with full description — no fetch step. We append with
fetch_status=fetched so they go straight to scoring.

Schema: same as Greenhouse, plus source="swooped" so you can filter by source.
Uses canonical Apply URL as job_url for deduplication.
"""

from __future__ import annotations

from typing import Dict, List

from agent.sheet_client import SheetClient, utc_now_iso
from agent.swooped_discovery import SwoopedJob


def upsert_swooped_jobs(sheet: SheetClient, jobs: List[SwoopedJob]) -> int:
    """
    Append new Swooped jobs to the sheet. Skips URLs already present.
    Appends with fetch_status=fetched (description from Swooped, no fetch needed).
    Sets source="swooped" so you can filter by source in the Sheet.

    Args:
        sheet: SheetClient configured for Greenhouse worksheet
        jobs: List of SwoopedJob (url, company, role_title, location, job_description)

    Returns:
        Number of new rows appended
    """
    index = sheet.build_row_index(key_col="job_url")
    now = utc_now_iso()
    appended = 0

    existing_urls = set(index.keys())
    next_row = max(index.values(), default=1) + 1

    for job in jobs:
        url = (job.url or "").strip()
        if not url or url in existing_urls:
            continue

        summary = (job.job_description or "")[:500]

        row: Dict[str, str] = {
            "source": "swooped",
            "first_seen": now,
            "company": job.company or "",
            "role_title": job.role_title or "",
            "job_url": url,
            "location": job.location or "",
            "department": "",
            "fetch_status": "fetched",  # No fetch needed — description from Swooped
            "fetch_attempts": "1",
            "last_fetch_at": now,
            "fetch_error": "",
            "job_description": job.job_description or "",
            "job_summary": summary,
            "agent_bucket": "",
            "agent_reasoning": "",
        }
        sheet.append_row_dict(row)
        index[url] = next_row
        next_row += 1
        appended += 1

    return appended
