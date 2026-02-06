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

---

## Things to Remember

- **Data analysis beats assumptions:** Check the actual data before implementing solutions
- **Simple first, complex later:** Try the simplest fix before adding dependencies
- **Own the decisions:** AI executes, but you decide strategy
- **Historical context matters:** What changed between working and not working?
- **User experience trumps technical purity:** Readable timestamps > technically correct UTC

---

*This is a living document. Add to it as you continue learning.*
