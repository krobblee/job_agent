"""
Company Jobs upsert: append jobs discovered from Company List to Company Jobs tab.

Discovery is expected to start from the job board URL in Company List `career_site_url`
(see README / SETUP). Schema matches Aggregator (source, first_seen, company, role_title,
job_url, location, fetch_status, …). source="companies". Deduplicates by job_url.
"""

from __future__ import annotations

from typing import Dict, List

from agent.company_discovery import CompanyJob
from agent.sheet_client import SheetClient, utc_now_iso


def upsert_company_jobs(sheet: SheetClient, jobs: List[CompanyJob]) -> int:
    """
    Append new company jobs to the sheet. Skips URLs already present.

    Args:
        sheet: SheetClient configured for Company Jobs worksheet
        jobs: List of CompanyJob (url, company)

    Returns:
        Number of new rows appended
    """
    index = sheet.build_row_index(key_col="job_url")
    now = utc_now_iso()

    existing_urls = set(index.keys())
    rows_to_append: List[Dict[str, str]] = []

    for job in jobs:
        url = (job.url or "").strip()
        if not url or url in existing_urls:
            continue

        rows_to_append.append({
            "source": "companies",
            "first_seen": now,
            "company": job.company or "",
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
        })
        existing_urls.add(url)

    if rows_to_append:
        sheet.append_rows_dict(rows_to_append)

    return len(rows_to_append)
