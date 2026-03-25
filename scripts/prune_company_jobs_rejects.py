"""
Delete Company Jobs rows where agent_bucket is reject (Company Jobs tab only).

Does not change Email or Aggregator. Safe to run standalone after rescoring.

Usage:
  python3 scripts/prune_company_jobs_rejects.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.sheet_client import SheetClient, SheetConfig
from config import COMPANIES_JOBS_WORKSHEET, SHEET_ID


def prune_rejected_company_job_rows(sheet: SheetClient) -> int:
    """
    Remove rows with agent_bucket == reject (case-insensitive). Never deletes row 1 (header).

    Returns:
        Number of rows deleted.
    """
    sheet.refresh_worksheet()
    values = sheet.get_all_values()
    if len(values) < 2:
        return 0
    try:
        bucket_idx = sheet._header_index("agent_bucket")
    except ValueError:
        return 0

    to_delete: list[int] = []
    for row_num, row in enumerate(values[1:], start=2):
        if bucket_idx >= len(row):
            continue
        if (row[bucket_idx] or "").strip().lower() == "reject":
            to_delete.append(row_num)

    if not to_delete:
        return 0
    return sheet.delete_rows_at(to_delete)


def main() -> None:
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID, worksheet_title=COMPANIES_JOBS_WORKSHEET))
    n = prune_rejected_company_job_rows(sheet)
    if n:
        print(f"Removed {n} rejected row(s) from Company Jobs.")
    else:
        print("No rejected rows to remove (or missing agent_bucket column).")


if __name__ == "__main__":
    main()
