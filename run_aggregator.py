"""
Aggregator pipeline: startup aggregators + Swooped → Sheet → Fetch → Score.

Discovers jobs from aggregator pages (e.g. topstartups.io) and Swooped,
diffs against previous snapshot for freshness, appends new jobs to the
Aggregator tab. Then fetches job pages and scores them.

Pipeline: Discovery → (optional) Upsert new → Save snapshot → Fetch → Score
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from agent.fetch_client import HttpFetcher
from agent.fetch_manager import FetchConfig, FetchManager
from agent.greenhouse_discovery import discover_greenhouse_jobs
from agent.swooped_discovery import discover_swooped_jobs
from agent.scorer import rank_jobs
from agent.sheet_client import SheetClient, SheetConfig
from config import (
    AGGREGATOR_SNAPSHOT_DIR,
    AGGREGATOR_WORKSHEET,
    SHEET_ID,
    STARTUP_URLS_PATH,
    SWOOPED_URLS_PATH,
)
from models import Job
from scripts.aggregator_snapshot import load_previous_snapshot, save_snapshot
from scripts.aggregator_upsert import upsert_aggregator_jobs
from scripts.swooped_upsert import upsert_swooped_jobs


def _build_jobs_from_records(records: List[dict]) -> List[Job]:
    """Build Job objects from Sheet records (fetch_status='fetched')."""
    jobs = []
    for rec in records:
        if rec.get("fetch_status") == "fetched":
            job = Job(
                source=rec.get("source", "greenhouse"),
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
    print("=== Aggregator Pipeline ===\n")

    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=AGGREGATOR_WORKSHEET))

    # 1. Discover jobs from aggregators (scraping)
    print("=== Aggregator Discovery ===")
    aggregator_jobs = discover_greenhouse_jobs(
        seed_urls_path=STARTUP_URLS_PATH,
        timeout=15,
        delay_between_requests=2.0,
    )
    if aggregator_jobs:
        current_urls = {j.url for j in aggregator_jobs}
        print(f"\nAggregator scraping: {len(aggregator_jobs)} jobs")
    else:
        current_urls = set()
        print("\nAggregator scraping: 0 jobs")

    # 2. Discover Swooped jobs (always run — better quality, full descriptions)
    print("\n=== Swooped Discovery ===")
    swooped_jobs = discover_swooped_jobs(
        seed_urls_path=SWOOPED_URLS_PATH,
        timeout=30,
        delay_between_requests=2.0,
    )
    if swooped_jobs:
        print(f"  Found {len(swooped_jobs)} Swooped jobs")
        appended_swooped = upsert_swooped_jobs(sheet, swooped_jobs)
        print(f"✓ Appended {appended_swooped} new Swooped jobs (source=swooped)\n")
    else:
        print("  No Swooped jobs (or Swooped_URLs.txt empty)\n")

    # 3. Delta and upsert new aggregator jobs
    if aggregator_jobs:
        previous_urls = load_previous_snapshot(AGGREGATOR_SNAPSHOT_DIR)
        new_jobs = [j for j in aggregator_jobs if j.url not in previous_urls]
        print(f"Previous snapshot: {len(previous_urls)} aggregator URLs")
        print(f"New (fresh) aggregator jobs: {len(new_jobs)}\n")

        if new_jobs:
            print("=== Sheet Write (Aggregator) ===")
            appended = upsert_aggregator_jobs(sheet, new_jobs)
            print(f"✓ Appended {appended} new aggregator jobs\n")

        # Save snapshot (aggregator scraping only)
        eastern = ZoneInfo("America/New_York")
        save_snapshot(
            AGGREGATOR_SNAPSHOT_DIR,
            datetime.now(eastern).strftime("%Y-%m-%d"),
            list(current_urls),
        )
        print(f"✓ Snapshot saved ({len(current_urls)} aggregator URLs)\n")

    # Exit only if both sources found nothing
    if not aggregator_jobs and not swooped_jobs:
        print("No jobs discovered from aggregators or Swooped. Add URLs to data/Startup_URLs.txt and data/Swooped_URLs.txt")
        return

    # 4. Fetch pending job pages
    print("=== Fetching ===")
    http_fetcher = HttpFetcher(delay_between_requests=1.5)
    fetch_manager = FetchManager(sheet, FetchConfig(max_rows_per_run=25), fetch_client=http_fetcher)
    attempted = fetch_manager.fetch_pending_jobs()
    print(f"✓ Fetched {attempted} jobs\n")

    # 5. Score fetched jobs
    print("=== Scoring ===")
    records = sheet.get_all_records()
    fetched_jobs = _build_jobs_from_records(records)
    print(f"Found {len(fetched_jobs)} jobs ready to score")

    if fetched_jobs:
        digest, _ = rank_jobs(fetched_jobs)
        print(f"\n=== TRUE MATCHES ({len(digest.true_matches)}) ===")
        for job in digest.true_matches:
            print(f"  ✓ {job.url}")
        print(f"\n=== MONITOR ({len(digest.monitor)}) ===")
        for job in digest.monitor:
            print(f"  ⚠ {job.url}")
        print(f"\n=== REJECTS ({len(digest.rejects)}) ===")
        for job in digest.rejects:
            print(f"  ✗ {job.url}")

        all_scored = digest.true_matches + digest.monitor + digest.rejects
        updated = sheet.write_scoring_results(all_scored)
        print(f"\n✓ Updated {updated} jobs with scores\n")
    else:
        print("No jobs ready to score yet\n")


if __name__ == "__main__":
    main()
