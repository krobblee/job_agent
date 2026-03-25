#!/usr/bin/env python3
"""
Debug script: fetch a job board or careers URL and print all links found.
Prefer the hosted ATS board URL (same as Company List `career_site_url`).
Run: python3 scripts/debug_company_page.py https://jobs.gem.com/supio

Use this to see what links exist on the page and which match our job URL patterns.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from agent.company_discovery import (
    _fetch_page,
    _fetch_page_with_playwright,
    _extract_job_urls_from_html,
    _is_job_url,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/debug_company_page.py <url>")
        print("Example: python3 scripts/debug_company_page.py https://jobs.gem.com/supio")
        sys.exit(1)

    url = sys.argv[1].strip()
    print(f"URL: {url}\n")

    # Try httpx first
    print("=== httpx ===")
    try:
        html = _fetch_page(url, timeout=15)
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if href and not href.startswith("#") and "javascript" not in href:
                full = urljoin(url, href)
                if full.startswith("http"):
                    links.append(full)
        print(f"Total links: {len(links)}")
        job_links = [u for u in links if _is_job_url(u)]
        print(f"Matching job patterns: {len(job_links)}")
        for u in links[:25]:
            print(f"  {'✓' if _is_job_url(u) else ' '} {u[:85]}")
    except Exception as e:
        print(f"Error: {e}")

    # Try Playwright
    print("\n=== Playwright ===")
    try:
        html = _fetch_page_with_playwright(url, timeout=25)
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if href and not href.startswith("#") and "javascript" not in href:
                full = urljoin(url, href)
                if full.startswith("http"):
                    links.append(full)
        print(f"Total links: {len(links)}")
        job_links = [u for u in links if _is_job_url(u)]
        print(f"Matching job patterns: {len(job_links)}")
        for u in links[:25]:
            print(f"  {'✓' if _is_job_url(u) else ' '} {u[:85]}")
        if not job_links and links:
            print("\n(No links matched. Consider adding patterns for the URLs above.)")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
