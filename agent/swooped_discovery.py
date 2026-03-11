"""
Swooped job discovery via Playwright.

Swooped is a SPA; job data is loaded by JavaScript from api.swooped.co.
We intercept API responses to extract job data (apply URL, title, company, description).
Falls back to HTML parsing if API interception yields nothing.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set
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


def _parse_jobs_from_api_body(body: Any) -> List[SwoopedJob]:
    """
    Extract SwoopedJob from API response JSON.
    Handles Swooped GraphQL: data.jobPostings with url, jobTitle, company.name, jobDescription.
    """
    results: List[SwoopedJob] = []
    seen: Set[str] = set()

    # Swooped GraphQL: data.jobPostings
    jobs_data = None
    if isinstance(body, dict):
        data = body.get("data") or body
        jobs_data = data.get("jobPostings") or data.get("jobs")

    if isinstance(jobs_data, list):
        for obj in jobs_data:
            if not isinstance(obj, dict):
                continue
            url = (obj.get("url") or obj.get("applyUrl") or obj.get("apply_url") or "").strip()
            if not url or "swooped.co" in url:
                continue
            if url in seen:
                continue
            seen.add(url)
            title = (obj.get("jobTitle") or obj.get("title") or obj.get("role_title") or "").strip()
            company = ""
            c = obj.get("company")
            if isinstance(c, dict):
                company = (c.get("name") or "").strip()
            elif isinstance(c, str):
                company = c.strip()
            loc = (obj.get("location") or obj.get("location_text") or "").strip()
            desc = obj.get("jobDescription") or obj.get("description") or obj.get("job_description") or ""
            desc = desc[:6000] if isinstance(desc, str) else ""
            results.append(SwoopedJob(
                url=url,
                company=company,
                role_title=title,
                location=loc,
                job_description=desc,
            ))
        return results

    # Fallback: generic walk
    def _extract_apply_url(obj: Dict) -> str:
        for key in ("apply_url", "applyUrl", "application_url", "job_url", "url", "external_url"):
            v = obj.get(key)
            if v and isinstance(v, str) and v.startswith("http") and "swooped.co" not in v:
                return v.strip()
        return ""

    def _str(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, dict):
            return str(val.get("name", val.get("title", "")) or "")
        return str(val).strip()

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            url = _extract_apply_url(obj)
            if url and url not in seen:
                seen.add(url)
                title = _str(obj.get("jobTitle") or obj.get("title") or obj.get("role_title") or obj.get("name"))
                company = _str(obj.get("company") or obj.get("company_name") or obj.get("employer"))
                desc = obj.get("jobDescription") or obj.get("description") or obj.get("job_description") or obj.get("body") or ""
                desc = desc[:6000] if isinstance(desc, str) else ""
                loc = _str(obj.get("location") or obj.get("location_text"))
                results.append(SwoopedJob(
                    url=url,
                    company=company,
                    role_title=title,
                    location=loc,
                    job_description=desc,
                ))
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(body)
    return results


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
        raise ImportError("Playwright required for Swooped. Run: pip3 install playwright && playwright install chromium")

    urls = _load_swooped_urls(seed_urls_path)
    swooped_urls = [u for u in urls if "swooped.co" in u]
    if not swooped_urls:
        return []

    all_jobs: List[SwoopedJob] = []
    seen_urls: Set[str] = set()
    api_bodies: List[Any] = []

    def _on_response(response):
        url = response.url
        if "api.swooped.co" in url and "graphql" in url.lower():
            try:
                body = response.json()
                if body and isinstance(body, dict):
                    api_bodies.append(body)
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout * 1000)
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            })
            page.on("response", _on_response)

            for i, url in enumerate(swooped_urls):
                try:
                    api_bodies.clear()
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)  # Allow API responses to complete

                    jobs: List[SwoopedJob] = []
                    for body in api_bodies:
                        jobs.extend(_parse_jobs_from_api_body(body))

                    if not jobs:
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
