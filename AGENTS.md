# Agent Notes

- Keep temporary/debug files inside `.tmp/` (repo-local), not `/tmp`.
- Reason: using `.tmp/` avoids sandbox/escalation prompts and keeps scratch artifacts in the workspace.
- Keep `README.md` up to date whenever code changes alter behavior, flags, workflows, or outputs.
- For non-Unicode output, rely on `src/deps/printers.py`'s Unicode-to-ASCII map instead of adding ad-hoc fallbacks at call sites.
- Keep terminal output spacing block-based and explicit: for adjacent rendered UI blocks, maintain exactly one blank line separator (never zero, never two+). Avoid ad-hoc scattered `print()` newlines; prefer reusable helpers at block boundaries.
- Keep count-based user-facing text grammatically correct (`1 row` vs `2 rows`, `1 scraper` vs `2 scrapers`, matching verbs like `differs` vs `differ`).
- Stay aware of files with existing uncommitted edits in the worktree, and do not accidentally include unrelated changes when staging or committing task-specific work.
- When reporting completed commits to the user, include the commit hash and the commit message summary (short text only, not full patch/log output).
- Agent SHOULD proactively and frequently create commits when appropriate (especially after coherent, validated progress).
- If a change is a minor tweak to the immediately previous change, amend the previous commit instead of creating a new commit.
- When amending, update the commit message if needed so it accurately reflects the revised scope.
- If commit strategy needs special handling (squash/split/message format), user will specify.

## Price Mismatch Workflow (Canonical Procedure)

Known prices are regression checks for scraper correctness. Treat every mismatch
as test triage, not noise.

### Definitions

- A **quad** is:
  `(seller, model, condition, storage)`.
- The expected result for a quad lives in `data/known-prices.json`.
- The expected result includes:
  - query URL(s) used
  - known-good computed price
- Human-verified price is the source of truth.

### Core rules

- Do not invalidate cache by default.
- Work one failing quad at a time unless asked otherwise.
- Keep cache invalidation narrow and explicit when needed.

### Decide mode first (before changing anything)

1. **Cached regression mode** (no invalidation):
   - Use when the known-good value is believed to correspond to current cached
     HTML in the repo.
   - Purpose: detect parser regressions against fixed input.
   - A mismatch here usually means scraper logic drift or parser bug.

2. **Refresh / reverification mode** (targeted invalidation):
   - Use when fresher market data is desired, or when known-good data may have
     been verified against different HTML, or when explicitly requested.
   - Invalidate only the target quad's relevant cache entries.
   - Include dependent pages only if required (for example PDP/detail pages).
   - Never broad-wipe cache unless explicitly requested.

### Standard procedure for a mismatch

1. Pick one failing quad: `(seller, model, condition, storage)`.
2. Choose mode: cached regression vs refresh/reverification.
3. Run focused command using:
   - `--search-sellers`
   - `--search-models`
   - `--search-storages`
   - `--search-conditions`
4. Capture and share:
   - computed price
   - query URL(s)
   - listing URL (if present, or when requested)
5. Ask human to verify price on live site when verification is part of the task.
6. If verification is performed, update `data/known-prices.json` with the
   human-verified value for that quad.
7. If computed price still differs from verified price:
   - treat as failing test case
   - fix scraper logic
   - rerun same quad
   - repeat until match

### How to interpret results

- Mismatch in cached regression mode:
  - likely parser bug/regression.
- Mismatch after refresh:
  - could be market movement, DOM/query behavior change, or parser bug.
  - reverify manually, then decide between data update only vs parser fix.
- URL mismatch with matching price:
  - still important; query intent drift can hide future failures.

### Logging policy

- Known-price mismatches are loud warnings (non-fatal).
- Warnings must clearly state:
  - that this is a known-price mismatch
  - which quad is affected
  - whether mismatch is URLs, price, or both
  - expected vs actual values
- Preserve user-intended logging wording/formatting unless asked to change.

### Commit and change hygiene

- Keep cache edits minimal and auditable.
- Keep logic fixes narrow and evidence-driven.
- Add comments for non-obvious scraper behavior.
- Commit coherent validated progress proactively.
- Minor follow-up tweak to immediately previous change => amend previous commit.
- Never overwrite unrelated user changes.
