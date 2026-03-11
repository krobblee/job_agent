"""
Debug: capture Swooped API responses and save to JSON.
Run: python3 scripts/debug_swooped_api.py
Output: data/swooped_api_responses.json
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://swooped.co/app/job-postings?search=Technical+Program+Manager"
OUTPUT = Path("data/swooped_api_responses.json")


def main():
    responses = []

    def on_response(response):
        url = response.url
        if "swooped.co" in url:
            try:
                body = response.json()
                responses.append({"url": url, "body": body})
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        page.on("response", on_response)
        page.goto(URL, wait_until="networkidle")
        import time
        time.sleep(5)
        browser.close()

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(responses, indent=2, default=str), encoding="utf-8")
    print(f"Saved {len(responses)} API responses to {OUTPUT}")


if __name__ == "__main__":
    main()
