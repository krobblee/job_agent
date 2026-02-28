from __future__ import annotations

import re
from typing import Tuple

from bs4 import BeautifulSoup


def _parse_linkedin_title(title: str) -> Tuple[str, str, str]:
    """
    Parse LinkedIn <title> format: "Company hiring Role in Location | LinkedIn"
    
    Returns:
        Tuple of (company, role_title, location)
    """
    company = ""
    role_title = title
    location = ""
    
    # Strip LinkedIn suffix
    clean = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    
    # Match "Company hiring Role in Location"
    if " hiring " in clean:
        before, after = clean.split(" hiring ", 1)
        company = before.strip()
        role_part = after
        
        if " in " in role_part:
            # Use last " in " so roles like "PM in Product" don't break location
            role_title, location = role_part.rsplit(" in ", 1)
            role_title = role_title.strip()
            location = location.strip()
        else:
            role_title = role_part.strip()
    
    return company, role_title, location


def extract_job_info(html: str) -> Tuple[str, str, str, str]:
    """
    Extract minimal job information from HTML.
    
    This is a lightweight, heuristic-based parser designed for v1.
    We only require role_title OR job_description to be non-empty for success.
    
    Args:
        html: Raw HTML content from job posting page
    
    Returns:
        Tuple of (role_title, company, location, job_description)
        - role_title: Job title (parsed from <title>; "Company hiring Role in Location" → "Role")
        - company: Company name (parsed from <title> when format is "Company hiring ...")
        - location: Location (parsed from <title> when format includes " in Location")
        - job_description: Concatenated visible text from main/article/body, bounded to 6000 chars
    
    Note:
        At least one of role_title or job_description must be non-empty for the
        fetch to be considered successful. Empty results should be marked as parse_empty.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract title from <title> tag
    title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    
    company, role_title, location = _parse_linkedin_title(title)
    
    # Extract description: concatenate visible text from main/article/body
    main = soup.find("main") or soup.find("article") or soup.body
    desc = ""
    if main:
        desc = " ".join(main.get_text(" ", strip=True).split())
        # Bound to 6000 chars for sheet compatibility and reasonable summary size
        desc = desc[:6000]
    
    return role_title, company, location, desc
