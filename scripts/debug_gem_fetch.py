#!/usr/bin/env python3
"""
Debug: fetch a Gem job URL with BrowserFetcher and inspect what the parser gets.
Usage: python3 scripts/debug_gem_fetch.py [url]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.fetch_client import BrowserFetcher, HttpFetcher
from agent.page_parser import extract_job_info

URL = "https://jobs.gem.com/supio/am9icG9zdDpja-8ADVD-brVLI6w-NDlK"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    url = args[0] if args else URL
    use_browser = "--browser" in sys.argv
    print(f"Fetching: {url} (use_browser={use_browser})\n")

    fetcher = BrowserFetcher(headless=True) if use_browser else HttpFetcher()
    html = fetcher.fetch(url, timeout_seconds=30)

    print(f"HTML length: {len(html)} chars")
    print(f"Has <main>: {'<main>' in html or '<Main>' in html}")
    print(f"Has <article>: {'<article>' in html or '<Article>' in html}")
    print(f"Has body: {'<body' in html}")

    # Check for JSON-LD
    if 'application/ld+json' in html:
        print("Has JSON-LD script")
    if 'JobPosting' in html:
        print("Has JobPosting in HTML")

    role_title, company, location, job_desc = extract_job_info(html)
    print(f"\n--- Parser output ---")
    print(f"role_title: {role_title!r}")
    print(f"company: {company!r}")
    print(f"location: {location!r}")
    print(f"job_description length: {len(job_desc)} chars")
    print(f"job_description preview: {job_desc[:300]!r}...")


if __name__ == "__main__":
    main()
