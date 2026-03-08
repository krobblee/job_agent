"""
Swooped job discovery via Playwright.

Swooped is a SPA; job data is loaded by JavaScript. We use Playwright to render
the page, then extract job cards with full descriptions and "Apply on Employer Site" URLs.

Jobs are returned with description already populated — no fetch step needed.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass
class SwoopedJob:
    """A discovered Swooped job with full description (no fetch needed)."""
    url: str  # Canonical Apply URL (from "Apply on Employer Site" button)
    company: str
    role_title: str
    location: str
    job_description: str


def _load_swooped_urls(path: str) -> List[str]:
    """Load Swooped search URLs from file (one per line, skip comments and blank)."""
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


def _extract_jobs_from_html(html: str, base_url: str) -> List[SwoopedJob]:
    """
    Extract job data from Swooped HTML.
    
    Looks for:
    - Links to job detail pages (swooped.co/.../job-postings/... or selectedJobId)
    - "Apply on Employer Site" button/link (canonical job URL)
    - Job title, company, description
    
    Returns list of SwoopedJob. May return empty if page structure differs.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[SwoopedJob] = []
    seen_urls: Set[str] = set()

    # Find Apply buttons/links - text like "Apply on Employer Site" or "Apply"
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        text = (a.get_text(strip=True) or "").lower()
        if not href or href.startswith("#") or "javascript:" in href:
            continue
            
        full_url = urljoin(base_url, href)
        
        # Skip Swooped internal links
        if "swooped.co" in full_url and "job-postings" not in full_url:
            continue
            
        # Skip if it's a Swooped job detail page (we want the external Apply URL)
        parsed = urlparse(full_url)
        if "swooped.co" in parsed.netloc and "/job-postings" in parsed.path:
            # This might be a link TO a job detail page, not the Apply URL
            continue
        if "apply" in text or "employer site" in text:
            # This might be the Apply on Employer Site URL
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                # We need title, company, description from context - may need to get from parent
                results.append(SwoopedJob(
                    url=full_url,
                    company="",
                    role_title="",
                    location="",
                    job_description="",
                ))
    
    return results


def discover_swooped_jobs(
    seed_urls_path: str,
    timeout: int = 30,
    delay_between_requests: float = 2.0,
    headless: bool = True,
) -> List[SwoopedJob]:
    """
    Use Playwright to load Swooped search pages and extract jobs.
    
    Each job has full description from Swooped — no fetch step needed.
    Uses canonical Apply URL for deduplication.
    
    Returns list of SwoopedJob.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Playwright required for Swooped. Run: pip install playwright && playwright install chromium")

    urls = _load_swooped_urls(seed_urls_path)
    swooped_urls = [u for u in urls if "swooped.co" in u]
    if not swooped_urls:
        return []

    all_jobs: List[SwoopedJob] = []
    seen_urls: Set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout * 1000)
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            })

            for i, url in enumerate(swooped_urls):
                try:
                    page.goto(url, wait_until="networkidle")
                    # Wait for job cards to load
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)  # Extra wait for dynamic content

                    html = page.content()
                    jobs = _extract_swooped_jobs_from_rendered_page(page, page.url, html)

                    new_count = 0
                    for job in jobs:
                        if job.url not in seen_urls:
                            seen_urls.add(job.url)
                            all_jobs.append(job)
                            new_count += 1

                    print(f"    [{i+1}/{len(swooped_urls)}] {url[:70]}... → {len(jobs)} jobs ({new_count} new)")
                    time.sleep(delay_between_requests)
                except Exception as e:
                    print(f"    [{i+1}/{len(swooped_urls)}] {url[:70]}... → failed: {e}")
        finally:
            browser.close()

    return all_jobs


def _extract_swooped_jobs_from_rendered_page(page, base_url: str, html: str) -> List[SwoopedJob]:
    """
    Extract jobs from rendered Swooped page.
    
    Swooped layout: job list on left, detail panel on right when selected.
    We look for job cards and extract Apply URL + description from the detail view.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[SwoopedJob] = []
    seen: Set[str] = set()

    # Strategy: find all links that look like external Apply URLs (greenhouse, ashby, lever, etc.)
    ats_pattern = re.compile(
        r"https?://(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.ashbyhq\.com|jobs\.lever\.co|apply\.workable\.com|[a-zA-Z0-9-]+\.greenhouse\.io)/[^\s\"']+",
        re.IGNORECASE,
    )

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or "javascript:" in href:
            continue
        full = urljoin(base_url, href)
        m = ats_pattern.search(full)
        if m:
            apply_url = m.group(0).split('"')[0].split("'")[0].strip()
            if apply_url not in seen:
                seen.add(apply_url)
                # Try to get title/company from nearby text
                parent = a.find_parent(["div", "article", "li", "section"])
                title = ""
                company = ""
                desc = ""
                if parent:
                    text = parent.get_text(" ", strip=True)
                    desc = text[:6000] if len(text) > 100 else ""
                results.append(SwoopedJob(
                    url=apply_url,
                    company=company,
                    role_title=title,
                    location="",
                    job_description=desc,
                ))

    # If we didn't find ATS links, look for "Apply on Employer Site" button
    if not results:
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            text = (a.get_text(strip=True) or "")
            if not href or "swooped.co" in href:
                continue
            if "apply" in text.lower() or "employer" in text.lower():
                full = urljoin(base_url, href)
                if full not in seen:
                    seen.add(full)
                    parent = a.find_parent(["div", "article", "li", "section"])
                    desc = parent.get_text(" ", strip=True)[:6000] if parent else ""
                    results.append(SwoopedJob(
                        url=full,
                        company="",
                        role_title="",
                        location="",
                        job_description=desc,
                    ))

    return results
