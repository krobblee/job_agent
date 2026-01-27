from __future__ import annotations

from typing import Dict, List

from agent.sheets_client import SheetConfig, SheetsClient, utc_now_iso

# v1 contract constants
MAX_FETCH_ATTEMPTS = 3

SHEET_ID = "1mGVfJZuQzfIEtIbqnpxyh9UajHZ8b9JA77lXpR2hOgo"


def upsert_pending(sheet: SheetsClient, job_urls: List[str], source: str = "linkedin") -> None:
    index = sheet.build_row_index(key_col="job_url")

    now = utc_now_iso()

    for url in job_urls:
        url = (url or "").strip()
        if not url:
            continue

        if url in index:
            # Existing row: just bump last_seen_at
            row_num = index[url]
            sheet.update_row_cells(row_num, {"last_seen_at": now})
            continue

        # New row: create with v1-resumable fields initialized
        row: Dict[str, str] = {
            "job_url": url,
            "source": source,
            "date_received": now,
            "fetch_status": "pending",
            "fetch_attempts": "0",
            "fetch_error": "",
            "last_fetch_at": "",
            "last_seen_at": now,
            # leave remaining fields blank until fetch/extract
            "company": "",
            "role_title": "",
            "location": "",
            "apply_url": "",
            "job_description": "",
            "job_summary": "",
        }
        sheet.append_row_dict(row)

        # Update in-memory index so duplicates in this run don’t append twice
        index[url] = sheet.build_row_index(key_col="job_url").get(url, -1)


def main():
    cfg = SheetConfig(sheet_id=SHEET_ID, worksheet_title="Sheet1")
    sheet = SheetsClient(cfg)

    # TODO: replace this with real URLs from your Gmail extractor once wired
    sample_urls = [
        "https://www.linkedin.com/jobs/view/123456789/",
    ]

    upsert_pending(sheet, sample_urls, source="linkedin")
    print("Upsert complete")


if __name__ == "__main__":
    main()
