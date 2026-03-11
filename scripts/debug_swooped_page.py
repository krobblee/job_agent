"""
Debug script: save Swooped page HTML after Playwright render.
Run: python3 scripts/debug_swooped_page.py
Output: data/swooped_debug.html — inspect to see current page structure.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://swooped.co/app/job-postings?search=Technical+Program+Manager"
OUTPUT = Path("data/swooped_debug.html")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_load_state("networkidle")
        import time
        time.sleep(3)
        html = page.content()
        browser.close()

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Saved {len(html)} chars to {OUTPUT}")
    print("Inspect the file to see Swooped's current HTML structure.")


if __name__ == "__main__":
    main()
