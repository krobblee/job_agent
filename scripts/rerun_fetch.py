"""
Reset fetched jobs to pending and re-run fetch.
Useful after parser changes (e.g. company/role extraction) to refresh sheet data.
"""
import sys
from pathlib import Path

# Add project root so "agent" module is findable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.fetch_manager import FetchConfig, FetchManager
from agent.fetch_client import HttpFetcher
from agent.sheet_client import SheetConfig, SheetClient
from config import LINKEDIN_WORKSHEET, SHEET_ID


def main():
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=LINKEDIN_WORKSHEET))
    sheet.refresh_worksheet()

    # Reset fetched rows to pending so they get re-fetched
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

    # Run fetch
    print("\nRunning fetch...")
    http_fetcher = HttpFetcher(delay_between_requests=2.0)
    fetch_manager = FetchManager(sheet, FetchConfig(max_rows_per_run=25), fetch_client=http_fetcher)
    attempted = fetch_manager.fetch_pending_jobs()
    print(f"✓ Fetched {attempted} jobs")


if __name__ == "__main__":
    main()
