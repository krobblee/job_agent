"""
Debug script to inspect Swooped page structure.

Run: python3 scripts/debug_swooped.py

Saves the rendered HTML and prints links/buttons found.
Use this to refine swooped_discovery selectors.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    url = "https://swooped.co/app/job-postings?officeRequirements=remote&search=Technical%20Program%20Manager"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        print(f"Loading {url}...")
        page.goto(url, wait_until="networkidle")
        page.wait_for_load_state("networkidle")
        import time
        time.sleep(3)
        
        html = page.content()
        out = Path("data/swooped_debug.html")
        out.write_text(html, encoding="utf-8")
        print(f"Saved HTML to {out} ({len(html)} chars)")
        
        # Find all links
        links = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(a => ({
                    href: a.href,
                    text: a.textContent?.trim().slice(0, 80),
                    isApply: /apply|employer/i.test(a.textContent || '')
                }));
            }
        """)
        
        apply_links = [l for l in links if l["isApply"] or "greenhouse" in (l["href"] or "").lower() or "ashby" in (l["href"] or "").lower() or "lever" in (l["href"] or "").lower()]
        print(f"\nFound {len(links)} total links, {len(apply_links)} apply/external:")
        for l in apply_links[:15]:
            print(f"  {l['text'][:50]} -> {l['href'][:80]}")
        
        browser.close()


if __name__ == "__main__":
    main()
