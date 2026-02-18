"""
Greenhouse job discovery via startup aggregators.

Aggregators like topstartups.io/jobs list jobs with direct links to ATS (Greenhouse,
Ashby, Lever, etc.). We extract only Greenhouse job URLs from these pages.

Supported Greenhouse URL patterns:
  - boards.greenhouse.io/company/jobs/ID
  - job-boards.greenhouse.io/company/jobs/ID
  - job-boards.eu.greenhouse.io/company/jobs/ID
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class GreenhouseJob:
    """A discovered Greenhouse job with board context."""
    url: str
    company_slug: str


# Match Greenhouse job URLs: .../company/jobs/NUM
# Supports: boards.greenhouse.io, job-boards.greenhouse.io, job-boards.eu.greenhouse.io
GREENHOUSE_JOB_PATTERN = re.compile(
    r"https?://(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|job-boards\.eu\.greenhouse\.io)/([a-zA-Z0-9_-]+)/jobs/(\d+)",
    re.IGNORECASE,
)


def _load_seed_urls(path: str) -> List[str]:
    """Load aggregator URLs from file (one per line, skip comments and blank)."""
    p = Path(path)
    if not p.exists():
        return []
    urls = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def _extract_greenhouse_jobs_from_html(html: str, base_url: str) -> List[Tuple[str, str]]:
    """
    Extract Greenhouse job URLs and company slugs from HTML.
    
    Returns list of (job_url, company_slug). Normalizes URLs (no query params).
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()
    results: List[Tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        m = GREENHOUSE_JOB_PATTERN.search(full)
        if m:
            company_slug = m.group(1).lower()
            # Normalize: scheme + netloc + path, no query
            parsed = urlparse(full)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean_url not in seen:
                seen.add(clean_url)
                results.append((clean_url, company_slug))
    return results


def discover_greenhouse_jobs(
    seed_urls_path: str,
    timeout: int = 15,
    delay_between_requests: float = 2.0,
) -> List[GreenhouseJob]:
    """
    Scrape aggregator pages and extract direct Greenhouse job URLs.
    
    Aggregators like topstartups.io/jobs link directly to job pages
    (boards.greenhouse.io, job-boards.greenhouse.io, job-boards.eu.greenhouse.io).
    No need to visit company profiles or careers pages.
    
    Returns list of GreenhouseJob (url + company_slug).
    """
    seed_urls = _load_seed_urls(seed_urls_path)
    if not seed_urls:
        print("  No seed URLs in Startup_URLs.txt (or file missing)")
        return []

    print(f"  Scraping {len(seed_urls)} aggregator page(s)...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    all_jobs: List[GreenhouseJob] = []
    seen_urls: Set[str] = set()

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for i, url in enumerate(seed_urls):
            try:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                jobs = _extract_greenhouse_jobs_from_html(resp.text, url)
                new_count = sum(1 for u, _ in jobs if u not in seen_urls)
                for job_url, company_slug in jobs:
                    if job_url not in seen_urls:
                        seen_urls.add(job_url)
                        all_jobs.append(GreenhouseJob(url=job_url, company_slug=company_slug))
                print(f"    [{i+1}/{len(seed_urls)}] {url[:60]}... → {len(jobs)} Greenhouse jobs ({new_count} new)")
                time.sleep(delay_between_requests)
            except Exception as e:
                print(f"    [{i+1}/{len(seed_urls)}] {url[:60]}... → failed: {e}")
                continue

    return all_jobs
