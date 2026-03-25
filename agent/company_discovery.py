"""
Job discovery for the Company List pipeline.

**Intended input:** `career_site_url` is the direct URL of the hosted job board (open roles
listing on Ashby, Greenhouse, Lever, Gem, Workday, Darwinbox, etc.). See README and SETUP.

**Fallback:** If `career_site_url` fails or returns no links, fetches `company_url` and tries
to find a careers/jobs link on the marketing site (less reliable than pasting the board URL).

Extracts job posting URLs using ATS-oriented patterns and generic heuristics.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class CompanyJob:
    """A discovered job URL from a job board or (fallback) company site."""
    url: str
    company: str


# URL patterns that indicate a job posting (not benefits, culture, etc.)
JOB_URL_PATTERNS = [
    re.compile(r"greenhouse\.io/.*/jobs/\d+", re.I),
    re.compile(r"job-boards\.greenhouse\.io/.*/jobs/\d+", re.I),
    re.compile(r"jobs\.lever\.co/", re.I),
    re.compile(r"workday\.com/.*/job", re.I),
    re.compile(r"jobs\.ashbyhq\.com/[^/]+/[^/]+", re.I),  # jobs.ashbyhq.com/org/job-id
    re.compile(r"ashbyhq\.com/.*/jobs", re.I),
    re.compile(r"jobs\.gem\.com/[^/]+/(?:job|jobs)/", re.I),  # jobs.gem.com/company/jobs/123
    re.compile(r"jobs\.gem\.com/[^/]+/[^/]+/.+", re.I),  # jobs.gem.com/company/jobs/xyz (3+ path segments)
    re.compile(r"jobs\.gem\.com/[^/]+/[a-zA-Z0-9_-]{20,}", re.I),  # jobs.gem.com/supio/am9icG9zdDp... (encoded job id)
    re.compile(r"darwinbox\.in/.*/(?:job|jobs)/", re.I),  # e.g. spotdraft.darwinbox.in/ms/candidate/job/123
    re.compile(r"/careers?/.*(?:job|position|opening)", re.I),
    re.compile(r"/jobs?/.*(?:job|position|opening|\d+)", re.I),
    re.compile(r"/openings?/", re.I),
    re.compile(r"/job/", re.I),
    re.compile(r"/position/", re.I),
    re.compile(r"linkedin\.com/jobs/view/\d+", re.I),
]

# Link text that suggests the actual job board / open roles page (not the careers landing page)
OPEN_ROLES_LINK_TEXT = [
    "view open roles",
    "see open roles",
    "open roles",
    "open positions",
    "current openings",
    "browse jobs",
    "view jobs",
    "see jobs",
    "all jobs",
    "job openings",
    "join our team",
    "we're hiring",
]

# Paths/hrefs that suggest a careers or jobs listing page (for fallback discovery)
CAREERS_LINK_PATTERNS = [
    re.compile(r"/careers?/?$", re.I),
    re.compile(r"/jobs?/?$", re.I),
    re.compile(r"/careers?/", re.I),
    re.compile(r"/jobs?/", re.I),
    re.compile(r"/openings?/", re.I),
    re.compile(r"/join/?$", re.I),
    re.compile(r"/work-with-us/?$", re.I),
]

# Link text that suggests careers (for fallback)
CAREERS_LINK_TEXT = {"careers", "jobs", "join us", "join our team", "work with us", "open positions", "open roles"}


def _ensure_url_protocol(url: str) -> str:
    """Ensure URL has http(s) protocol. Returns normalized URL."""
    u = (url or "").strip()
    if not u:
        return u
    lower = u.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return u
    # Protocol-relative //example.com -> https://example.com
    if u.startswith("//"):
        return "https:" + u
    return "https://" + u


def _is_job_url(url: str) -> bool:
    """Return True if URL looks like a job posting (not benefits, culture, etc.)."""
    if not url or len(url) < 10:
        return False
    # Exclude common non-job pages
    lower = url.lower()
    if any(x in lower for x in ["/benefits", "/culture", "/about", "/contact", "/press", "/blog", "linkedin.com/company"]):
        return False
    return any(p.search(url) for p in JOB_URL_PATTERNS)


def _extract_job_urls_from_html(html: str, base_url: str) -> List[str]:
    """Extract job URLs from HTML. Returns deduplicated list."""
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()
    results: List[str] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        # Require http(s)
        if parsed.scheme not in ("http", "https"):
            continue
        # Normalize: no fragment
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            clean += "?" + parsed.query
        clean = clean.rstrip("/") or clean
        if clean not in seen and _is_job_url(clean):
            seen.add(clean)
            results.append(clean)
    return results


def _find_open_roles_link(html: str, base_url: str) -> str | None:
    """
    Find a link to the actual job board (e.g. "View open roles" -> jobs.gem.com/supio).
    Many careers pages are landing pages; the real job listings are behind a separate link.
    """
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        text = (a.get_text(strip=True) or "").lower()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        # Prefer links whose text explicitly says "open roles" etc.
        if any(phrase in text for phrase in OPEN_ROLES_LINK_TEXT):
            return full
    return None


def _find_careers_url_on_page(html: str, base_url: str) -> str | None:
    """
    Find a careers/jobs link on a company homepage.
    Returns first matching URL or None.
    """
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        text = (a.get_text(strip=True) or "").lower()
        if not href or href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        # Same domain or relative
        base_parsed = urlparse(base_url)
        if parsed.netloc and parsed.netloc != base_parsed.netloc:
            # External link - skip unless it's clearly careers
            pass
        path = (parsed.path or "").lower()
        # Match by path pattern
        if any(p.search(path) for p in CAREERS_LINK_PATTERNS):
            return full
        # Match by link text
        if text in CAREERS_LINK_TEXT or any(phrase in text for phrase in ["careers", "jobs", "open roles", "open positions"]):
            return full
    return None


def _fetch_page(url: str, timeout: int = 15, headers: dict | None = None) -> str:
    """Fetch page HTML. Raises on error."""
    h = headers or {}
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    default_headers.update(h)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=default_headers)
        resp.raise_for_status()
        return resp.text


def _fetch_page_with_playwright(url: str, timeout: int = 20) -> str:
    """Fetch page with Playwright (JS execution). For job boards that render via JavaScript."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Playwright required. Run: pip3 install playwright && playwright install chromium")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout * 1000)
            page.goto(url, wait_until="load")
            time.sleep(3)  # Allow dynamic content to render
            return page.content()
        finally:
            browser.close()


def _fetch_open_roles_via_playwright_click(career_url: str, timeout: int = 25) -> str | None:
    """
    Load career page with Playwright, find and click "View open roles" / "See open positions"
    (link or button), wait for navigation, return the job board page HTML.
    Returns None if click fails or no navigation.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    # Text patterns to search for (case-insensitive)
    click_patterns = [
        "view open roles",
        "see open roles",
        "open roles",
        "see open positions",
        "view open positions",
        "open positions",
        "browse jobs",
        "view jobs",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout * 1000)
            page.goto(career_url, wait_until="load")
            time.sleep(2)

            for pattern in click_patterns:
                try:
                    # Prefer links (most "View open roles" are <a href>)
                    locator = page.get_by_role("link", name=pattern)
                    if locator.count() > 0:
                        with page.expect_navigation(wait_until="load", timeout=15000):
                            locator.first.click()
                        time.sleep(3)
                        return page.content()
                except Exception:
                    pass

                try:
                    # Fallback: any element with this text (button, div, etc.)
                    locator = page.get_by_text(pattern, exact=False)
                    if locator.count() > 0:
                        with page.expect_navigation(wait_until="load", timeout=15000):
                            locator.first.click()
                        time.sleep(3)
                        return page.content()
                except Exception:
                    pass

            return None
        finally:
            browser.close()


def discover_jobs_from_career_page(
    career_url: str,
    company_name: str,
    timeout: int = 15,
) -> List[CompanyJob]:
    """
    Fetch a URL (normally the hosted job board listing) and extract job posting URLs.

    Also handles marketing career landings that only link to the real board (e.g. "View open
    roles" → jobs.gem.com). If httpx finds nothing (JS-rendered boards), tries Playwright.
    Returns list of CompanyJob (url, company).
    """
    html = _fetch_page(career_url, timeout=timeout)
    urls = _extract_job_urls_from_html(html, career_url)

    # If no jobs on this page, look for "View open roles" / "See open roles" link
    if not urls:
        open_roles_url = _find_open_roles_link(html, career_url)
        if open_roles_url:
            try:
                html = _fetch_page(open_roles_url, timeout=timeout)
                urls = _extract_job_urls_from_html(html, open_roles_url)
            except Exception:
                pass

    # If still no jobs, try Playwright. First: click "View open roles" (handles buttons, JS links)
    if not urls:
        try:
            job_board_html = _fetch_open_roles_via_playwright_click(career_url, timeout=25)
            if job_board_html:
                urls = _extract_job_urls_from_html(job_board_html, career_url)
        except Exception as e:
            print(f"    [Playwright click] {e}")

    # Fallback: fetch career page with Playwright, find link in HTML, fetch that URL
    if not urls:
        open_roles_url = _find_open_roles_link(html, career_url)
        playwright_url = open_roles_url if open_roles_url else career_url
        try:
            html = _fetch_page_with_playwright(playwright_url, timeout=20)
            urls = _extract_job_urls_from_html(html, playwright_url)
        except Exception as e:
            print(f"    [Playwright] {e}")

    return [CompanyJob(url=u, company=company_name) for u in urls]


def discover_jobs_for_company(
    company_name: str,
    company_url: str,
    career_site_url: str,
    timeout: int = 15,
    delay: float = 1.5,
) -> Tuple[List[CompanyJob], str | None]:
    """
    Discover jobs for one company row. Order of operations:

    1. `career_site_url` — should be the ATS job board listing URL (preferred).
    2. `company_url` — optional fallback: scrape homepage for a careers/jobs link.

    Returns:
        (jobs, error): jobs list and None, or ([], error_message) on failure.
    """
    time.sleep(delay)

    # 1. Try career_site_url first
    if career_site_url and career_site_url.strip():
        career_url = _ensure_url_protocol(career_site_url.strip())
        try:
            jobs = discover_jobs_from_career_page(
                career_url=career_url,
                company_name=company_name or "Unknown",
                timeout=timeout,
            )
            if jobs:
                return jobs, None
        except Exception as e:
            pass  # Fall through to company_url

    # 2. Fallback: fetch company_url, find careers link
    if not company_url or not company_url.strip():
        return [], f"Career URL failed and no company URL to fall back to"

    company_url = _ensure_url_protocol(company_url.strip())
    try:
        html = _fetch_page(company_url, timeout=timeout)
        careers_link = _find_careers_url_on_page(html, company_url)
        if not careers_link:
            return [], f"Career URL failed; no careers link found on company page"
        careers_link = _ensure_url_protocol(careers_link)
        jobs = discover_jobs_from_career_page(
            career_url=careers_link,
            company_name=company_name or "Unknown",
            timeout=timeout,
        )
        if jobs:
            return jobs, None
        return [], f"Found careers page but no job links extracted"
    except Exception as e:
        return [], f"Fallback failed: {e}"
