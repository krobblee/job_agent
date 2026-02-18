# Learning Journal: Building Job Agent with AI

This document captures key moments where I (Katie) actively problem-solved and contributed insights, rather than just accepting AI suggestions.

---

## Key Problem-Solving Contributions

### 1. **Identifying the LinkedIn URL Pattern Issue** (Feb 5, 2026)

**Context:** AI suggested implementing full browser automation (Playwright) to bypass LinkedIn's login walls. This would have added significant complexity and dependencies.

**My Contribution:** 
- Analyzed the data in my Sheet
- Compared successful vs failed fetch attempts
- **Discovered the root cause:** URLs from Gmail had `/comm/` in the path (`linkedin.com/comm/jobs/view/`) while direct LinkedIn URLs didn't (`linkedin.com/jobs/view/`)
- **Proposed simple solution:** Strip `/comm/` from URLs instead of adding browser automation
- This saved time, complexity, and kept the solution lightweight

**Impact:** 
- ✅ **CONFIRMED SOLUTION** - URL normalization completely solved the LinkedIn fetching issue
- Avoided unnecessary technical complexity (Playwright browser automation)
- Kept the solution lightweight and fast
- Jobs fetched jumped from 65 → 90 after implementing the fix

**What I learned:** 
- Data analysis can reveal simpler solutions than proposed technical fixes
- Always compare working vs non-working examples to find patterns
- Question whether complex solutions are necessary

---

### 2. **Critical Architectural Boundaries** (Feb 5, 2026)

**Context:** During refactoring, many architectural decisions needed to be made.

**My Contribution:**
- Explicitly stated: "You do NOT make architecture or product decisions. I own all of those."
- Set clear rules about when AI should stop and ask vs proceeding
- Maintained ownership of product direction while delegating implementation

**What I learned:**
- Importance of clear boundaries when working with AI
- AI is excellent for execution, but human judgment needed for strategy
- Being explicit about decision-making authority prevents scope creep

---

### 3. **Timezone Usability Issue** (Feb 5, 2026)

**Context:** Timestamps were in UTC format: `2026-02-05T18:09:55+00:00`

**My Contribution:**
- Identified that UTC timestamps were confusing and not user-friendly
- Requested Eastern Time (EST/EDT) with proper daylight saving handling
- Thought about end-user experience, not just technical correctness

**What I learned:**
- Technical correctness (UTC) isn't always the best user experience
- User-facing data needs to be human-readable
- Small UX improvements matter

---

### 4. **Recognizing the Real Fetching Problem** (Feb 5, 2026)

**Context:** AI thought fetching was "working" during refactoring because it wasn't throwing errors.

**My Contribution:**
- Actually checked the Google Sheet data
- Reported: "I'm seeing 'LinkedIn Login' in the role_title column"
- Realized the fetcher was technically working but getting wrong content
- Asked clarifying questions: "why did it work before without changing headers?"

**What I learned:**
- "Working" from a technical perspective doesn't mean "working" for the user
- Always verify actual output, not just that code runs without errors
- HTTP 200 OK doesn't mean you got the right content

---

### 5. **Historical Context Investigation** (Feb 5, 2026)

**Context:** AI assumed LinkedIn had always been blocking scrapers.

**My Contribution:**
- Checked historical data in Sheet (Jan 23 successful fetch)
- Distinguished between "source: linkedin" vs "source: gmail"
- Provided timeline: "it worked before when the source was linkedin, never w/ gmail"
- This led to discovering the `/comm/` URL difference

**What I learned:**
- Historical data can provide important clues
- What worked before vs now reveals changes in the system
- Specific examples are more valuable than general descriptions

---

### 6. **Diagnosing the Row Deletion Caching Bug** (Feb 11, 2026)

**Context:** After deleting rows from the Sheet, the fetch pipeline stopped working. Terminal showed "✓ Fetched 25 jobs" but Sheet remained unchanged (fetch_status = pending, fetch_attempts = 0).

**My Contribution:**
- Recognized the timing: "It was working at 10:38 AM EST, then I deleted rows, now it's broken"
- Observed the symptom: "Data is being written willy-nilly all over the sheet" - updates going to wrong rows
- Provided specific evidence: Showed exact row data with timestamps proving the pattern
- Identified that the issue started after row deletion, not before
- Asked clarifying questions to help AI understand the messy state

**AI's Investigation:**
- AI initially focused on wrong causes (authentication, rate limits, LinkedIn blocking)
- User's timeline observation ("worked before deletion") redirected investigation
- AI discovered gspread worksheet caching was holding stale row numbers
- Root cause: After row deletion, row numbers shifted but cached worksheet had old positions

**Solution:**
- Added `refresh_worksheet()` method to force gspread to reload sheet data
- Call refresh before fetching to clear any stale row number cache
- This ensures row index is always fresh, even after sheet modifications

**Impact:**
- ✅ Fetch pipeline now resilient to sheet modifications (row deletion/insertion)
- ✅ System can handle manual sheet cleanup without breaking
- ✅ Starting fresh (delete all rows) now works correctly

**What I learned:**
- Timing matters: "when did it break?" is as important as "what's broken?"
- Sometimes the solution is clearing a cache, not fixing logic
- Communicating observed symptoms clearly helps AI debug faster
- Manual data operations (like deleting rows) can have unexpected side effects in systems that cache state

---

### 7. **Profile Hard NOs — Catching a Scoring Gap** (Feb 18, 2026)

**Context:** A job marked as true_match was in the defense industry — a hard NO for Katie.

**My Contribution:**
- Noticed the mismatch: "one of the jobs accepted as a true_match is in the defense industry"
- Requested prompt update to exclude defense, crypto, and government sectors
- Ensured both config PROFILE and scorer REJECT rule reflected these exclusions

**What I learned:**
- Spot-check LLM output against real results — the profile is only as good as what's enforced
- Catching edge cases early prevents bad recommendations

---

### 8. **Discovery Chain Insight** (Feb 13–14, 2026)

**Context:** Plan was to scrape aggregators and extract Greenhouse links.

**My Contribution:**
- Pushed back: "We don't know they're necessarily on Greenhouse"
- Clarified the flow: aggregator → company profile → careers page → check if Greenhouse
- This led to verifying topstartups.io/jobs — which *does* have direct Greenhouse links, simplifying the design

**What I learned:**
- Question whether data exists where the plan assumes — verify before building
- Asking "how does this actually work?" surfaces simpler or different approaches

---

### 9. **Publishing Boundaries and Security Ownership** (Feb 18, 2026)

**Context:** Preparing the repo for portfolio; AI had committed without explicit permission.

**My Contribution:**
- Drove the pre-publish security checklist: rotate keys, .env.example, stop tracking credentials
- Set the rule: "Never commit unless I explicitly say so" (documented in CONTINUATION_PROMPT_V3)
- Owned the publish process — didn't defer; ran through the checklist and made decisions

**What I learned:**
- Boundary-setting extends beyond architecture — workflows (who commits, when) matter too
- Taking ownership of security steps prevents shortcuts and oversights

---

### 10. **Greenhouse Tab Separation** (Feb 13, 2026)

**Context:** Adding Greenhouse pipeline; AI initially assumed jobs could live in the same sheet as LinkedIn.

**My Contribution:**
- Said: "I don't want to pollute the current Google Sheet I have for LinkedIn jobs"
- Asked for a separate tab and a user-friendly structure for the front end (Sheet is her only UI)
- Kept pipelines logically separate while sharing fetch/scoring logic

**What I learned:**
- Data organization reflects how you work — separate concerns when they serve different workflows
- "User-friendly" means designing for how the data will actually be used

---

## Design Decisions I Made

### Hybrid Approach for Fetching
- Chose to start with enhanced HTTP headers (simple)
- But designed system for easy upgrade to browser automation (future-proof)
- Explicitly stated: "keep in mind we'll likely want to move to a more robust approach if I decide to productize"
- **Lesson:** Balance immediate needs with future flexibility

### Refactoring Philosophy
- Insisted on one-step-at-a-time approach
- Required testing after each change
- Rejected adding features during refactoring
- **Lesson:** Disciplined process prevents chaos

---

## Questions That Led to Better Solutions

1. "Why would you rename it?" → Forced clarification of architectural intent
2. "Why did it work before without changing headers?" → Uncovered the real problem
3. "Can we try stripping out 'comm' from a url?" → Simple solution instead of complex one
4. "We don't know they're necessarily on Greenhouse" → Led to verifying aggregator structure
5. "That's a NO GO for me" (re: defense) → Caught profile gap, added hard NOs

---

## Things to Remember

- **Data analysis beats assumptions:** Check the actual data before implementing solutions
- **Simple first, complex later:** Try the simplest fix before adding dependencies
- **Own the decisions:** AI executes, but you decide strategy
- **Historical context matters:** What changed between working and not working?
- **User experience trumps technical purity:** Readable timestamps > technically correct UTC
- **Spot-check LLM output:** Profile gaps show up in real results — verify
- **Boundaries extend to workflows:** Who commits, when, and how — document and enforce

---

*This is a living document. Add to it as you continue learning.*
