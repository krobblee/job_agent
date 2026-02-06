from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Protocol

import httpx


class FetchClient(Protocol):
    """
    Protocol for fetching URL content.
    
    This abstraction allows swapping between HTTP-based fetching
    and browser automation without changing FetchManager.
    """
    
    def fetch(self, url: str, timeout_seconds: int) -> str:
        """
        Fetch content from URL.
        
        Args:
            url: URL to fetch
            timeout_seconds: Timeout in seconds
            
        Returns:
            HTML content as string
            
        Raises:
            httpx.TimeoutException: If request times out
            Exception: For other fetch errors
        """
        ...


class HttpFetcher:
    """
    HTTP-based fetcher with enhanced headers to mimic a real browser.
    
    Uses realistic User-Agent and headers to avoid being blocked by
    sites like LinkedIn. Includes rate limiting between requests.
    """
    
    def __init__(self, delay_between_requests: float = 1.0):
        """
        Args:
            delay_between_requests: Seconds to wait between requests (default 1.0)
        """
        self.delay_between_requests = delay_between_requests
        self._last_request_time: float = 0
        
        # Realistic Chrome User-Agent on macOS
        self._user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Common browser headers to look legitimate
        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    
    def fetch(self, url: str, timeout_seconds: int) -> str:
        """
        Fetch URL content with realistic browser headers.
        
        Includes rate limiting to avoid detection and being too aggressive.
        """
        # Rate limiting: wait between requests
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay_between_requests:
                time.sleep(self.delay_between_requests - elapsed)
        
        with httpx.Client() as client:
            resp = client.get(
                url,
                headers=self._headers,
                timeout=timeout_seconds,
                follow_redirects=True,
            )
            resp.raise_for_status()
            
            self._last_request_time = time.time()
            return resp.text


class BrowserFetcher:
    """
    Browser automation fetcher using Playwright.
    
    Uses a real Chromium browser to fetch content, which bypasses
    most anti-scraping measures. Slower than HTTP but much more reliable
    for sites like LinkedIn that block simple requests.
    
    Installation required:
        pip install playwright
        playwright install chromium
    """
    
    def __init__(self, headless: bool = True):
        """
        Args:
            headless: Run browser in headless mode (no visible window).
                     Set to False for debugging.
        """
        self.headless = headless
    
    def fetch(self, url: str, timeout_seconds: int) -> str:
        """
        Fetch URL using Playwright browser automation.
        
        Opens a real browser, navigates to the URL, waits for page load,
        and returns the full HTML content including JavaScript-rendered content.
        """
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
        
        try:
            with sync_playwright() as p:
                # Launch Chromium browser
                browser = p.chromium.launch(headless=self.headless)
                
                # Create new browser context (like a new incognito window)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                
                # Create new page
                page = context.new_page()
                
                # Navigate to URL with timeout
                page.goto(url, timeout=timeout_seconds * 1000, wait_until="domcontentloaded")
                
                # Wait a bit for dynamic content to load
                page.wait_for_timeout(2000)  # 2 seconds
                
                # Get full page content
                content = page.content()
                
                # Cleanup
                browser.close()
                
                return content
                
        except PlaywrightTimeoutError:
            # Convert Playwright timeout to httpx.TimeoutException for consistency
            raise httpx.TimeoutException(f"Browser timeout fetching {url}")
        except Exception as e:
            # Re-raise other exceptions
            raise
