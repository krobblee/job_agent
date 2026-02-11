from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

import httpx

from agent.fetch_client import FetchClient, HttpFetcher
from agent.page_parser import extract_job_info
from agent.sheet_client import SheetClient, utc_now_iso

# v1 locked constants
MAX_FETCH_ATTEMPTS = 3


@dataclass(frozen=True)
class FetchConfig:
    per_url_timeout_seconds: int = 20
    total_run_budget_seconds: int = 120
    max_rows_per_run: int = 25  # safety


RETRYABLE_STATUSES = {"pending", "failed", "timeout"}


class FetchManager:
    """
    Manages the fetch lifecycle for job postings.
    
    Respects v1 contract:
    - Max 3 fetch attempts per URL
    - Explicit fetch_status states: pending/fetched/failed/timeout
    - Batch updates to avoid rate limits
    - Resumable across runs
    """
    
    def __init__(
        self,
        sheet: SheetClient,
        config: FetchConfig,
        fetch_client: FetchClient | None = None,
    ):
        """
        Args:
            sheet: SheetClient instance for reading/writing job data
            config: FetchConfig with timeout and batch size settings
            fetch_client: Optional custom fetch client. Defaults to HttpFetcher.
        """
        self.sheet = sheet
        self.config = config
        self.fetch_client = fetch_client or HttpFetcher()
    
    
    def fetch_pending_jobs(self) -> int:
        """
        Fetch up to config.max_rows_per_run eligible jobs and update the Sheet.
        
        Uses batch updates to avoid rate limits.
        
        Returns:
            Number of jobs attempted
        """
        start = time.time()
        # Refresh worksheet to clear any caching after previous writes
        self.sheet.refresh_worksheet()
        records = self.sheet.get_all_records()
        row_index = self.sheet.build_row_index(key_col="job_url")
        
        attempted = 0
        batch_updates: Dict[int, Dict[str, Any]] = {}  # Collect all updates for batch write
        
        def add_update(row_num: int, updates: Dict[str, Any]) -> None:
            """Helper to merge updates for a row."""
            if row_num not in batch_updates:
                batch_updates[row_num] = {}
            batch_updates[row_num].update(updates)
        
        # Main fetch loop (no longer needs httpx.Client context)
        pending_count = 0
        for rec in records:
            if attempted >= self.config.max_rows_per_run:
                    break
            
            original_url = (rec.get("job_url") or "").strip()
            if not original_url:
                continue
            
            # Debug: Count how many pending jobs we see
            if rec.get("fetch_status") in RETRYABLE_STATUSES:
                pending_count += 1
            
            status = (rec.get("fetch_status") or "pending").strip()
            if status not in RETRYABLE_STATUSES:
                continue
            
            attempts_str = str(rec.get("fetch_attempts") or "0")
            try:
                attempts = int(attempts_str)
            except ValueError:
                attempts = 0
            
            if attempts >= MAX_FETCH_ATTEMPTS:
                continue
            
            # run budget check (overall)
            elapsed = time.time() - start
            if elapsed >= self.config.total_run_budget_seconds:
                break
            
            # Get row_num using ORIGINAL URL (before normalization)
            row_num = row_index.get(original_url)
            if not row_num:
                continue  # should not happen; defensive
            
            # Normalize LinkedIn URLs for fetching: strip /comm/ path to avoid anti-scraping
            # linkedin.com/comm/jobs/view/123 -> linkedin.com/jobs/view/123
            fetch_url = original_url.replace("/comm/jobs/view/", "/jobs/view/")
            
            attempted += 1
            
            now = utc_now_iso()
            # Collect initial update (increment attempts)
            add_update(row_num, {
                "fetch_attempts": str(attempts + 1),
                "last_fetch_at": now,
                "fetch_error": "",
            })
            
            try:
                html = self.fetch_client.fetch(fetch_url, self.config.per_url_timeout_seconds)
            except httpx.TimeoutException:
                add_update(row_num, {"fetch_status": "timeout", "fetch_error": "timeout"})
                continue
            except Exception as e:
                add_update(row_num, {"fetch_status": "failed", "fetch_error": f"http_error:{type(e).__name__}"})
                continue
            
            try:
                role_title, company, location, job_desc = extract_job_info(html)
            except Exception as e:
                add_update(row_num, {"fetch_status": "failed", "fetch_error": f"parse_error:{type(e).__name__}"})
                continue
            
            if not role_title and not job_desc:
                add_update(row_num, {"fetch_status": "failed", "fetch_error": "parse_empty"})
                continue
            
            # v1 fetched: collect extracted fields
            summary = job_desc[:500]  # v1: simple, deterministic, bounded
            
            add_update(row_num, {
                "fetch_status": "fetched",
                "role_title": role_title,
                "company": company,
                "location": location,
                "job_description": job_desc,
                "job_summary": summary,
            })
        
        # Batch write all updates at once
        print(f"  Debug: Saw {pending_count} total pending jobs, attempted {attempted}")
        if batch_updates:
            print(f"  Debug: Writing {len(batch_updates)} row updates to Sheet")
            self.sheet.batch_update_rows(batch_updates)
        else:
            print("  Debug: No batch updates to write!")
        
        return attempted
