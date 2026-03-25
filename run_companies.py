"""
Companies pipeline: Company List → job board discovery → Company Jobs → Fetch → Score.

Reads Company List (company, company_url, career_site_url). **Expected:** `career_site_url`
is the direct hosted ATS job board URL (Ashby, Greenhouse, Lever, Gem, etc.) where open
roles are listed—not the marketing site's generic /careers page. If that URL fails,
the pipeline may fall back to `company_url` to find a careers link (less reliable).

Pipeline: Read Company List → Discover jobs → Upsert to Company Jobs → Fetch → Score → Prune rejects
"""

from __future__ import annotations

from typing import List

from agent.company_discovery import CompanyJob, discover_jobs_for_company
from agent.fetch_client import BrowserFetcher
from agent.fetch_manager import FetchConfig, FetchManager
from agent.scorer import rank_jobs
from agent.sheet_client import SheetClient, SheetConfig
from config import (
    COMPANIES_JOBS_WORKSHEET,
    COMPANIES_LIST_WORKSHEET,
    SHEET_ID,
)
from models import Job
from scripts.company_upsert import upsert_company_jobs
from scripts.prune_company_jobs_rejects import prune_rejected_company_job_rows


def _get_company_list_with_rows(sheet: SheetClient) -> List[tuple[int, str, str, str]]:
    """
    Read Company List tab. Returns list of (row_num, company, company_url, career_site_url).
    Includes rows with either column set; prefer `career_site_url` = job board URL (see README/SETUP).
    """
    values = sheet.get_all_values()
    if not values or len(values) < 2:
        return []

    try:
        company_idx = sheet._header_index("company")
        company_url_idx = sheet._header_index("company_url")
        career_idx = sheet._header_index("career_site_url")
    except ValueError:
        return []

    result = []
    for row_num, row in enumerate(values[1:], start=2):
        company = (row[company_idx] if company_idx < len(row) else "").strip()
        company_url = (row[company_url_idx] if company_url_idx < len(row) else "").strip()
        career_url = (row[career_idx] if career_idx < len(row) else "").strip()
        if company_url or career_url:
            result.append((row_num, company, company_url, career_url))
    return result


def _build_jobs_from_records(records: List[dict]) -> List[Job]:
    """Build Job objects from Sheet records (fetch_status='fetched')."""
    jobs = []
    for rec in records:
        if rec.get("fetch_status") == "fetched":
            job = Job(
                source=rec.get("source", "companies"),
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
    print("=== Companies Pipeline ===\n")

    list_sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=COMPANIES_LIST_WORKSHEET))
    jobs_sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=COMPANIES_JOBS_WORKSHEET))

    # 1. Read Company List
    print("=== Company List ===")
    companies = _get_company_list_with_rows(list_sheet)
    if not companies:
        print("No companies in Company List (add rows with career_site_url = job board URL, or company_url).")
        return
    print(f"Found {len(companies)} companies to scrape\n")

    # 2. Discover jobs from each company
    print("=== Discovery ===")
    all_jobs: List[CompanyJob] = []
    error_updates: dict[int, str] = {}

    for i, (row_num, company, company_url, career_url) in enumerate(companies):
        print(f"  [{i+1}/{len(companies)}] {company or 'Unknown'}...", end=" ", flush=True)
        jobs, err = discover_jobs_for_company(
            company_name=company,
            company_url=company_url,
            career_site_url=career_url,
            timeout=15,
            delay=1.5,
        )
        if err:
            print(f"✗ {err}")
            error_updates[row_num] = err
        else:
            print(f"✓ {len(jobs)} jobs")
            all_jobs.extend(jobs)

    # 3. Update last_error for failed companies
    if error_updates:
        list_sheet.batch_update_rows({row: {"last_error": msg} for row, msg in error_updates.items()})
        print(f"\n  Updated last_error for {len(error_updates)} companies\n")

    # 4. Upsert to Company Jobs
    if not all_jobs:
        print("No jobs discovered. Check career_site_url (job board link), last_error, or SETUP.md.")
        jobs_sheet.refresh_worksheet()
        pruned = prune_rejected_company_job_rows(jobs_sheet)
        if pruned:
            print(f"✓ Removed {pruned} rejected row(s) from Company Jobs\n")
        return

    print("=== Sheet Write (Company Jobs) ===")
    appended = upsert_company_jobs(jobs_sheet, all_jobs)
    print(f"✓ Appended {appended} new jobs ({len(all_jobs)} total discovered, deduped)\n")

    # 5. Fetch pending job pages
    print("=== Fetching ===")
    jobs_sheet.refresh_worksheet()
    # Use Playwright for fetch — Company Jobs URLs (Gem, Darwinbox, etc.) are often JS-rendered
    browser_fetcher = BrowserFetcher(headless=True)
    fetch_manager = FetchManager(jobs_sheet, FetchConfig(max_rows_per_run=50), fetch_client=browser_fetcher)
    attempted = fetch_manager.fetch_pending_jobs()
    print(f"✓ Fetched {attempted} jobs\n")

    # 6. Score fetched jobs
    print("=== Scoring ===")
    jobs_sheet.refresh_worksheet()
    records = jobs_sheet.get_all_records()
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
        updated = jobs_sheet.write_scoring_results(all_scored)
        print(f"\n✓ Updated {updated} jobs with scores\n")
    else:
        print("No jobs ready to score yet\n")

    # 7. Drop rejected rows so Company Jobs stays true_match + monitor + pending only
    jobs_sheet.refresh_worksheet()
    pruned = prune_rejected_company_job_rows(jobs_sheet)
    if pruned:
        print(f"✓ Removed {pruned} rejected row(s) from Company Jobs\n")


if __name__ == "__main__":
    main()
