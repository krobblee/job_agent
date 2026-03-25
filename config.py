from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

# OpenAI client is intentionally created once and imported where needed.
client = OpenAI()

# Gmail API scope (readonly for v1)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Google Sheet ID (source of truth for job tracking)
SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    raise ValueError("SHEET_ID must be set in .env file")

# Worksheet (tab) names
EMAIL_WORKSHEET = os.getenv("EMAIL_WORKSHEET", "Email")
AGGREGATOR_WORKSHEET = os.getenv("AGGREGATOR_WORKSHEET", "Aggregator")
COMPANIES_LIST_WORKSHEET = os.getenv("COMPANIES_LIST_WORKSHEET", "Company List")
COMPANIES_JOBS_WORKSHEET = os.getenv("COMPANIES_JOBS_WORKSHEET", "Company Jobs")

# Aggregator discovery: aggregator URLs (one per line)
STARTUP_URLS_PATH = os.getenv("STARTUP_URLS_PATH", "data/Startup_URLs.txt")
AGGREGATOR_SNAPSHOT_DIR = os.getenv("AGGREGATOR_SNAPSHOT_DIR", "data/snapshots")

# Swooped discovery: search URLs (one per line); jobs have full description, no fetch needed
SWOOPED_URLS_PATH = os.getenv("SWOOPED_URLS_PATH", "data/Swooped_URLs.txt")

# Feedback / learned preferences
FEEDBACK_RAW_PATH = os.getenv("FEEDBACK_RAW_PATH", "data/feedback_raw.txt")
LEARNED_PREFERENCES_PATH = os.getenv("LEARNED_PREFERENCES_PATH", "data/learned_preferences.json")

# Candidate profile: path to a text file (default data/profile.txt)
PROFILE_PATH = os.getenv("PROFILE_PATH", "data/profile.txt")


def _load_profile() -> str:
    """Load profile from PROFILE_PATH. Raises if file does not exist or is empty."""
    path = Path(PROFILE_PATH)
    if not path.exists():
        if PROFILE_PATH == "data/profile.txt":
            raise FileNotFoundError(
                f"Profile file not found at {PROFILE_PATH}. "
                "Copy data/profile.example.txt to data/profile.txt and customize it."
            )
        raise FileNotFoundError(
            f"Profile file not found at {PROFILE_PATH}. "
            "Create the file or set PROFILE_PATH to your profile file path."
        )
    content = path.read_text(encoding="utf-8").strip()
    if len(content) < 50:
        raise ValueError(
            f"Profile at {PROFILE_PATH} appears empty or too short. "
            "Add your experience, salary range, preferences, and hard NOs. "
            "See data/profile.example.txt for structure."
        )
    return content


PROFILE = _load_profile()
