"""
Structured feedback storage with dedupe and anti-contradiction.
Entity rules override category rules. Entities in exception override reject.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# Common entity normalizations (company name -> canonical)
ENTITY_ALIASES: dict[str, str] = {
    "microsoft corp": "Microsoft",
    "microsoft corporation": "Microsoft",
    "msft": "Microsoft",
    "google llc": "Google",
    "alphabet": "Google",
    "amazon.com": "Amazon",
    "amazon": "Amazon",
    "aws": "Amazon",
}


def _normalize_entity(entity: str) -> str:
    """Normalize company name for consistent storage and matching."""
    e = (entity or "").strip()
    if not e:
        return ""
    lower = e.lower()
    return ENTITY_ALIASES.get(lower, e)


def load_preferences(path: Path) -> dict:
    """Load learned preferences from JSON. Returns {reject: [], exception: [], notes: []}."""
    if not path.exists():
        return {"reject": [], "exception": [], "notes": []}
    try:
        data = json.loads(path.read_text())
        return {
            "reject": list(data.get("reject", [])),
            "exception": list(data.get("exception", [])),
            "notes": list(data.get("notes", [])),
        }
    except (json.JSONDecodeError, OSError):
        return {"reject": [], "exception": [], "notes": []}


def save_preferences(path: Path, prefs: dict) -> None:
    """Save learned preferences to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2))


def add_note(prefs: dict, note: str) -> None:
    """Append a free-form note (role-level guidance, etc.)."""
    note = (note or "").strip()
    if not note:
        return
    notes = prefs.get("notes", [])
    if note not in notes:
        notes.append(note)
        prefs["notes"] = notes


def add_preference(
    prefs: dict[str, list[str]],
    entity: str,
    action: Literal["reject", "exception"],
) -> tuple[bool, str | None]:
    """
    Add a preference with dedupe and anti-contradiction.
    Returns (success, error_message).
    """
    entity = _normalize_entity(entity)
    if not entity:
        return False, "Entity is empty after normalization"

    reject_list = [e for e in prefs.get("reject", []) if e]
    exception_list = [e for e in prefs.get("exception", []) if e]

    if action == "reject":
        if entity in exception_list:
            return False, f"Contradiction: {entity} is in exceptions. Remove from exceptions first, or confirm you want to reject."
        if entity in reject_list:
            return True, None  # Dedupe: already there, no-op
        reject_list.append(entity)
        prefs["reject"] = sorted(set(reject_list))
    else:  # exception
        if entity in reject_list:
            return False, f"Contradiction: {entity} is in reject list. Remove from reject first, or confirm you want to add as exception."
        if entity in exception_list:
            return True, None  # Dedupe: already there, no-op
        exception_list.append(entity)
        prefs["exception"] = sorted(set(exception_list))

    return True, None
