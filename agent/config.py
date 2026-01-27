from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

# OpenAI client is intentionally created once and imported where needed.
client = OpenAI()

DB_PATH = os.getenv("DB_PATH", "jobs.db")

# Gmail API scope (readonly for v1)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

PROFILE = """
Candidate profile (high level):
- 15 years TPM / Product Ops experience
- Wants to lead digital transformation: improve PDLC/SDLC, workflows, operating model, and execution predictability
- Strong interest in AI-enabled transformation: adopting AI tools/agents, redefining roles & responsibilities for engineers and PMs, helping teams manage agents and work more strategically
- Strong preference for 0-1 / greenfield / building new software and new capabilities
- Loves ambiguity: come into chaos, create clarity, operating cadence, and measurable execution
- Would love to be a founding member / first hire of TPM or Product Operations function

Hard NOs:
- Compliance-heavy/regulatory/legal/GRC domains
- Implementation / onboarding / professional services / customer delivery roles
- Infrastructure, migrations, architecture, platform-heavy work
"""
