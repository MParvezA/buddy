# Codex Daily — Implementation Review

## Decision

Status: review-failed
Reviewed commit: `0b43951089cd28064a93b7fcd208e3d97bb944e8`
Reviewed slices: `d3f0185` through `0b43951` (Slices 01–06)
Next action: return to `4_Implement` for one focused review-corrections slice, then
repeat this review before cleanup.

The complete daily loop is implemented and the aggregate app checks pass, but
the reviewed commit is not cleanup-ready. The findings below are verified
against the approved design, alignment, slice plans, implementation, tests, the
installed Codex App Server schema, and independent read-only review passes.

## Must Fix Before Cleanup

### R1 — Protect the loopback HTTP boundary

The loopback service accepts arbitrary `Host` and `Origin` values. A DNS-rebinding
origin can therefore read export data or call destructive local-data operations;
the confirmation phrase is fixed and shipped to the browser.

- Evidence: `src/server/app.ts` installs no host/origin validation before
  registering `/api/operations/*`; an isolated Fastify injection using
  `Host: attacker.example` and `Origin: https://attacker.example` returned `200`
  for export and confirmed delete-all.
- Required correction: allow only loopback hosts and same-origin browser
  requests, with focused route tests for hostile Host/Origin combinations.

### R2 — Make transient thread content explicitly non-cacheable

`GET /api/observer/threads/:threadId` returns full request-scoped thread content
without `Cache-Control: no-store`, so browser or intermediary caches may retain
content the product describes as transient.

- Evidence: `src/server/codex/observer-routes.ts:62` returns detail directly; a
  route probe returned transcript content with no cache-control header.
- Required correction: send `no-store` on success and relevant failures, and
  request the resource with browser cache disabled.

### R3 — Make day deletion internally consistent

Day deletion removes normalized activities and attention rows but leaves
`observed_threads.last_activity_at` pointing at deleted activity. When attention
restarts, an active thread can immediately recreate a `possibly_stale` item from
that deleted timestamp.

- Evidence: `src/server/privacy/privacy-service.ts` deletes activities but never
  recomputes the denormalized field used by
  `src/server/attention/attention-engine.ts`.
- Required correction: recompute each affected thread's retained
  `last_activity_at` transactionally and prove deleted activity cannot recreate
  attention.

### R4 — Recover narrative work without blocking factual access

A crash after snapshot creation leaves narrative status permanently `pending`;
startup skips the occupied automatic slot and narrative retry rejects `pending`.
In addition, missed-run startup awaits the whole optional narrative stage before
the application can listen, despite the factual snapshot already being durable.

- Evidence: `src/server/reports/report-service.ts:95-126` persists `pending` and
  rejects its retry; `report-scheduler.ts:40-44` awaits recovery. A focused probe
  measured scheduler startup waiting for the injected narrative provider, and a
  persisted restart probe left the report permanently unretryable.
- Required correction: mark startup-orphaned pending work as safely failed or
  otherwise recoverable, and let missed recovery expose facts without awaiting
  optional interpretation. Preserve bounded drain behavior for deletion and
  shutdown.

### R5 — Give server-request episodes reconnect-stable identities

Approval/input source keys use only thread ID plus App Server request ID. Request
IDs may be reused by a new connection, causing a distinct same-thread episode to
collide with the earlier durable key and disappear.

- Evidence: `src/server/codex/activity-normalizer.ts` builds
  `request:<thread>:<request-id>:pending`; a same-thread reused-ID probe inserted
  the first episode and discarded the second.
- Required correction: namespace request episodes by connection generation or a
  stable item/approval identity while keeping resolution correlation exact.

### R6 — Coordinate every database write during deletion

`GET /api/planning` calls `PlanningService.view()`, which creates the current day,
but the write coordinator exempts every GET. A dashboard load can therefore write
while exclusive deletion considers ingestion quiescent.

- Evidence: `src/server/app.ts:139-145` exempts GET; 
  `src/server/planning/planning-service.ts:65-69` writes via `ensureDay`.
- Required correction: track this route as a writer or make planning reads
  genuinely read-only, with a concurrent deletion regression test.

### R7 — Do not expose editable Settings defaults before retained state loads

Settings renders enabled Europe/Berlin/18:00 defaults before the retained
schedule request finishes. On a slow or failed load, Save can overwrite the
operator's real preferences with those defaults.

- Evidence: `src/client/pages/SettingsPage.tsx:24-53,146-175`.
- Required correction: represent loading explicitly and disable editing/saving
  until retained settings have loaded successfully.

### R8 — Synchronize the mounted client after a timezone change

Saving a timezone that crosses a local-date boundary updates the server
immediately, but the mounted planning and report providers retain the old local
date. Subsequent task mutations and manual report generation can target the
wrong day until a full reload.

- Evidence: Settings updates only local component state; planning/report
  providers reload only through their own counters, while report preview passes
  the cached planning date.
- Required correction: invalidate/reload both providers after schedule changes
  and prove a cross-date timezone change updates subsequent writes.

### R9 — Surface automatic report failures

The scheduler retains `lastFailure`, but neither the dashboard report preview nor
Settings presents it. This violates the approved requirement to surface
scheduling failures and leave manual recovery available.

- Evidence: `src/server/reports/report-scheduler.ts` and `src/shared/report.ts`
  expose the value; production client rendering does not.
- Required correction: show a persistent, comprehensible automatic-run failure
  beside the manual generation/retry path.

## Should Fix In The Correction Slice

- Clamp reconnect jitter to the configured maximum. The current calculation can
  schedule 120% of `reconnectMaxMs`.
- Prevent equal-second inventory rows from overwriting newer live runtime/title
  state; current `updated_at >=` conflict handling accepts the regression.
- Preserve per-thread normalized activity access in thread detail rather than
  relying on the global 200-item dashboard snapshot window.
- Show deletion errors inside the open confirmation dialog, distinguish
  thread-attention load failure from an authoritative empty history, and
  distinguish report-history loading/error from an empty history.
- Make the Settings/report-history browser tests independently reproducible;
  the focused report-regeneration test currently expects state created by an
  earlier test.
- Remove the undocumented `CODEX_DAILY_LOCAL_DATE` override from the production
  entry point and place the deterministic clock in a test-only entry point.
- Either apply an explicit active/recent policy to “Active Codex chats” or rename
  and bound the section so a large unarchived history cannot overwhelm Today.
- Expand keyboard, disconnected-state, and 390px workflow evidence enough to
  support the acceptance claim; record any deliberately narrower proof honestly.
- Remove the eight extra blank lines at EOF so
  `git diff --check d3f0185^..HEAD` passes.

## Follow-Up

No deferred `FUP-001` through `FUP-006` item was accidentally implemented or made
mandatory. Dependency-audit remediation remains adjacent debt rather than a
review correction.

## Accepted Deviations

- The default standalone observer cannot see live approval/question requests
  owned by another Codex process. The UI and documentation disclose this, while
  shared-live mode covers the supported capability.
- Deterministic fake App Server coverage replaces a real ordinary-chat smoke to
  avoid exposing chat content. The installed Codex CLI
  (`0.146.0-alpha.3.1`) generated schema independently confirms the implemented
  `thread/list`, `thread/read`, `thread/start`, `turn/start`, approval, input, and
  resolution method/field shapes.
- Playwright needs permission to bind its loopback server.
- The full ROS test run retains the recorded untouched `buddy_bringup` hang and
  `buddy_navigation` failure. The 16-package inventory, full build evidence,
  protected-path diff, and 4 repository contracts remain valid.
- Process restart is proven at the persistent product boundary rather than
  duplicated as a browser process-restart journey.

## Verification Reviewed

- `npm run check`: passed; 30 files and 87 tests.
- `npm run test:e2e`: passed as a full ordered suite; 14 passed and 6 mobile
  mutation duplicates skipped.
- Isolated report-regeneration Playwright scenario: failed because it expected a
  prior test's report.
- Production loopback health and signal smoke: passed.
- Open-SSE shutdown probe: passed.
- Installed Codex App Server experimental schema generation: passed and matched
  the adapter's used protocol surface.
- `python3 -m pytest buddy_bringup/test/test_repository_contracts.py`: 4 passed.
- `colcon list`: unchanged 16 packages.
- Protected `buddy_*` and `docs/contracts` diff: empty.
- `git diff --check d3f0185^..0b43951`: failed on eight blank lines at EOF.

