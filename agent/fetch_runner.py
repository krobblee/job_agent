from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx
from bs4 import BeautifulSoup  # if you don’t have this installed, we’ll swap to stdlib

from agent.sheets_client import SheetsClient, utc_now_iso

# v1 locked constants
MAX_FETCH_ATTEMPTS = 3


@dataclass(frozen=True)
class FetchConfig:
    per_url_timeout_seconds: int = 20
    total_run_budget_seconds: int = 120
    max_rows_per_run: int = 25  # safety


RETRYABLE_STATUSES = {"pending", "failed", "timeout"}


def _extract_minimal(html: str) -> Tuple[str, str, str, str]:
    """
    Returns: (role_title, company, location, job_description)

    v1: minimal heuristic extraction. We only require role_title OR job_description to be non-empty.
    """
    soup = BeautifulSoup(html, "html.parser")

    title = (soup.title.get_text(strip=True) if soup.title else "").strip()

    # Very lightweight fallback description: concatenate visible text from main/article if present
    main = soup.find("main") or soup.find("article") or soup.body
    desc = ""
    if main:
        desc = " ".join(main.get_text(" ", strip=True).split())
        # keep it bounded; sheet has scan-friendly summary later
        desc = desc[:6000]

    # Company/location are best-effort for now
    company = ""
    location = ""

    return title, company, location, desc


def _fetch_url(client: httpx.Client, url: str, timeout_s: int) -> str:
    resp = client.get(url, timeout=timeout_s, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)"
    })
    resp.raise_for_status()
    return resp.text


def run_fetch_once(sheet: SheetsClient, cfg: FetchConfig) -> int:
    """
    Fetches up to cfg.max_rows_per_run eligible rows and updates the Sheet in-place.
    Returns number of rows attempted.
    """
    start = time.time()
    records = sheet.get_all_records()
    row_index = sheet.build_row_index(key_col="job_url")

    attempted = 0

    with httpx.Client() as client:
        for rec in records:
            if attempted >= cfg.max_rows_per_run:
                break

            url = (rec.get("job_url") or "").strip()
            if not url:
                continue

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
            if elapsed >= cfg.total_run_budget_seconds:
                # mark remaining retryable rows as timeout? v1 says timeout can mean run budget exceeded.
                # We only update the current row as timeout; remaining rows will be picked up next run.
                break

            row_num = row_index.get(url)
            if not row_num:
                continue  # should not happen; defensive

            attempted += 1

            now = utc_now_iso()
            sheet.update_row_cells(row_num, {
                "fetch_attempts": str(attempts + 1),
                "last_fetch_at": now,
                "fetch_error": "",
            })

            try:
                html = _fetch_url(client, url, cfg.per_url_timeout_seconds)
            except httpx.TimeoutException:
                sheet.update_row_cells(row_num, {"fetch_status": "timeout", "fetch_error": "timeout"})
                continue
            except Exception as e:
                sheet.update_row_cells(row_num, {"fetch_status": "failed", "fetch_error": f"http_error:{type(e).__name__}"})
                continue

            try:
                role_title, company, location, job_desc = _extract_minimal(html)
            except Exception as e:
                sheet.update_row_cells(row_num, {"fetch_status": "failed", "fetch_error": f"parse_error:{type(e).__name__}"})
                continue

            if not role_title and not job_desc:
                sheet.update_row_cells(row_num, {"fetch_status": "failed", "fetch_error": "parse_empty"})
                continue

            # v1 fetched: write extracted fields
            summary = job_desc[:500]  # v1: simple, deterministic, bounded

            updates: Dict[str, Any] = {
                "fetch_status": "fetched",
                "role_title": role_title,
                "company": company,
                "location": location,
                "job_description": job_desc,
                "job_summary": summary,
            }
            sheet.update_row_cells(row_num, updates)


    return attempted
