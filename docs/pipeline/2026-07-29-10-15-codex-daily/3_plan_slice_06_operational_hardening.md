# Codex Daily — Slice 06 Operational Hardening

## Implementation Status

Status: planned
Commit:
Verification:
Deviations:
Follow-ups:

## Context And Selected Slice

- Repository: `/home/syncrobot/buddy`
- Planning branch: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Sequence: `06 of 06`
- Selected vertical slice: **Operational Hardening**
- Dependencies: approved, implemented, and individually verified Slices 01–05.
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`, `CURRENT.md`,
  `docs/about/05_ux_decision_catalogue.md`, and every approved
  `3_plan_slice_01_*.md` through `3_plan_slice_05_*.md`.

Prove and harden the complete local lifecycle without adding a new product
capability:

`Morning review → Plan → Observe → Needs You → Evening report → Next morning`

The slice owns cross-cutting recovery, privacy controls, diagnostics,
accessibility/responsive polish, production startup documentation, and final
non-regression evidence.

## Repository Rules

- Consulted: root `README.md`; feature design, alignment, roadmap, current routing,
  UX catalogue, all Slice 01–05 plans, repository contract tests, and ROS
  build/test instructions. `docs/rules/README.md` and a root `AGENTS.md` do not
  exist.
- Constraints applied: extend the single `apps/codex-daily/` Node 24/npm 11
  Fastify + React/Vite application and its established SQLite, App Server,
  attention, and reporting boundaries; bind only to loopback; preserve minimal
  retention and read-only ordinary Codex behavior; do not enter the colcon package
  graph or modify Buddy runtime behavior.
- Rule updates: None

## Exact Scope

- Add one deterministic full-lifecycle test harness spanning the behaviors
  delivered by Slices 01–05.
- Harden App Server disconnect/reconnect, replay, ordering, and deduplication.
- Harden local-day and report scheduling across timezone changes, daylight-saving
  transitions, restarts, and missed scheduled runs.
- Add inspect/export and destructive deletion controls for Codex Daily's local
  monitor data only.
- Add privacy-safe operational diagnostics for database, scheduler, observer, and
  report generation health.
- Complete keyboard, semantic, contrast/status, screen-size, loading, empty,
  disconnected, and error-state polish.
- Verify graceful production startup/shutdown and document exact local setup,
  configuration, data location, backup/export, deletion, and troubleshooting.
- Run the full web and ROS verification matrices and prove the existing workspace
  remains outside the web app's ownership.

## Explicit Non-Goals

- New planning, observer, attention, or report product semantics.
- Cloud hosting, remote access, accounts, authentication, teams, sync, telemetry,
  third-party integrations, OS installers, containers, systemd services, or
  automatic startup.
- Sending prompts, answering approvals/questions, steering/interruption,
  archiving, deleting, or otherwise mutating Codex threads.
- Deleting Codex App Server history, Codex credentials, repositories, worktrees,
  or ROS data.
- Persisting full transcripts, raw protocol payloads, secrets, or unredacted
  diagnostic logs.
- Repository-aware completion evidence, weekly reporting, cost analysis, or other
  deferred feature work.
- Broad refactors or replacement of the established framework, database, adapter,
  scheduler, or test stack.

## Follow-Up Scope

- Included `FUP-###` items: none.
- Still deferred: `FUP-001` evidence-backed completion, `FUP-002` weekly review,
  `FUP-003` third-party integrations, `FUP-004` multi-device sync, `FUP-005`
  cost/limit insights, and `FUP-006` proactive chat control.
- Hardening must test the boundaries around these items, not implement them.

## Central Issue Scope

- Included issue IDs: none.
- Still deferred issue IDs: none identified.
- Newly created issue IDs: none.
- The repository has no central issue register. Record newly discovered durable
  debt separately before using an issue ID; do not absorb unrelated debt into
  this final slice.

## Canonical Mental Model And Required Cleanup

The canonical durable unit remains the operator's local day. Chats are observed
evidence, attention is a derived local projection, and reports reconcile facts
before optional interpretation.

Recovery must preserve that model:

- replay may update an existing observation but never create duplicate activity,
  attention, task links, or report snapshots;
- unknown/disconnected state stays unknown/disconnected;
- a completed turn never completes a task;
- a missed report is created at most once for a local date;
- deleting local monitor data never implies or performs deletion in Codex; and
- scheduled or intelligent reporting never blocks access to factual local data.

Required cleanup:

- Remove remaining representative data, mock-only production branches, duplicate
  clocks/schedulers, unbounded retry loops, swallowed errors, and stale
  compatibility names from prior slices.
- Keep one injected clock/timezone boundary, one observer reconnect policy, one
  event identity/deduplication path, one report uniqueness rule, and one local
  deletion coordinator.
- Remove debug endpoints or logs that expose raw prompts, responses, credentials,
  protocol payloads, or filesystem contents.
- Remove dead dependencies, unused migrations/types, placeholder settings/report
  copy, and test-only controls from production bundles.
- Do not preserve two schema/API shapes “for compatibility”; migrate tests and UI
  to the canonical implemented contract.

## Privacy And Diagnostics Contract

The Settings secondary view must clearly identify Codex Daily as local-only and
show:

- configured timezone/report time;
- database path or an unambiguous local data-location description;
- retained data categories and record counts;
- oldest/newest retained dates where applicable;
- observer connection state, last successful sync, reconnect attempt/backoff,
  last redacted error category/time, and replay/deduplication counters;
- scheduler next-run, last-run, missed-run recovery, and last factual/narrative
  outcomes; and
- application/runtime version information useful for troubleshooting.

Provide a deterministic JSON export of the actual local monitor tables using
stable product DTOs. It may include plans, task links, normalized activity,
attention state, reports, and preferences, but never fetched transcript bodies,
credentials, or raw App Server payloads.

Provide explicit, confirmed deletion for:

- one retained local day and its monitor-owned dependent records; and
- all Codex Daily local data, including preferences, followed by default
  reinitialization.

Deletion must coordinate the observer, scheduler, report generator, and database
so no in-flight write repopulates data during the operation. The UI must explain
that resuming monitoring can rediscover current Codex thread metadata. It must
never invoke App Server thread archive/delete/mutation methods. Tests must assert
zero outbound Codex mutations and verify rollback on a failed local deletion.

Deleting one day removes that day's tasks, links, attention projections, and
report snapshots. Cross-day successor tasks remain on their own dates and their
immediate `origin_task_id` becomes null through the canonical foreign-key policy;
the export records that lineage may be shortened by deletion. Delete-all removes
all monitor-owned rows. Neither operation touches Codex history.

Diagnostics are bounded product state, not a transcript/log viewer. Store only
redacted error codes/categories and timestamps when persistence is needed.

## Likely Files, Modules, Components, Tests, And Docs

Extend actual Slice 01–05 names rather than creating parallel services. Likely
paths:

- `apps/codex-daily/src/shared/operations.ts`
- `apps/codex-daily/src/server/runtime/lifecycle.ts`
- `apps/codex-daily/src/server/codex/app-server-client.ts`
- `apps/codex-daily/src/server/codex/activity-normalizer.ts`
- `apps/codex-daily/src/server/codex/observer-service.ts`
- `apps/codex-daily/src/server/storage/observer-repository.ts`
- `apps/codex-daily/test/fixtures/fake-codex-app-server.mjs` and
  `test/fixtures/app-server/*.jsonl`
- Slice 05 clock, timezone, scheduler, report repository, and fake summarizer
- `apps/codex-daily/src/server/privacy/privacy-service.ts`
- `apps/codex-daily/src/server/privacy/privacy-routes.ts`
- `apps/codex-daily/src/server/diagnostics/diagnostics-service.ts`
- `apps/codex-daily/src/server/diagnostics/diagnostics-routes.ts`
- `apps/codex-daily/src/server/app.ts` and `src/server/main.ts`
- `apps/codex-daily/src/client/pages/SettingsPage.tsx`
- settings components for diagnostics, export, and destructive confirmation
- shared shell, dashboard, report history, and error/empty/loading components
- focused Vitest tests beside the modules above
- `apps/codex-daily/e2e/full-lifecycle.spec.ts`
- `apps/codex-daily/e2e/recovery-privacy.spec.ts`
- `apps/codex-daily/README.md`
- root `README.md` only to link the bounded application's run documentation

Prefer existing scripts and dependencies. Add a narrowly scoped accessibility
test dependency only if the current Playwright/Testing Library stack cannot
provide equivalent automated checks.

## Existing Patterns And Non-Regression

- Keep Slice 01's Fastify builder/thin entry point, React shell, loopback binding,
  plain-CSS tokens, Vitest/Testing Library, and Playwright production-server
  harness.
- Keep Slice 02's transactional SQLite migrations and injected local-date clock.
- Keep Slice 03's narrow hand-written App Server decoder, standalone-history and
  shared-live capability modes, normalization boundary, bounded reconnect,
  stable event keys, and fake transport. Preserve its
  `connecting | connected | reconnecting | disconnected` connection states,
  content-free normalized activity, and
  `unknown | not_loaded | idle | active | system_error` thread runtime states
  rather than introducing hardening-only aliases.
- Keep Slice 04's certainty-preserving derivation and local-only
  acknowledgement/dismissal.
- Keep Slice 05's factual-first report, unique snapshots, injected scheduler, and
  optional narrative fallback.
- Keep dashboard order and secondary navigation unchanged.
- Keep planning/report history usable while Codex is disconnected.
- Keep all destructive controls explicit, accessible, and clearly scoped to local
  Codex Daily data.
- Keep full transcripts and credentials out of SQLite, exports, logs, diagnostics,
  tests, and screenshots.
- Preserve every `buddy_*` source, ROS contract, launch/config file, build command,
  and package-discovery result.

## Acceptance Criteria

1. A deterministic E2E scenario completes prior-day review, creates and orders
   today's outcomes, observes and links fake Codex work, derives/handles attention,
   creates factual and optional narrative reports, restarts, and begins the next
   morning without losing or duplicating state.
2. During App Server loss, planning and report history remain usable and the UI
   shows disconnected/last-known state. Bounded reconnect recovers inventory and
   live events.
3. Replayed, duplicated, out-of-order, and reconnect-overlap fixtures create no
   duplicate normalized activity, task links, attention items, or reports.
4. Reconnect backoff is bounded, observable, cancelled during shutdown, and
   deterministic under a fake timer.
5. Timezone tests cover Europe/Berlin spring-forward and fall-back boundaries,
   another configured timezone, a runtime preference change, and process restart.
   Each instant maps to the intended local day.
6. A process starting after report time creates exactly one missed factual report
   for the current local date when its automatic slot is empty. Repeated restarts,
   fall-back repeated wall time, and concurrent automatic attempts do not
   duplicate that slot; older dates are not backfilled and intentional manual
   snapshots may coexist.
7. Narrative failure still leaves a retained factual report and a useful
   diagnostic state.
8. Settings accurately shows retained-data counts/location and redacted observer,
   scheduler, and report diagnostics without transcript/credential leakage.
9. JSON export is complete for monitor-owned product records, deterministic enough
   to test, and contains no transcript bodies, secrets, or raw protocol payloads.
10. Day deletion and delete-all require explicit confirmation, affect only local
    monitor data, coordinate in-flight writers, and never send a Codex mutation.
    Day deletion removes that day's dependent monitor records, preserves
    cross-day successors with null immediate lineage, and removes that day's
    report history; delete-all resets preferences to approved defaults.
11. Keyboard-only operation covers primary/secondary navigation, dialogs, morning
    review, attention actions, manual reporting, export, and deletion. Focus is
    restored after dialogs and announced status/errors use semantic live regions.
12. Automated checks and Playwright at 390px and 1440px show no horizontal
    overflow, inaccessible unlabeled controls, color-only state, broken focus
    order, or hidden priority hierarchy.
13. `npm ci`, all app checks, production build/start, graceful SIGINT/SIGTERM
    shutdown, and a fresh temporary-data smoke pass on Node 24.
14. Codex Daily remains bound to `127.0.0.1`, generated/runtime data stays ignored,
    and documented configuration works without editing source.
15. `colcon list`, full ROS build/tests, and repository contract tests pass; Codex
    Daily is not a ROS package and no existing ROS-owned path changes.

## Ordered Implementation Tasks

1. Confirm Slices 01–05 are implemented/verified; inventory their canonical
   clocks, timers, observer keys, migrations, scheduler uniqueness, APIs, scripts,
   and remaining representative/placeholder code.
2. Write failing cross-slice tests first: full lifecycle, disconnect/replay,
   out-of-order duplicates, bounded backoff/shutdown, DST, timezone change,
   missed-run concurrency, narrative failure, export, and deletion isolation.
3. Consolidate duplicate recovery/time abstractions and close only failures exposed
   by those tests. Preserve each slice's public behavior.
4. Add coordinated lifecycle startup/shutdown so timers, App Server transport,
   report work, HTTP service, and SQLite close in a deterministic order.
5. Add privacy inspection/export and transactional day/all-data deletion with
   ingestion quiescence, explicit confirmation contracts, and zero Codex writes.
6. Add bounded redacted diagnostics and wire them into the existing Settings page
   with loading/error/empty/disconnected states.
7. Complete responsive and accessibility behavior across every real surface,
   including focus management for destructive confirmations.
8. Remove all superseded fixtures, debug leakage, dead dependencies/types, and
   production test hooks; inspect the built artifacts and database/export schema.
9. Update app-local operating documentation and add only a root README link.
10. Run the complete web, production smoke, privacy, lifecycle, and ROS verification
    matrix; update the status block with exact evidence and deviations.

## Verification Commands And Expected Outcomes

From `apps/codex-daily/`:

```bash
node --version
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run check
```

Expected: Node is `v24.x`; clean locked install succeeds; all prior and new
unit/integration/component tests pass; production builds; Playwright passes the
full lifecycle, recovery, DST/missed-run, privacy, accessibility, and 390/1440px
flows; aggregate check exits zero.

Production smoke with explicit temporary data and configuration:

```bash
CODEX_DAILY_DB_PATH=/tmp/codex-daily-hardening.sqlite \
CODEX_DAILY_TIMEZONE=Europe/Berlin \
CODEX_DAILY_REPORT_TIME=18:00 \
npm run start
```

Expected: the built app binds only to the documented loopback address, initializes
the temporary database, reports useful health/diagnostics, survives fake App
Server unavailability, and shuts down cleanly on SIGINT/SIGTERM without pending
timers or a locked database. Remove only these explicitly named temporary SQLite
files after verification.

From the repository root:

```bash
source /opt/ros/jazzy/setup.bash
colcon list
colcon build --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
ROS_LOG_DIR=/tmp/buddy-test-logs colcon test --ctest-args --output-on-failure
colcon test-result --verbose
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
git status --short
```

Expected: package discovery contains only the existing Buddy packages; full ROS
build and tests pass with no failures; repository contracts pass; no whitespace
errors or ROS/contract diffs exist; status contains only intended Codex Daily/docs
changes and preserved pre-existing work.

## Risks, Dependencies, And Stop Conditions

- This slice depends on all prior slices being complete. Stop if any status block
  is not `implemented` or its required verification is missing.
- Reconnect and scheduler races can corrupt exactly-once behavior. Require stable
  source keys, database uniqueness, transactions, and fake-timer concurrency tests;
  do not rely on debounce timing alone.
- Timezone libraries or APIs may disagree at DST boundaries. Keep one canonical
  implementation and fixture known transition instants; stop before replacing the
  time stack broadly.
- Delete-all can race with ingestion/reporting. Quiesce writers and prove rollback;
  stop if safe deletion requires killing unrelated processes or touching Codex
  storage.
- Diagnostics/export can leak sensitive content. Stop if useful diagnostics cannot
  be produced from normalized/redacted metadata.
- Full ROS verification may expose pre-existing failures. Record exact commands and
  distinguish pre-existing evidence; do not modify ROS code to make this web slice
  pass.
- Dependency/browser installation may require network access. Report the exact
  blocked command rather than changing the approved stack or weakening checks.
- Stop if hardening requires cloud/auth/team features, external telemetry, direct
  Codex state parsing, ordinary-thread mutation, full transcripts, a deferred
  `FUP-###`, broad unrelated refactors, or changes outside the app/docs boundary.
- Stop if tests cannot use isolated temporary databases/fake transports/fake time,
  production cannot remain loopback-only, or unrelated user changes overlap
  required files.

When blocked, leave a minimal reproducible failing test where safe, record the
failure and affected acceptance criterion, preserve the worktree, mark status
`blocked`, and request the smallest missing decision. Do not add compatibility
fallbacks or silently skip verification.

## Preserve Unrelated Changes

The planning worktree already contains untracked `docs/about/` and
`docs/pipeline/` content. Treat all pre-existing and concurrent edits as
user-owned. Inspect `git status --short` and relevant diffs before editing and
committing. Never reset, clean, stash, overwrite, reformat, stage, or commit
unrelated paths. Stop if overlap cannot be preserved safely.

## Expected Final Summary

Report:

- `implemented` or `blocked`, branch, and commit;
- lifecycle/recovery, time resilience, privacy, diagnostics, accessibility, and
  operating-doc behavior delivered;
- canonical files/modules changed and superseded paths removed;
- proof that deletion affected only local monitor data and no Codex mutation was
  sent;
- every web, production smoke, and ROS verification command with outcome;
- deviations, remaining risks, and `FUP-###`/issue references;
- confirmation that unrelated changes were preserved; and
- feature readiness for independent review, not a claim of self-approval or
  authority to merge.
