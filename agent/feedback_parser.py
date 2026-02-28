"""
Parse free-form feedback into structured FeedbackPreference.
Uses LLM with schema validation. Returns None if parse fails.
"""
from __future__ import annotations

from config import client
from models import FeedbackPreference


PARSE_PROMPT = """Extract the job preference from this feedback. Return ONLY valid JSON.

Feedback: "{feedback}"

Return JSON in this exact format:
{{"entity": "CompanyName", "action": "reject"}}
or
{{"entity": "CompanyName", "action": "exception"}}

- entity: The company name (e.g. Microsoft, Netflix). Use the standard/canonical name.
- action: "reject" if the user would not work there, "exception" if the user would work there despite a category rule (e.g. large enterprise exception).

If the feedback is ambiguous (e.g. "that company", "the big one") or cannot be parsed, return: {{"entity": "", "action": ""}}
"""


def parse_feedback(feedback: str) -> FeedbackPreference | None:
    """
    Parse free-form feedback into FeedbackPreference.
    Returns None if parse fails or result is invalid/ambiguous.
    """
    if not (feedback or "").strip():
        return None

    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=PARSE_PROMPT.format(feedback=feedback.strip()),
        )
        raw = (resp.output_text or "").strip()
        # Strip ```json if present
        if raw.startswith("```"):
            raw = raw.strip("`").replace("json", "", 1).strip()
        import re
        raw = re.sub(r'[\x00-\x1f\x7f]', '', raw)

        import json as _json
        data = _json.loads(raw)
        entity = (data.get("entity") or "").strip()
        action = (data.get("action") or "").strip().lower()

        if not entity or action not in ("reject", "exception"):
            return None

        return FeedbackPreference(entity=entity, action=action)
    except Exception:
        return None
