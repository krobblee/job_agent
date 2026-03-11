from __future__ import annotations

import os

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

# Aggregator discovery: aggregator URLs (one per line)
STARTUP_URLS_PATH = os.getenv("STARTUP_URLS_PATH", "data/Startup_URLs.txt")
AGGREGATOR_SNAPSHOT_DIR = os.getenv("AGGREGATOR_SNAPSHOT_DIR", "data/snapshots")

# Swooped discovery: search URLs (one per line); jobs have full description, no fetch needed
SWOOPED_URLS_PATH = os.getenv("SWOOPED_URLS_PATH", "data/Swooped_URLs.txt")

# Feedback / learned preferences
FEEDBACK_RAW_PATH = os.getenv("FEEDBACK_RAW_PATH", "data/feedback_raw.txt")
LEARNED_PREFERENCES_PATH = os.getenv("LEARNED_PREFERENCES_PATH", "data/learned_preferences.json")

PROFILE = """
Candidate profile (high level):
- 15 years TPM / Product Ops experience

Salary requirements:
- Reject if posted salary/compensation is stated and below $180k base (minimum; higher for leadership)
- If salary is not posted, do not reject solely on that basis (can apply and negotiate)
- Wants to lead digital transformation: improve PDLC/SDLC, workflows, operating model, and execution predictability
- Strong interest in AI-enabled transformation: adopting AI tools/agents, redefining roles & responsibilities for engineers and PMs, helping teams manage agents and work more strategically
- Strong preference for 0-1 / greenfield / building new software and new capabilities
- Loves ambiguity: come into chaos, create clarity, operating cadence, and measurable execution
- Would love to be a founding member / first hire of TPM or Product Operations function

Hard NOs:
- Compliance-heavy/regulatory/legal/GRC domains
- Implementation / onboarding / professional services / customer delivery roles
- Infrastructure, migrations, architecture, platform-heavy work
- Defense / defense contractors / military
- Crypto / blockchain / Web3
- Government sector / government contracting
- Employer: Remote Hunter
- Hybrid / onsite requirements (e.g. "3 days per week in office", "hybrid onsite", "onsite in [city]") — candidate wants remote or flexible
- Large enterprise / big tech companies (e.g. Microsoft, Google, Amazon, Oracle, Meta, Apple, Salesforce, IBM) — EXCEPT: Netflix, Zillow (add others to this exceptions list as needed)
- Reposted jobs (e.g. "United States · Reposted 3 days ago") — too late to apply, too many applications
- Job description includes "No longer accepting applications" — role is closed

Rule precedence: Entity-level preferences override category rules. E.g. "reject large enterprises" is a category rule; "Netflix is exception" is an entity rule — for Netflix, the entity rule wins.
"""
