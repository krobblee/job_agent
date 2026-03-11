# Commit Plan — Review Before Approving

Below are staged commit groups. Run the commands after you approve. **Nothing is committed yet.**

---

## Commit 1: Sheet append fix

**Files:** `agent/sheet_client.py`

**Summary:** `fix(sheet): use table_range=A1 so append starts at column A`

**Description:**
```
Without table_range, the Sheets API auto-detects the "table" and may
append starting at the first column with data (e.g. O) instead of A.
Passing table_range="A1" forces append to always start at column A.
```

**Commands:**
```bash
git add agent/sheet_client.py
git commit -m "fix(sheet): use table_range=A1 so append starts at column A" -m "Without table_range, the Sheets API auto-detects the \"table\" and may append starting at the first column with data (e.g. O) instead of A. Passing table_range=\"A1\" forces append to always start at column A."
```

---

## Commit 2: Scorer fixes

**Files:** `agent/scorer.py`, `config.py`

**Summary:** `fix(scorer): auto-reject closed roles, expand large enterprise list`

**Description:**
```
- Auto-reject jobs with "no longer accepting applications" (or similar)
  before LLM scoring — programmatic pre-filter, not LLM-dependent
- Add Oracle, Meta, Apple, Salesforce, IBM to large enterprise rejection list
- Add SWOOPED_URLS_PATH to config for Swooped pipeline (used in next commit)
```

**Commands:**
```bash
git add agent/scorer.py config.py
git commit -m "fix(scorer): auto-reject closed roles, expand large enterprise list" -m "- Auto-reject jobs with \"no longer accepting applications\" before LLM scoring
- Add Oracle, Meta, Apple, Salesforce, IBM to large enterprise rejection list
- Add SWOOPED_URLS_PATH to config for Swooped pipeline"
```

---

## Commit 3: Swooped pipeline

**Files:** `agent/swooped_discovery.py`, `scripts/swooped_upsert.py`, `data/Swooped_URLs.txt`, `run_greenhouse.py`, `scripts/greenhouse_upsert.py`

**Summary:** `feat(swooped): add Swooped discovery to Greenhouse pipeline`

**Description:**
```
- Scrape Swooped search URLs for jobs with full descriptions
- Append to Greenhouse tab with source=swooped, fetch_status=fetched (no fetch needed)
- Add source column to greenhouse_upsert; run_greenhouse runs both Greenhouse and Swooped discovery
```

**Commands:**
```bash
git add agent/swooped_discovery.py scripts/swooped_upsert.py data/Swooped_URLs.txt run_greenhouse.py scripts/greenhouse_upsert.py
git commit -m "feat(swooped): add Swooped discovery to Greenhouse pipeline" -m "- Scrape Swooped search URLs for jobs with full descriptions
- Append to Greenhouse tab with source=swooped, fetch_status=fetched (no fetch needed)
- Add source column to greenhouse_upsert; run_greenhouse runs both Greenhouse and Swooped discovery"
```

---

## Commit 4: Documentation

**Files:** `README.md`, `docs/HANDOFF_V2_COMPLETE.md`, `LEARNING_JOURNAL.md`

**Summary:** `docs: update README, HANDOFF_V2, LEARNING_JOURNAL`

**Description:**
```
- README: scoring rules (auto-reject closed roles, large enterprise list), key features, table_range fix
- HANDOFF_V2: pre-filter for closed roles, table_range note for Sheet storage
- LEARNING_JOURNAL: entry #14 (Sheet alignment & auto-reject fixes, Mar 6 2026)
```

**Commands:**
```bash
git add README.md docs/HANDOFF_V2_COMPLETE.md LEARNING_JOURNAL.md
git commit -m "docs: update README, HANDOFF_V2, LEARNING_JOURNAL" -m "- README: scoring rules, auto-reject closed roles, large enterprise list, table_range fix
- HANDOFF_V2: pre-filter for closed roles, table_range note for Sheet storage
- LEARNING_JOURNAL: entry #14 (Sheet alignment & auto-reject fixes, Mar 6 2026)"
```

---

## Commit 5: run_agent improvements

**Files:** `run_agent.py`

**Summary:** `chore(run_agent): add GMAIL_MAX_RESULTS env, row counts, dedupe URLs`

**Description:**
```
- Use GMAIL_MAX_RESULTS env (default 50) instead of hardcoded 15
- Add rows before/after for upsert; log unique URL count
- Dedupe URLs before upsert; refresh worksheet after upsert
```

**Commands:**
```bash
git add run_agent.py
git commit -m "chore(run_agent): add GMAIL_MAX_RESULTS env, row counts, dedupe URLs" -m "- Use GMAIL_MAX_RESULTS env (default 50) instead of hardcoded 15
- Add rows before/after for upsert; log unique URL count
- Dedupe URLs before upsert; refresh worksheet after upsert"
```

---

## Commit 6: Debug logging (optional — remove if not desired)

**Files:** `agent/fetch_manager.py`, `scripts/upsert_pending.py`

**Summary:** `chore: add debug logging to fetch and upsert`

**Description:**
```
- fetch_manager: log record count, fetch_status distribution, first record keys
- upsert_pending: log index size, existing vs new counts, sample keys
```

**Commands:** (only if you want to keep debug logging)
```bash
git add agent/fetch_manager.py scripts/upsert_pending.py
git commit -m "chore: add debug logging to fetch and upsert" -m "- fetch_manager: log record count, fetch_status distribution, first record keys
- upsert_pending: log index size, existing vs new counts, sample keys"
```

**Note:** If you prefer to remove this debug logging before committing, say so and we can revert those changes.

---

## Commit 7: .gitignore

**Files:** `.gitignore`

**Summary:** `chore: add debug scripts to .gitignore`

**Description:**
```
Ignore scripts/debug_sheet_write.py and scripts/test_write_scoring.py
```

**Commands:**
```bash
git add .gitignore
git commit -m "chore: add debug scripts to .gitignore" -m "Ignore scripts/debug_sheet_write.py and scripts/test_write_scoring.py"
```

---

## Excluded (not in any commit)

- `docs/data:linkedin_debug.csv` — debug artifact
- `scripts/debug_linkedin_discovery.py` — debug script
- `scripts/debug_swooped.py` — debug script
- `.cursor/rules/ask-before-editing.mdc` — Cursor rule (add if you want it versioned)

---

## All-in-one script (after you approve)

```bash
# Commit 1
git add agent/sheet_client.py
git commit -m "fix(sheet): use table_range=A1 so append starts at column A" -m "Without table_range, the Sheets API auto-detects the \"table\" and may append starting at the first column with data (e.g. O) instead of A. Passing table_range=\"A1\" forces append to always start at column A."

# Commit 2
git add agent/scorer.py config.py
git commit -m "fix(scorer): auto-reject closed roles, expand large enterprise list" -m "- Auto-reject jobs with \"no longer accepting applications\" before LLM scoring
- Add Oracle, Meta, Apple, Salesforce, IBM to large enterprise rejection list
- Add SWOOPED_URLS_PATH to config for Swooped pipeline"

# Commit 3
git add agent/swooped_discovery.py scripts/swooped_upsert.py data/Swooped_URLs.txt run_greenhouse.py scripts/greenhouse_upsert.py
git commit -m "feat(swooped): add Swooped discovery to Greenhouse pipeline" -m "- Scrape Swooped search URLs for jobs with full descriptions
- Append to Greenhouse tab with source=swooped, fetch_status=fetched (no fetch needed)
- Add source column to greenhouse_upsert; run_greenhouse runs both Greenhouse and Swooped discovery"

# Commit 4
git add README.md docs/HANDOFF_V2_COMPLETE.md LEARNING_JOURNAL.md
git commit -m "docs: update README, HANDOFF_V2, LEARNING_JOURNAL" -m "- README: scoring rules, auto-reject closed roles, large enterprise list, table_range fix
- HANDOFF_V2: pre-filter for closed roles, table_range note for Sheet storage
- LEARNING_JOURNAL: entry #14 (Sheet alignment & auto-reject fixes, Mar 6 2026)"

# Commit 5
git add run_agent.py
git commit -m "chore(run_agent): add GMAIL_MAX_RESULTS env, row counts, dedupe URLs" -m "- Use GMAIL_MAX_RESULTS env (default 50) instead of hardcoded 15
- Add rows before/after for upsert; log unique URL count
- Dedupe URLs before upsert; refresh worksheet after upsert"

# Commit 6 (optional - omit if removing debug logging)
git add agent/fetch_manager.py scripts/upsert_pending.py
git commit -m "chore: add debug logging to fetch and upsert" -m "- fetch_manager: log record count, fetch_status distribution, first record keys
- upsert_pending: log index size, existing vs new counts, sample keys"

# Commit 7
git add .gitignore
git commit -m "chore: add debug scripts to .gitignore" -m "Ignore scripts/debug_sheet_write.py and scripts/test_write_scoring.py"
```

---

Review and approve before running. Say which commits to run, or if you want changes (e.g. drop commit 6, add .cursor/rules, etc.).
