# Codex Daily — Slice 05 Evening Report

## Implementation Status

Status: planned
Commit:
Verification:
Deviations:
Follow-ups:

## Context

- Repository: `/home/syncrobot/buddy`
- Planning branch: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Selected vertical slice: `05 — Evening Report`
- Sequence: `05 of 06`
- Depends on: implemented and verified Slices 01–04
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`,
  `CURRENT.md`, `3_plan_slice_01_daily_dashboard.md`,
  `3_plan_slice_02_morning_planning.md`,
  `3_plan_slice_03_codex_observer.md`, and
  `3_plan_slice_04_needs_you.md`

Implement the factual-first end of the daily loop: generate immutable report
snapshots from persisted intent and normalized observations, retain history,
schedule one automatic report per local day, recover a missed run, and optionally
add a clearly separated Codex-authored narrative.

## Repository Rules

- Consulted: root `README.md`, approved design/alignment/roadmap, current slice
  plans, UX decision catalogue, repository contracts, and current Git status.
  `docs/rules/` does not exist, so no `docs/rules/README.md` or rule file was
  available.
- Constraints applied: extend the single Node 24 TypeScript application and its
  npm lockfile; keep the local service loopback-only and outside `buddy_*`; use
  the established SQLite, clock, HTTP error, App Server adapter, observer,
  component, and test boundaries; never parse Codex internal storage.
- Rule updates: None.

## Scope

Build a deterministic reconciliation engine and reporting workflow that:

- freezes a factual digest of one local day;
- deterministically distinguishes planned, operator-confirmed complete, pending,
  blocked, unplanned observed work, outstanding attention, and a factual
  `consider tomorrow` list;
- appends manual and automatic snapshots without overwriting earlier facts;
- defaults to `18:00` in `Europe/Berlin`, with validated configurable local time
  and IANA timezone;
- recovers a missed automatic run after startup and uses a durable uniqueness
  constraint so retries, restarts, or concurrent callbacks still create exactly
  one automatic snapshot for that local date;
- optionally sends the factual digest plus transient, on-demand final assistant
  messages from task-linked threads to a dedicated Codex reporting thread, which
  returns a clearly separated narrative and structured completion suggestions;
  and
- keeps the factual report available when Codex is disconnected, times out, or
  returns an unusable narrative.

Manual generation always creates a newer intentional snapshot. Automatic
generation has one durable slot per local date; a manual snapshot and the day's
automatic snapshot may both exist. Startup recovery checks only the current local
date after its due time and never backfills older dates. Store factual snapshot
data, narrative output/status, bounded structured suggestion records,
report-thread identity/role metadata, trigger, local date, cutoff, timestamps,
and schedule preferences. Do not store full transcripts, raw prompts/responses
from ordinary threads, credentials, or copied Codex history.

## Explicit Non-Goals

- Evidence-backed Git/test completion (`FUP-001`) or automatic task completion.
- Weekly summaries (`FUP-002`), third-party delivery, cloud sync, usage/cost
  reporting, or multi-user reporting.
- Sending prompts to, approving requests for, archiving, or otherwise mutating
  ordinary work threads.
- Replacing Slice 03 normalization or Slice 04 attention derivation.
- Broad recovery/privacy diagnostics owned by Slice 06.
- Narrative fact-checking through repository access or transcript mirroring.

## Follow-Up Scope

- Included deferred items: none.
- Still deferred: FUP-001 evidence-backed completion, FUP-002 weekly review,
  FUP-003 third-party integrations, FUP-004 multi-device sync, FUP-005 cost and
  limit insights, and FUP-006 proactive chat control.
- The dedicated reporting thread is the narrowly approved summarization exception,
  not implementation of FUP-006; it receives a frozen digest and never controls
  ordinary work.

## Central Issue Scope

- Included issue-register IDs: none.
- Newly created issue-register IDs: none.
- Still deferred issue-register IDs: none known.
- The repository has no `docs/issues/register.md`. Do not create it for this
  slice; report newly discovered durable debt or external verification gaps for
  separate triage.

## Canonical Mental Model And Required Cleanup

The report is a snapshot of the day, and its deterministic factual digest is the
source of truth. Generated narrative is optional interpretation attached to that
snapshot. It must never replace, edit, or contradict the status semantics of the
stored facts. A completed turn remains evidence only; only operator-confirmed
task completion is reported as confirmed.

Use one canonical `ReportSnapshot` contract and one factual-digest builder. Freeze
the input cutoff and derived facts at generation time; historical views must not
recompute old reports from mutable current data. Keep narrative state explicit:
`not_requested`, `pending`, `ready`, or `failed`.

Completion suggestions are generated interpretation, not factual task state.
Store each as a bounded record linked to the report snapshot and task, with a
short reason and source thread IDs. A suggestion never changes a task; the
existing operator-confirm action remains the only completion transition.
Supersede a suggestion when its task is edited, reopened, closed, or included in
a newer generated report. If narrative generation is disabled or fails, the
factual report remains complete and simply has no generated suggestions.

Remove Slice 01's representative report preview/history/settings data and any fake
generate/schedule handlers once real report APIs are wired. Remove duplicate
report DTOs, browser storage, fallback fixtures, and alternate status names. Do
not remove representative or real behavior owned by other slices. Do not add a
compatibility path that treats narrative as the report or a report thread as
ordinary observed activity.

## Storage, Scheduling, And Service Contract

Add the next numbered SQLite migration using the established runner. Represent at
minimum:

- immutable report snapshots with ID, day/local date, sequence, trigger
  (`manual`, `scheduled`, `missed_recovery`), cutoff, factual digest JSON, and
  creation timestamp;
- a durable automatic-run key unique per local date, shared by scheduled and
  missed-recovery attempts;
- optional narrative records/status linked to a snapshot, including bounded safe
  failure metadata but no copied transcript;
- bounded structured completion suggestions linked to the narrative snapshot and
  task, with no transcript body;
- reporting-thread role/identity metadata used by the observer exclusion filter;
  and
- report schedule preferences with default `18:00` and `Europe/Berlin`.

The factual builder must operate only on a transactionally consistent read of
persisted tasks, links, normalized activity, thread metadata, and attention state
up to the cutoff. Use stable ordering and serializable DTOs so identical frozen
inputs produce identical digest content.

The deterministic `consider tomorrow` section contains unresolved pending or
blocked tasks plus unplanned observed work that occurred before the cutoff. It is
advisory and does not carry or reschedule anything.

The scheduler must use the established injected clock/timer and timezone helper.
On startup and whenever preferences change, compute the next local due time. If a
due automatic slot has no snapshot, atomically claim and create it once; a
uniqueness conflict means another attempt already succeeded. Recovery must not
create duplicates across repeated startup, repeated callbacks, or concurrent
instances. DST and UTC boundaries follow the configured timezone, not host-local
or fixed-offset arithmetic.

Save the factual snapshot before requesting narrative. When narrative is enabled,
create or reuse only a dedicated reporting thread through the App Server adapter,
register its role durably, and exclude that thread and its events from observer
inventory, unplanned work, attention, and future digests. Fetch only the final
assistant message of each task-linked thread transiently through `thread/read`;
send those bounded messages with the factual digest, then discard them. Require a
validated structured result containing narrative text and zero or more
task-ID-bound completion suggestions. Timeout, disconnection, malformed output,
or persistence failure in the narrative stage leaves the factual snapshot
readable and records a visible narrative failure.

Extend the established API with coherent operations to:

- generate a manual snapshot for a requested local date;
- list report snapshots newest-first and read one immutable snapshot;
- read and update validated report schedule preferences;
- expose next-run/last-run/failure state; and
- request or retry optional narrative for a factual snapshot without regenerating
  or replacing its facts.

## UI Contract

- Replace the dashboard preview fixture with the latest real factual snapshot,
  next scheduled run, and a manual **Generate report** action.
- Provide report history and immutable report detail views showing trigger,
  generation time, cutoff, and snapshot sequence.
- Present factual sections before narrative and label generated interpretation
  clearly.
- Show confirmed, suggested, pending, blocked, unplanned, and outstanding
  attention states without collapsing their certainty.
- Expose schedule time, timezone, and narrative opt-in in Settings with validation
  and visible save/failure status.
- When Codex or narrative generation fails, keep facts/history usable and show a
  scoped failure with retry; do not show the entire report as failed.
- Preserve the dashboard's attention-first ordering, responsive shell,
  accessibility, and connection-health behavior.

## Likely Files, Modules, Components, Commands, And Tests

Extend the canonical Slice 01 application root, expected to be
`apps/codex-daily/`; if implemented slices use a different root, extend that one
rather than creating a second package.

Likely additions or modifications:

- `src/shared/report.ts` — factual digest, snapshot, narrative, schedule, and API
  DTOs
- next `src/server/storage/migrations/*.sql`
- `src/server/reports/factual-digest.ts`
- `src/server/reports/report-repository.ts`
- `src/server/reports/report-service.ts`
- `src/server/reports/report-scheduler.ts`
- `src/server/reports/reporting-thread.ts`
- established server composition, observer exclusion registry/filter, clock,
  preferences store, and App Server adapter
- `src/client/api/reports.ts`
- report preview, history, detail, schedule settings, narrative status, and
  generate/retry components under the existing client feature/page structure
- focused `*.test.ts`/`*.test.tsx` suites for digest, repository, service,
  scheduler, routes, observer exclusion, and UI
- `e2e/evening-report.spec.ts`

Required test doubles:

- fake clock and controllable timer/scheduler;
- isolated temporary SQLite store with migration/restart helpers;
- fake App Server supporting reporting-thread creation/reuse, streamed result,
  timeout, disconnect, malformed result, and failure;
- deterministic planning/activity/attention fixtures that contain no transcripts.

Use existing app scripts: `npm ci`, `npm run lint`, `npm run typecheck`,
`npm test`, `npm run build`, `npm run test:e2e`, and `npm run check`. Do not add a
second package manager, lockfile, scheduler process, or application root.

## Existing Patterns And Non-Regression

- Follow the established testable-core/thin-entry-point style, dependency
  injection, prepared SQLite repository boundary, typed HTTP errors, shared DTOs,
  and accessible React components.
- Preserve atomic store operations, migration idempotence, configurable temporary
  database paths, loopback binding, and deterministic clocks from earlier slices.
- Consume Slice 03 normalized state and Slice 04 derived attention; do not infer
  new protocol semantics inside reporting.
- Observer inventory, dashboard counts, Needs You, and unplanned-work projection
  must exclude every registered reporting thread.
- Planning remains editable and report history remains readable while Codex is
  disconnected.
- Existing task states, explicit completion ownership, carry-forward history,
  attention acknowledgement, and thread links must not change.
- No complete transcript, ordinary-thread prompt/response, or credential is added
  to SQLite, logs, fixtures, API responses, or report snapshots.
- No `buddy_*`, ROS contract, launch, configuration, or runtime behavior changes.

## Acceptance Criteria

1. A report generated from fixed persisted inputs has stable ordering and an
   identical factual digest across repeated pure-builder runs.
2. The digest separately reports planned work, operator-confirmed completion,
   pending and blocked work, unplanned observed work, outstanding attention, and
   deterministic `consider tomorrow` candidates as of its frozen cutoff.
3. Manual generation works with Codex disconnected and appends a new immutable
   snapshot; earlier snapshots remain byte-for-byte factual history.
4. The default automatic run is `18:00 Europe/Berlin`; valid time/timezone changes
   reschedule the next run, while invalid values are rejected without losing the
   prior preference.
5. At the due instant, the scheduler creates one automatic snapshot. Repeated
   automatic callbacks, service restart, and competing automatic claims create no
   duplicate automatic slot for the same local date. Intentional manual snapshots
   remain separate and may coexist with that automatic snapshot.
6. Startup after today's missed due time creates one `missed_recovery` snapshot
   for today's unfilled automatic slot. A second startup creates none, and older
   local dates are never backfilled automatically. Fake-clock tests cover UTC-date
   and Europe/Berlin DST boundaries.
7. Every automatic or manual path commits the factual snapshot before optional
   narrative work starts.
8. With narrative enabled, the adapter creates or reuses a dedicated reporting
   thread, passes the factual digest and only transient bounded final assistant
   messages from linked threads, stores narrative and validated completion
   suggestions separately, and excludes that thread from observer inventory,
   attention, unplanned work, and subsequent digests.
9. App Server unavailable, timeout, malformed narrative, and persistence failure
   tests leave the factual snapshot readable, mark only narrative as failed, and
   permit a narrative-only retry.
10. Report history is newest-first, detail reads the selected immutable snapshot,
    and regeneration never destroys or silently replaces an older record.
11. Dashboard preview, manual generation, history/detail, schedule settings, and
    factual-versus-generated labels work at desktop and mobile widths with
    keyboard access and visible status/error regions.
12. SQLite schema/API/fixtures contain no full transcript or copied ordinary
    prompt/response fields, and reporting never mutates an ordinary Codex thread.
13. A completion suggestion is labelled generated, includes its bounded reason,
    never changes the task automatically, and can reach confirmed completion only
    through the existing explicit operator confirmation.
14. All earlier Node tests, production build, browser tests, ROS boundary tests,
    and diff-scope checks continue to pass.

## Ordered Implementation Tasks

1. Confirm Slices 01–04 are implemented and verified; map these likely paths to
   their actual app root, store, clock, adapter, observer, API, UI, and test
   conventions. Stop on an architectural conflict.
2. Add failing pure digest tests for every factual category, `consider tomorrow`,
   cutoff, stable ordering, unknown state, and absence of transcript content.
3. Add the report/schedule/reporting-thread-role migration and repository tests
   for immutable snapshots, history order, migration idempotence, and the unique
   automatic slot.
4. Implement the factual builder and report service with one consistent store
   read and factual commit before any optional narrative call.
5. Implement the injected scheduler and startup recovery; test exact due time,
   preference changes, restart, concurrent claims, UTC date changes, and
   Europe/Berlin DST behavior with fake clock/timers.
6. Extend the App Server adapter with transient linked-thread final-message reads,
   the dedicated reporting-thread workflow, structured suggestion validation, and
   durable observer exclusion. Cover create, reuse, success, timeout, disconnect,
   malformed result, supersession, and retry using the fake App Server.
7. Add report and schedule routes using established DTO/error conventions,
   including manual append, history/detail, settings, scheduler state, and
   narrative-only retry.
8. Replace only report-related fixtures and handlers in the dashboard, Report,
   and Settings surfaces; implement factual-first preview/history/detail and
   scoped narrative failure/retry states.
9. Remove superseded report fixtures, fake schedule/generate controls, duplicate
   DTOs, and any path that recomputes history or exposes the reporting thread as
   work.
10. Run targeted and full verification, inspect storage and observer output for
    retention/exclusion, update this plan's status block, and preserve unrelated
    changes.

## Verification And Expected Outcomes

From the implemented app root:

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run check
```

Expected: reproducible install; lint/type checks pass; all previous and new
digest/store/fake-clock/scheduler/fake-App-Server/component tests pass; production
service/client build succeeds; browser tests prove manual generation, history,
settings, missed recovery, narrative failure fallback, and responsive views; the
aggregate check exits zero.

Run focused deterministic report tests with their in-process fake clock, timers,
store, and App Server:

```bash
npm test -- --run test/server/reports
npm run test:e2e -- evening-report.spec.ts
```

Expected: facts can be generated and revisited without Codex; the fake narrative
creates separately labelled suggestions; fake-clock restart produces one missed
automatic snapshot for the current day and never backfills older dates.

From the repository root:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git status --short
```

Expected: no whitespace errors; no ROS or frozen-contract diff; repository
boundary tests pass; status contains only intended Codex Daily/report files, this
plan status update, and untouched pre-existing user changes.

## Risks, Dependencies, And Stop Conditions

- Earlier slice paths and APIs may differ from the plan. Extend their canonical
  implementation; stop rather than create parallel stores, clocks, adapters, or
  app roots.
- Scheduled callbacks can race with startup recovery. Rely on a database unique
  automatic slot and transactional claim, not an in-memory flag.
- Timezone and clock changes can produce duplicate or skipped callbacks. Centralize
  local-date/due-time calculation and prove it with fake time; do not scatter
  `Date` or fixed-offset arithmetic.
- External narrative work is non-atomic and may hang. Commit facts first, bound
  timeouts, persist explicit status, and make retry narrative-only.
- Reporting-thread creation and observer exclusion can race. Register the
  dedicated role at the adapter boundary before projecting inventory; stop if the
  established observer cannot guarantee exclusion without protocol redesign.
- Stop if implementation requires ordinary-thread mutation, full-transcript
  retention, repository evidence, a second scheduler process, a new database
  library, broad unrelated changes, or weakened tests.
- Stop and report if required context is missing, Slices 01–04 are not implemented,
  verification commands cannot run, or Slice 05 exceeds a factual report plus
  optional narrative. Preserve the tree and provide the failing command, evidence,
  and smallest decision needed.

## Preserve Unrelated Changes

Inspect `git status` before editing and before committing. Do not revert,
reformat, stage, or include unrelated user changes. Limit implementation to the
existing Codex Daily app, this plan's status update, and only the migration/API/UI
tests necessary for Slice 05. Never use destructive cleanup on untracked files or
temporary databases not created by this slice.

## Expected Final Summary

The implementing agent must report:

- **Implemented:** factual schema/engine, scheduler and recovery, report APIs/UI,
  and optional reporting-thread behavior with exact major paths.
- **Verification:** every command and outcome, including fake-clock scheduler,
  temporary-store restart, fake App Server fallback/exclusion, browser, and ROS
  boundary evidence.
- **Deviations:** differences from this contract, or `None`.
- **Follow-ups:** stable IDs only, or `None`; FUP-001 through FUP-006 remain
  deferred.
- **Unrelated changes preserved:** pre-existing paths left untouched.
- **Implementation status:** commit hash and confirmation that the block above was
  updated to `implemented`, or the exact blocker and retained evidence.
