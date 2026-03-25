from __future__ import annotations

import json
import re
from typing import Tuple

from bs4 import BeautifulSoup

# Generic page titles (Gem, etc.) that don't convey the real role
GENERIC_TITLES = {"work with us!", "join our team!", "careers", "open roles", "job opportunities"}


def html_to_plain_text(text: str) -> str:
    """
    Strip HTML tags and normalize whitespace for sheet storage and scoring.
    JSON-LD JobPosting descriptions (Ashby, etc.) often contain HTML.
    """
    if not text:
        return ""
    t = text.strip()
    if "<" in t and ">" in t:
        t = " ".join(BeautifulSoup(t, "html.parser").get_text(" ", strip=True).split())
    else:
        t = " ".join(t.split())
    return t


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


def _extract_jsonld_job_posting(soup: BeautifulSoup) -> Tuple[str, str, str, str] | None:
    """
    Extract job info from JSON-LD JobPosting schema if present.
    Returns (role_title, company, location, job_description) or None.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                continue
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    title = item.get("title") or ""
                    desc = item.get("description") or ""
                    org = item.get("hiringOrganization", {})
                    company = org.get("name", "") if isinstance(org, dict) else ""
                    loc = item.get("jobLocation", {})
                    if isinstance(loc, dict):
                        location = loc.get("address", {})
                        if isinstance(location, dict):
                            location = location.get("addressLocality", "") or ""
                        else:
                            location = ""
                    else:
                        location = ""
                    if title or desc:
                        plain = html_to_plain_text(str(desc))[:6000]
                        return (title.strip(), company.strip(), location.strip(), plain)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


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

    # Try JSON-LD JobPosting first (reliable for Gem and many ATS)
    jsonld = _extract_jsonld_job_posting(soup)
    if jsonld:
        return jsonld

    # Extract title from <title> tag
    title = (soup.title.get_text(strip=True) if soup.title else "").strip()
    company, role_title, location = _parse_linkedin_title(title)

    # Use first h1 for role when title is generic (Gem uses "Work with us!")
    if role_title.lower().strip() in GENERIC_TITLES:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            role_title = h1.get_text(strip=True)

    # Extract description: main/article/body, then fallbacks
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("article") or soup.body
    desc = ""
    if main:
        desc = " ".join(main.get_text(" ", strip=True).split())

    # Fallback: look for job description containers (Gem, Darwinbox, etc.)
    if not desc or len(desc) < 100:
        for sel in (
            soup.find(class_=re.compile(r"job-description|job-details|description", re.I)),
            soup.find(id=re.compile(r"job-description|description", re.I)),
            soup.find(attrs={"data-testid": re.compile(r"job|description", re.I)}),
        ):
            if sel:
                desc = " ".join(sel.get_text(" ", strip=True).split())
                if len(desc) >= 100:
                    break

    if not desc and soup.body:
        desc = " ".join(soup.body.get_text(" ", strip=True).split())

    desc = html_to_plain_text(desc)[:6000]
    return role_title, company, location, desc
