"""
Cleanup script to normalize /comm/ URLs in the Google Sheet.

Finds all rows with linkedin.com/comm/jobs/view/ URLs and:
1. Normalizes URL to remove /comm/ path
2. Resets fetch_status to "pending" for refetch
3. Clears old fetch data (attempts, errors, etc.)

This allows previously failed /comm/ URLs to be refetched successfully.
"""
from __future__ import annotations

import os
import sys

# Add parent directory to path so we can import from agent/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.sheet_client import SheetClient, SheetConfig
from config import SHEET_ID


def normalize_comm_urls() -> None:
    """Normalize all /comm/ URLs in the Sheet."""
    sheet = SheetClient(SheetConfig(sheet_id=SHEET_ID))
    
    print("=== URL Normalization Cleanup ===\n")
    
    # Get all records
    records = sheet.get_all_records()
    row_index = sheet.build_row_index(key_col="job_url")
    
    # Find URLs with /comm/ that need normalization
    to_normalize = []
    for rec in records:
        url = (rec.get("job_url") or "").strip()
        if "/comm/jobs/view/" in url:
            to_normalize.append((url, rec))
    
    print(f"Found {len(to_normalize)} URLs with /comm/ to normalize\n")
    
    if not to_normalize:
        print("✓ No URLs need normalization")
        return
    
    # Batch updates
    batch_updates = {}
    
    for url, rec in to_normalize:
        normalized_url = url.replace("/comm/jobs/view/", "/jobs/view/")
        row_num = row_index.get(url)
        
        if not row_num:
            continue
        
        print(f"Normalizing row {row_num}:")
        print(f"  Old: {url}")
        print(f"  New: {normalized_url}\n")
        
        # Update URL and reset fetch state for refetch
        batch_updates[row_num] = {
            "job_url": normalized_url,
            "fetch_status": "pending",
            "fetch_attempts": "0",
            "fetch_error": "",
            "last_fetch_at": "",
            # Clear old fetched data so it gets refetched
            "role_title": "",
            "company": "",
            "location": "",
            "job_description": "",
            "job_summary": "",
            # Clear old scoring data
            "agent_bucket": "",
            "agent_reasoning": "",
        }
    
    # Write all updates
    if batch_updates:
        print(f"Writing {len(batch_updates)} normalized URLs to Sheet...")
        sheet.batch_update_rows(batch_updates)
        print(f"✓ Normalized {len(batch_updates)} URLs")
        print("\nThese jobs will be refetched on the next agent run.")


if __name__ == "__main__":
    normalize_comm_urls()
