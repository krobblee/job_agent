from __future__ import annotations

from typing import Tuple

from bs4 import BeautifulSoup


def extract_job_info(html: str) -> Tuple[str, str, str, str]:
    """
    Extract minimal job information from HTML.
    
    This is a lightweight, heuristic-based parser designed for v1.
    We only require role_title OR job_description to be non-empty for success.
    
    Args:
        html: Raw HTML content from job posting page
    
    Returns:
        Tuple of (role_title, company, location, job_description)
        - role_title: Extracted from <title> tag
        - company: Empty string (best-effort extraction not implemented in v1)
        - location: Empty string (best-effort extraction not implemented in v1)
        - job_description: Concatenated visible text from main/article/body, bounded to 6000 chars
    
    Note:
        At least one of role_title or job_description must be non-empty for the
        fetch to be considered successful. Empty results should be marked as parse_empty.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract title from <title> tag
    title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    
    # Extract description: concatenate visible text from main/article/body
    main = soup.find("main") or soup.find("article") or soup.body
    desc = ""
    if main:
        desc = " ".join(main.get_text(" ", strip=True).split())
        # Bound to 6000 chars for sheet compatibility and reasonable summary size
        desc = desc[:6000]
    
    # Company and location extraction are best-effort for v1
    # More sophisticated extraction can be added in future versions
    company = ""
    location = ""
    
    return title, company, location, desc
