"""
Add feedback to the job agent's learned preferences.

Flow:
1. Store raw feedback first (never lose it)
2. Parse with LLM
3. If parse fails, retry once
4. If retry fails, exit with PARSE_FAILED so Cursor can ask user for clarification
5. If parse succeeds, add to structured store (dedupe, anti-contradiction)

Usage:
  python scripts/add_feedback.py "I wouldn't work at Microsoft, it's too big"
  python scripts/add_feedback.py "Netflix is fine though"
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FEEDBACK_RAW_PATH, LEARNED_PREFERENCES_PATH
from agent.feedback_parser import parse_feedback
from agent.feedback_store import add_preference, load_preferences, save_preferences


def store_raw(raw_path: Path, feedback: str) -> None:
    """Append raw feedback to file. Never lose it."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "a") as f:
        f.write(feedback.strip() + "\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_feedback.py \"<feedback text>\"")
        return 1

    feedback = " ".join(sys.argv[1:]).strip()
    if not feedback:
        print("Error: Feedback text is empty")
        return 1

    raw_path = Path(FEEDBACK_RAW_PATH)
    prefs_path = Path(LEARNED_PREFERENCES_PATH)

    # 1. Store raw first
    store_raw(raw_path, feedback)

    # 2. Parse
    result = parse_feedback(feedback)
    if result is None:
        # 3. Retry once
        result = parse_feedback(feedback)
    if result is None:
        # 4. Parse failed twice - ask user for clarification (via Cursor)
        print("PARSE_FAILED")
        print("I couldn't parse that clearly. Did you mean:")
        print("  (a) Reject a company (which one?)")
        print("  (b) Add a company as an exception to a category rule (which one?)")
        print("  (c) Something else?")
        return 2

    # 5. Add to structured store
    prefs = load_preferences(prefs_path)
    success, err = add_preference(prefs, result.entity, result.action)
    if not success:
        print(f"Error: {err}")
        return 3
    save_preferences(prefs_path, prefs)

    print(f"Added: {result.action} {result.entity}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
