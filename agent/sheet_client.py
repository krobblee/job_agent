from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _col_to_a1(col_1based: int) -> str:
    """Convert 1-based column number to A1 letter (1=A, 2=B, ..., 27=AA)."""
    result = ""
    col = col_1based
    while col > 0:
        col, rem = divmod(col - 1, 26)
        result = chr(65 + rem) + result
    return result


def utc_now_iso() -> str:
    """Return current time in Eastern Time (EST/EDT) with readable format."""
    eastern = ZoneInfo("America/New_York")
    now = datetime.now(eastern)
    # Format: "2026-02-05 13:09:55 EST" (or EDT during daylight saving)
    timezone_abbr = now.strftime("%Z")  # EST or EDT
    return now.strftime(f"%Y-%m-%d %H:%M:%S {timezone_abbr}")


@dataclass(frozen=True)
class SheetConfig:
    sheet_id: str
    worksheet_title: str = "Sheet1"
    credentials_path: str = "credentials/service_account.json"


class SheetClient:
    def __init__(self, cfg: SheetConfig):
        self.cfg = cfg
        creds = Credentials.from_service_account_file(cfg.credentials_path, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        self._ws = self._client.open_by_key(cfg.sheet_id).worksheet(cfg.worksheet_title)
        self._header_cache: List[str] | None = None

    @property
    def worksheet(self):
        return self._ws
    
    def refresh_worksheet(self) -> None:
        """Force reload worksheet to clear any caching."""
        self._ws = self._client.open_by_key(self.cfg.sheet_id).worksheet(self.cfg.worksheet_title)
        self._header_cache = None

    def get_header(self, use_cache: bool = True) -> List[str]:
        """Get header row. use_cache=True to avoid redundant API calls."""
        if use_cache and self._header_cache is not None:
            return self._header_cache
        
        values = self._ws.get_all_values()
        header = values[0] if values else []
        self._header_cache = header
        return header

    def _header_index(self, col: str) -> int:
        """Get 0-based column index for col, case-insensitive, normalizes spaces/hyphens to underscores."""
        header = self.get_header()
        def _norm(s: str) -> str:
            return (s or "").strip().lower().replace(" ", "_").replace("-", "_")
        col_clean = _norm(col)
        for i, h in enumerate(header):
            if _norm(h) == col_clean:
                return i
        raise ValueError(f"Column not found in sheet header: {col!r} (saw: {header[:8]}...)")

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Return rows as list of dicts (header -> value). Handles duplicate/empty headers."""
        values = self._ws.get_all_values()
        if not values:
            return []
        raw_header = values[0]
        # De-duplicate headers (gspread raises on duplicate keys including '')
        seen: Dict[str, int] = {}
        header = []
        for i, h in enumerate(raw_header):
            raw_key = (h or "").strip()
            if not raw_key:
                key = f"__col_{i}"
            else:
                key = raw_key.lower().replace(" ", "_").replace("-", "_")
            if key in seen:
                seen[key] += 1
                key = f"{key}__{seen[key]}"
            else:
                seen[key] = 0
            header.append(key)
        records = []
        for row in values[1:]:
            rec = {}
            for i, col in enumerate(header):
                rec[col] = row[i] if i < len(row) else ""
            records.append(rec)
        return records

    def get_all_values(self) -> List[List[str]]:
        return self._ws.get_all_values()

    def build_row_index(self, key_col: str = "job_url") -> Dict[str, int]:
        """
        Returns mapping key -> 1-based row number in the sheet (including header row).
        Row 1 is header, so first data row is 2.
        """
        if not self.get_header():
            return {}
        key_idx = self._header_index(key_col)
        values = self.get_all_values()

        index: Dict[str, int] = {}
        for row_num, row in enumerate(values[1:], start=2):
            if key_idx >= len(row):
                continue
            key = (row[key_idx] or "").strip()
            if key:
                index[key] = row_num
                # Also index normalized variants for flexible matching
                if key.endswith("/"):
                    index[key.rstrip("/")] = row_num
                else:
                    index[key + "/"] = row_num
        return index

    def append_row_dict(self, row: Dict[str, Any]) -> None:
        header = self.get_header()
        if not header:
            raise ValueError("Sheet header row is empty; cannot append.")

        def _get_val(col: str) -> str:
            v = row.get(col)
            if v is not None:
                return v
            alt = (col or "").strip().lower().replace(" ", "_")
            return row.get(alt, "")

        out = []
        for col in header:
            val = _get_val(col)
            out.append("" if val is None else str(val))
        # table_range='A1' forces append to start at column A; without it, the Sheets API
        # may detect a "table" starting at the first column with data (e.g. O) and write there.
        self._ws.append_row(out, value_input_option="RAW", table_range="A1")

    def update_row_cells(self, row_number: int, updates: Dict[str, Any]) -> None:
        if not self.get_header():
            raise ValueError("Sheet header row is empty; cannot update.")

        cell_updates = []
        for col, val in updates.items():
            col_idx = self._header_index(col) + 1  # 1-based
            cell_updates.append(gspread.Cell(row_number, col_idx, "" if val is None else str(val)))

        if cell_updates:
            self._ws.update_cells(cell_updates, value_input_option="RAW")

    def batch_update_rows(self, row_updates: Dict[int, Dict[str, Any]]) -> None:
        """
        Batch update multiple rows at once to avoid rate limits.
        
        Args:
            row_updates: Dict mapping row_number -> {column: value}
        """
        if not row_updates:
            return
        
        if not self.get_header():
            raise ValueError("Sheet header row is empty; cannot update.")

        # Build batch_update payload with A1 notation (avoids gspread Cell/coordinate issues after column reorder)
        batch_data = []
        for row_num, updates in row_updates.items():
            for col, val in updates.items():
                col_idx = self._header_index(col) + 1  # 1-based
                cell_addr = f"{_col_to_a1(col_idx)}{row_num}"
                batch_data.append({"range": cell_addr, "values": [["" if val is None else str(val)]]})

        if batch_data:
            try:
                print(f"    batch_update_rows: Updating {len(batch_data)} cells across {len(row_updates)} rows")
                self._ws.batch_update(batch_data, value_input_option="RAW")
                print(f"    batch_update_rows: ✓ Update successful")
            except Exception as e:
                print(f"    batch_update_rows: ✗ ERROR: {type(e).__name__}: {e}")
                raise
    
    def _normalize_url_for_match(self, url: str) -> List[str]:
        """Return URL variants to try when matching sheet rows (handles /comm/ vs /jobs/, trailing slash)."""
        u = (url or "").strip()
        if not u:
            return []
        variants = [u]
        # Trailing slash variants
        if u.endswith("/"):
            variants.append(u.rstrip("/"))
        else:
            variants.append(u + "/")
        # /comm/ vs /jobs/ variants
        if "/comm/jobs/view/" in u:
            v = u.replace("/comm/jobs/view/", "/jobs/view/")
            if v not in variants:
                variants.append(v)
            if v.rstrip("/") not in variants and v != v.rstrip("/"):
                variants.append(v.rstrip("/"))
        elif "/jobs/view/" in u:
            v = u.replace("/jobs/view/", "/comm/jobs/view/")
            if v not in variants:
                variants.append(v)
        return variants

    def write_scoring_results(self, scored_jobs: List[Any]) -> int:
        """
        Write scoring results (bucket + reasoning) to Sheet.
        
        Args:
            scored_jobs: List of ScoredJob objects with url, bucket, why fields
            
        Returns:
            Number of jobs updated
        """
        if not scored_jobs:
            return 0
        
        row_index = self.build_row_index(key_col="job_url")
        batch_updates: Dict[int, Dict[str, Any]] = {}

        for job in scored_jobs:
            variants = self._normalize_url_for_match(job.url)
            row_num = None
            for v in variants:
                row_num = row_index.get(v)
                if row_num is not None:
                    break
            if not row_num:
                continue

            reasoning = "\n".join(f"• {reason}" for reason in job.why)
            batch_updates[row_num] = {
                "agent_bucket": job.bucket,
                "agent_reasoning": reasoning,
            }

        if batch_updates:
            self.batch_update_rows(batch_updates)

        return len(batch_updates)
