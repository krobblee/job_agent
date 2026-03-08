"""
Greenhouse-specific upsert to the Greenhouse tab.

Schema: source, first_seen, company, role_title, job_url, location, department,
        fetch_status, fetch_attempts, last_fetch_at, fetch_error,
        job_description, job_summary, agent_bucket, agent_reasoning

Add a "source" column to your Greenhouse tab if missing (greenhouse | swooped).
"""

from __future__ import annotations

from typing import Dict, List

from agent.greenhouse_discovery import GreenhouseJob
from agent.sheet_client import SheetClient, utc_now_iso


def upsert_greenhouse_jobs(sheet: SheetClient, jobs: List[GreenhouseJob]) -> int:
    """
    Append new Greenhouse jobs to the sheet. Skips URLs already present.

    Args:
        sheet: SheetClient configured for Greenhouse worksheet
        jobs: List of GreenhouseJob (url + company_slug)

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

        row: Dict[str, str] = {
            "source": "greenhouse",
            "first_seen": now,
            "company": job.company_slug,
            "role_title": "",
            "job_url": url,
            "location": "",
            "department": "",
            "fetch_status": "pending",
            "fetch_attempts": "0",
            "last_fetch_at": "",
            "fetch_error": "",
            "job_description": "",
            "job_summary": "",
            "agent_bucket": "",
            "agent_reasoning": "",
        }
        sheet.append_row_dict(row)
        index[url] = next_row
        next_row += 1
        appended += 1

    return appended
