from __future__ import annotations

import os
import sys
from typing import List

from agent.discovery import GmailDiscoverySource
from agent.fetch_client import HttpFetcher
from agent.fetch_manager import FetchConfig, FetchManager
from agent.scorer import rank_jobs
from agent.sheet_client import SheetClient, SheetConfig
from config import SHEET_ID
from models import Job

# Import upsert_pending logic
sys.path.insert(0, os.path.dirname(__file__))
from scripts.upsert_pending import upsert_pending


def _build_jobs_from_records(records: List[dict]) -> List[Job]:
    """
    Build Job objects from Sheet records.
    
    Only includes jobs with fetch_status='fetched'.
    """
    jobs = []
    for rec in records:
        if rec.get("fetch_status") == "fetched":
            job = Job(
                source=rec.get("source", "unknown"),
                url=rec.get("job_url", ""),
                title=rec.get("role_title"),
                company=rec.get("company"),
                location_text=rec.get("location"),
                job_description=rec.get("job_description"),
            )
            job.metadata["fetch_status"] = "fetched"
            jobs.append(job)
    return jobs


def main() -> None:
    """
    Main job agent pipeline orchestrator.
    
    Pipeline: Discovery → Sheet write → Fetch → Score → Sheet update
    """
    # 1. Initialize Sheet (source of truth)
    print("=== Initializing Sheet ===")
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID))
    print("✓ Connected\n")

    # 2. Discover jobs from Gmail
    print("=== Discovery ===")
    query = os.getenv("GMAIL_QUERY", "from:(jobalerts-noreply@linkedin.com) newer_than:3d")
    discovery = GmailDiscoverySource(query=query, max_results=15)
    jobs = discovery.discover_jobs()
    print(f"✓ Discovered {len(jobs)} jobs\n")

    # 3. Write discovered URLs to Sheet
    print("=== Sheet Write ===")
    urls = [j.url for j in jobs]
    upsert_pending(sheet, urls, source="gmail")
    print(f"✓ Upserted {len(urls)} URLs\n")

    # 4. Fetch job page content (trying normalized URLs first)
    print("=== Fetching ===")
    http_fetcher = HttpFetcher(delay_between_requests=2.0)  # Slower to be nice to LinkedIn
    fetch_manager = FetchManager(sheet, FetchConfig(max_rows_per_run=25), fetch_client=http_fetcher)
    attempted = fetch_manager.fetch_pending_jobs()
    print(f"✓ Fetched {attempted} jobs\n")

    # 5. Score fetched jobs
    print("=== Scoring ===")
    records = sheet.get_all_records()
    fetched_jobs = _build_jobs_from_records(records)
    print(f"Found {len(fetched_jobs)} jobs ready to score")

    if fetched_jobs:
        digest, raw = rank_jobs(fetched_jobs)
        
        print(f"\n=== TRUE MATCHES ({len(digest.true_matches)}) ===")
        for job in digest.true_matches:
            print(f"\n✓ {job.url}")
            for reason in job.why:
                print(f"  • {reason}")
            print(f"  → {job.what_to_do_next}")
        
        print(f"\n=== MONITOR ({len(digest.monitor)}) ===")
        for job in digest.monitor:
            print(f"\n⚠ {job.url}")
            for reason in job.why:
                print(f"  • {reason}")
        
        print(f"\n=== REJECTS ({len(digest.rejects)}) ===")
        for job in digest.rejects:
            print(f"\n✗ {job.url}")
            print(f"  Reason: {job.why[0] if job.why else 'Not a good fit'}")
        
        # Write scores to Sheet
        print("\n=== Writing Scores to Sheet ===")
        all_scored = digest.true_matches + digest.monitor + digest.rejects
        updated = sheet.write_scoring_results(all_scored)
        print(f"✓ Updated {updated} jobs with scores\n")
    else:
        print("No jobs ready to score yet\n")


if __name__ == "__main__":
    main()
