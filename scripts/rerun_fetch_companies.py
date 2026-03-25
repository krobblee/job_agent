"""
Reset fetched Company Jobs to pending and re-run fetch with BrowserFetcher.
Useful after parser changes or when Gem/JS-rendered pages returned empty JDs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.fetch_client import BrowserFetcher
from agent.fetch_manager import FetchConfig, FetchManager
from agent.sheet_client import SheetConfig, SheetClient
from config import COMPANIES_JOBS_WORKSHEET, SHEET_ID


def main():
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=COMPANIES_JOBS_WORKSHEET))
    sheet.refresh_worksheet()

    records = sheet.get_all_records()
    row_index = sheet.build_row_index(key_col="job_url")
    batch_updates = {}

    for rec in records:
        if rec.get("fetch_status") == "fetched":
            url = (rec.get("job_url") or "").strip()
            if not url:
                continue
            row_num = row_index.get(url)
            if row_num:
                batch_updates[row_num] = {
                    "fetch_status": "pending",
                    "fetch_attempts": "0",
                }

    if batch_updates:
        print(f"Resetting {len(batch_updates)} fetched rows to pending...")
        sheet.batch_update_rows(batch_updates)
    else:
        print("No fetched rows to reset.")

    print("\nRunning fetch (BrowserFetcher for Gem/JS-rendered pages)...")
    browser_fetcher = BrowserFetcher(headless=True)
    fetch_manager = FetchManager(sheet, FetchConfig(max_rows_per_run=50), fetch_client=browser_fetcher)
    attempted = fetch_manager.fetch_pending_jobs()
    print(f"✓ Fetched {attempted} jobs")


if __name__ == "__main__":
    main()
