"""
Snapshot storage for Aggregator pipeline delta-based freshness.

Stores the set of job URLs from each run. Next run diffs against this
to determine which jobs are "new" (posted since last run).
"""

from __future__ import annotations

import json
from pathlib import Path


SNAPSHOT_FILENAME = "aggregator_previous.json"


def load_previous_snapshot(snapshot_dir: str) -> set[str]:
    """
    Load URLs from the previous run's snapshot.

    Returns empty set if no snapshot exists (e.g., first run).
    """
    path = Path(snapshot_dir) / SNAPSHOT_FILENAME
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("urls", []))
    except Exception:
        return set()


def save_snapshot(snapshot_dir: str, date: str, urls: list[str]) -> None:
    """Save current run's URLs for next run's delta."""
    path = Path(snapshot_dir)
    path.mkdir(parents=True, exist_ok=True)
    data = {"date": date, "urls": sorted(urls)}
    (path / SNAPSHOT_FILENAME).write_text(json.dumps(data, indent=2), encoding="utf-8")
