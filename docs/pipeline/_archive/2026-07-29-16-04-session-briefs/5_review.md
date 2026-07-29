# Recent Session Briefs — Implementation Review

Archived after completed implementation review and cleanup.

## Review Scope

- Reviewed commits: `745c0f8`, `b35d70f`, `92ea030`, and `bc73241`
- Reviewed sources: `1_design.md`, `2_alignment.md`, `3_plan.md`, all four
  implemented slice plans, the UX decision catalogue, implementation code,
  focused tests, full web verification, and browser evidence
- Decision: revision required; return to `4_Implement` before cleanup

## Must Fix Before Cleanup

1. **Validate the production analysis-thread response before sending source
   text.** `ObserverService.createSessionBriefAnalysisThread()` currently checks
   only the returned thread ID. It must require the actual response model to be
   `gpt-5.6-sol` and the returned thread to be ephemeral before registering the
   ID or starting the analysis turn. The deterministic fake currently proves
   the gap by returning a non-ephemeral response that production accepts.
2. **Never project a failed ephemeral analysis-thread creation.** Buffered
   `thread/started` notifications are replayed as ordinary observer events when
   `thread/start` later rejects or returns malformed data. Ephemeral threads
   must remain excluded on both success and failure paths.
3. **Bind transient source content to the queued source revision.** The gateway
   receives `sourceUpdatedAt` but does not compare it with the `thread/read`
   response revision. A changed source can therefore be summarized and stamped
   as an older revision. Reject/supersede mismatched reads before generation or
   promotion.
4. **Cancel obsolete active workers when a thread leaves recent-10 or changes
   revision.** Reconciliation deletes the durable job but does not abort its
   in-memory worker, so obsolete work can consume one of the two worker slots
   until timeout.
5. **Suppress pre-delete brief snapshots during drain.** Worker finalizers
   publish while destructive maintenance is waiting for `pauseAndDrain()`,
   exposing an obsolete pre-delete `analyzing` snapshot. Only the authoritative
   post-delete snapshot may be published after resume.
6. **Add the missing operational regression proof.** Cover response
   model/ephemeral rejection, failed-create exclusion, source-revision mismatch,
   active window-exit cancellation, SSE-aware deletion drain, transactional
   rollback/late-promotion safety, and a persistent 11-session day-one to
   day-two restart/reconnect lifecycle.

## Should Fix In The Same Correction

- Map a rejected/missing `thread/read` to terminal `source_missing` rather than
  retrying it as `observer_unavailable`.
- Make the browser session-brief parser reject or reconstruct away undeclared
  snapshot/item/brief fields so raw transcript/prompt properties cannot enter
  React state.
- Disable refresh-all for an empty eligible window.
- Use state-accurate connecting/reconnecting/disconnected retry copy.
- Keep the card `<time dateTime>` value identical to the timestamp used for its
  visible text.
- Strengthen UI proof for overlapping duplicate refresh suppression, pending
  disabled semantics, initial loading, unlinking, and queued-to-analyzing live
  transitions.

## Accepted Deviations

- The single synthetic-only installed-host proof was blocked after 37 ms with
  the formerly coarse redacted category `contract_failed`. It read no history,
  used no fallback, and was not retried. Future runs now distinguish
  `host_unavailable`, `request_rejected`, and `model_contract_failed`; live Sol
  success remains unproven.
- Playwright requires host-context execution because sandboxed `tsx` IPC setup
  fails with `EPERM`.
- Migration 007's singleton durable coordinator epoch is an accepted
  implementation of the approved promotion guard.
- Seven existing high-severity npm audit advisories remain outside this feature.
- ROS verification retained one unchanged `buddy_bringup`
  `pytest.missing_result` error; protected ROS paths were untouched.

## Verification Reviewed

- `npm run check`: 43 files, 155 tests, lint/typecheck/build passed
- Full Playwright: 20 passed, 8 intentional mobile mutation skips
- Repository contracts: 4/4 passed
- ROS inventory/build: 16 packages; build passed
- ROS tests: 233 tests, one unchanged missing-result error, 13 skipped
- Production SIGINT/SIGTERM and SQLite reopen checks passed
- Independent focused backend/frontend review suites passed
- Whitespace, protected paths, and artifact privacy scans were clean

## Correction Resolution

Status: passed after correction

Correction commit: `Review corrections: harden recent session briefs` (this
status-bearing commit)

The correction pass:

- validates the actual returned `gpt-5.6-sol` model and ephemeral thread before
  sending source text;
- suppresses the candidate internal thread on rejected, malformed,
  wrong-model, non-ephemeral, and contradictory notification/response paths;
- binds `thread/read.updatedAt` to the desired revision and supersedes changed
  work;
- aborts in-memory work on source revision change and recent-window exit;
- suppresses drain-time SSE publication until post-maintenance resume;
- maps rejected source reads to `source_missing`;
- reconstructs browser DTOs from an explicit allowlist;
- corrects empty refresh, connection copy, timestamp, pending, and focus
  behavior; and
- adds the missing persistent overnight, deletion/rollback/late-promotion,
  model-boundary, revision, cancellation, SSE, privacy, and UI regression
  coverage.

Post-correction verification:

- `npm run check`: 43 files, 174 tests, lint/typecheck/build passed
- Correction-focused suites: 51 tests passed before the final replay hardening
- Gateway model/internal-thread boundary: 12/12 passed after final hardening
- Full Playwright: 20 passed, 8 intentional mobile mutation skips
- Operational/privacy focused suites: 13 tests passed
- Built-artifact privacy scan, whitespace, and protected paths: clean
- Host model proof: intentionally not rerun

Final decision: all must-fix and should-fix review findings are resolved.
Proceed to `6_Cleanup`.
