# Codex Daily — Slice 04 Operational Proof Plan

## Implementation Status

Status: implemented
Commit: `Slice 04: Operational Proof` (this status-bearing commit)
Verification: `npm ci` passed without lockfile changes; `npm run check` passed with 43 files/155 tests; full Playwright passed 20 runnable flows with 8 intentional mobile mutation skips; installed `codex-cli 0.146.0-alpha.3.1` schema generation passed; repository contracts passed 4/4; `colcon list` remained 16 and all 16 ROS packages built; production SIGINT/SIGTERM smokes, SQLite reopen/quick-check/foreign-key checks, privacy artifact scans, whitespace, and protected-range checks passed. ROS reported 233 tests, one unchanged `buddy_bringup` `pytest.missing_result` error, zero failures, and 13 skips.
Deviations: Playwright required host-context execution after sandboxed `tsx` IPC failed with `EPERM`; `npm ci` retained seven existing high-severity audit advisories. Exactly one synthetic-only installed-host model proof was attempted and stopped after 37 ms with the formerly coarse safe category `contract_failed`; it read no history and used no fallback, but live Sol success remains unproven. The proof now distinguishes future `host_unavailable`, `request_rejected`, and `model_contract_failed` outcomes without exposing raw errors; the historical redacted result cannot be reclassified safely and was not retried.
Follow-ups: None. `FUP-001` through `FUP-005` remain deferred.

## Context And Selected Slice

- Repository: `/home/syncrobot/buddy`
- Planning branch target: `dev`
- Recommended implementation branch:
  `feature/2026-07-29-16-04-session-briefs`
- Feature folder:
  `docs/pipeline/2026-07-29-16-04-session-briefs/`
- Selected vertical slice: `04 — Operational Proof`
- Sequence: `04 of 04`
- Dependencies: reviewed Codex Daily baseline ending at `f255d46` and
  implemented, individually verified Slices 01–03 of Recent Session Briefs.
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`, `CURRENT.md`,
  `3_plan_slice_01_brief_contract_storage.md`,
  `3_plan_slice_02_gpt56_background_analysis.md`,
  `3_plan_slice_03_recent_sessions_frontend.md`,
  `docs/about/05_ux_decision_catalogue.md`, and the archived Codex Daily
  implementation/review records under
  `docs/pipeline/_archive/2026-07-29-10-15-codex-daily/`.

Prove and harden the complete overnight session-brief lifecycle without adding a
new product capability:

`observe recent sessions → debounce → analyze with bounded GPT-5.6 workers →`
`supersede changed work → retain structured briefs overnight → restart and`
`recover → return to a truthful recent-10 briefing the next day`

This slice owns integrated lifecycle, privacy, host-model, browser, production,
and repository evidence. It may correct defects exposed by those proofs within
the approved Slices 01–03 contracts. It must not redesign the feature or expand
its scope.

## Repository Rules

- Consulted: all source documents above, root `README.md`,
  `apps/codex-daily/README.md`, current package scripts, Playwright/runtime,
  privacy, diagnostics, shutdown, observer/App Server adapter, deterministic
  fixture, generated installed App Server schemas, the archived Operational
  Hardening plan and all three implementation-review passes, and the `3-plan`
  skill. No root `AGENTS.md`, `docs/rules/README.md`, or central issue register
  exists.
- Constraints applied: extend the single `apps/codex-daily/` Node 24/npm 11
  Fastify/React/Vite/SQLite application; preserve same-origin loopback security,
  read-only ordinary chats, transient-only transcript input, coordinated SQLite
  writes, facts-before-generated-interpretation, human-confirmed completion,
  deterministic fake transport coverage, and the ROS protected-path boundary.
- Rule updates: None

## Exact Scope

- Add one deterministic full-lifecycle proof covering the recent-session window,
  automatic analysis, live frontend updates, source changes, retries, restart,
  overnight retention, and next-day cached orientation.
- Prove the exact App Server request contract in two layers:
  - deterministic fixture assertions for every field and negative path; and
  - an opt-in host-context smoke against the installed Codex App Server using
    invented synthetic content only.
- Prove explicit `gpt-5.6-sol`, `medium` effort, `ephemeral: true`,
  `allowProviderModelFallback: false`, empty dynamic tools/environment/workspace
  roots, and strict `outputSchema` behavior without reading a real Codex
  transcript.
- Prove at most two simultaneous workers, the approved two-minute timeout,
  transient retries after 30 seconds and two minutes only, per-revision
  deduplication, manual priority without concurrency bypass, and isolation of
  one failed job from the remaining window.
- Prove restart recovery for orphaned `analyzing` jobs, observer-readiness
  gating, last-good preservation, and bounded graceful shutdown/drain.
- Prove source-revision supersession at queued, retry-waiting, analyzing, and
  final-promotion boundaries so an obsolete result cannot become current.
- Prove privacy boundaries across SQLite, API, SSE, logs, diagnostics, JSON
  export, browser state/HTML, screenshots/traces, and built assets.
- Prove delete-day and delete-all pause/cancel/drain analysis, cannot be undone
  by a late model completion, roll back atomically on injected failure, resume
  writers safely, and send no ordinary-chat mutation.
- Prove out-of-window cancellation, one stable 24-hour grace marker, re-entry,
  exact-boundary pruning, quiet hourly pruning, and deletion/exclusion cascades.
- Extend safe operational diagnostics and Settings evidence for the brief queue,
  worker/retry/model state, last safe failure, pruning, and retained counts.
- Complete desktop, exact 390×844, keyboard, disconnected, stale, failure,
  retry, live-progress, and no-horizontal-overflow browser proof.
- Update the app-local README with the analysis contract, runtime requirements,
  privacy boundary, data/export/deletion behavior, diagnostics, startup/shutdown,
  host-model proof, and troubleshooting.
- Run all package, production, browser, repository-contract, ROS inventory/build/
  test, whitespace, and protected-scope checks and record exact environment
  blockers or accepted unchanged failures.

## Explicit Non-Goals

- Changing the selected count from 10, the first-intent plus recent-six input
  policy, the 32,000-character cap, model, effort, timeout, retry schedule,
  retention duration, structured schema, or UI hierarchy.
- Adding configurable count/depth/model, weekly synthesis, external
  notifications, third-party integrations, accounts, remote access, telemetry,
  costs/usage views, or automatic task/chat actions.
- Reading a real local transcript for verification, copying a real chat into a
  fixture, persisting prompts/raw output, or placing source text in logs,
  screenshots, Playwright traces, test names, failure messages, or status docs.
- Treating chat-reported completion as operator-confirmed completion or moving
  generated actions/blockers into Needs You, the morning plan, or reports.
- Sending prompts, approvals, answers, archives, deletes, steering, interrupts,
  or any mutation to an ordinary source thread.
- Adding another AI provider, model fallback, direct OpenAI API key, browser-side
  model call, generic job framework, second session list, compatibility DTO, or
  fallback free-text summary.
- Broad refactors of planning, observer, attention, reports, privacy, shell,
  routing, test stack, SQLite infrastructure, or ROS packages.
- Automatic service installation, systemd, containers, remote deployment, or
  leaving a privileged test process permanently running. The ordinary documented
  local app may be left running only through the existing operator run command.

## Follow-Up Scope

- Included `FUP-###` items: none.
- Still deferred:
  - `FUP-001` user-tunable session count;
  - `FUP-002` per-session analysis depth;
  - `FUP-003` weekly cross-session synthesis;
  - `FUP-004` external notifications; and
  - `FUP-005` automatic ordinary-chat actions.
- Operational proof must verify the boundaries around these items, not add
  hidden, disabled, or provisional implementations of them.

## Central Issue Scope

- Included register IDs: none.
- Still deferred register IDs: none identified.
- Newly created register IDs: none.
- No `docs/issues/register.md` exists. If verification exposes durable debt
  outside this feature, report it and stop rather than absorbing it into this
  slice or inventing an issue identifier.

## Canonical Mental Model And Required Cleanup

A **session brief** remains one validated, structured, model-derived
interpretation of one eligible ordinary Codex session at an exact
`{threadId, updatedAt}` source revision. The factual observer row, last-good
brief, and latest generation job are separate:

1. the observer owns factual session identity, recency, runtime, and transient
   request-scoped reads;
2. the repository owns one last-good structured result and one latest bounded
   job per thread;
3. the coordinator owns recent-10 selection, debounce, queue, workers, retries,
   supersession, retention, and shutdown; and
4. the browser renders the server-selected factual-plus-derived view without
   owning model or transcript state.

The overnight lifecycle is successful when a returning operator can read the
last validated structured result immediately, see whether it is current or
stale, and watch bounded refresh resume without rereading a chat. A generated
result is never evidence that an operator task is complete.

Required cleanup before final verification:

- Remove Slice 01's deterministic placeholder analyzer, placeholder generator
  rows, placeholder regeneration branch, and tests that permit
  `modelId: null` in production.
- Remove any production debug route, timer shortcut, fake clock, fixture switch,
  raw request recorder, transcript logger, or browser-only lifecycle override
  added by Slices 01–03.
- Keep one shared session-brief schema, one gateway, one coordinator, one
  repository, one API/SSE surface, one provider, and one Priority 03 card
  surface. Remove aliases, compatibility shapes, and duplicate status
  calculations.
- Keep retry due time and attempt state durable enough for restart behavior, but
  do not retain historical job attempts, prompts, model output, or exception
  bodies.
- Keep lifecycle/freshness as independent axes; do not flatten a stale
  last-good brief plus failed replacement into a generic error.
- Remove the old **Active and recent Codex chats**, runtime-first 20-card
  selection, and old selectors/tests if any remain after Slice 03.
- Ensure generated analysis threads are excluded by their approved durable
  boundary and do not appear as ordinary sessions, attention, reports, export
  transcript content, or future brief candidates.
- Remove any retry loop, timer, worker, observer listener, EventSource listener,
  or open App Server request that survives coordinated stop.

## Installed App Server Evidence And Host-Proof Contract

The installed CLI reports `codex-cli 0.146.0-alpha.3.1`. Its schema was generated
locally with:

```bash
codex app-server generate-json-schema --experimental \
  --out /tmp/codex-daily-appserver-schema-review
```

The generated v2 schemas establish:

- `ThreadReadParams` accepts `threadId` and `includeTurns`;
- `ThreadStartParams` accepts `model`, `ephemeral`,
  `allowProviderModelFallback`, `dynamicTools`, `environments`,
  `runtimeWorkspaceRoots`, approval/sandbox controls, and source metadata;
- `TurnStartParams` requires `threadId` and `input` and accepts `model`,
  `effort`, `environments`, `runtimeWorkspaceRoots`, and `outputSchema`; and
- `ThreadStartResponse` returns the selected `model`, `reasoningEffort`,
  `runtimeWorkspaceRoots`, sandbox information, and a thread whose schema
  contains `ephemeral`.

Do not copy `/tmp` schemas into production source or treat `/tmp` as durable
evidence. Add an executable, content-safe host proof such as
`scripts/prove-session-brief-host.mjs` that:

1. is opt-in and never runs during ordinary `npm test`, build, start, or
   Playwright;
2. starts the installed `codex app-server --stdio` through the same narrow
   protocol boundary;
3. never calls `thread/list` or `thread/read` and therefore cannot inspect a real
   local chat;
4. creates one analysis thread with the exact production parameters:
   `model: "gpt-5.6-sol"`, `ephemeral: true`,
   `allowProviderModelFallback: false`, `dynamicTools: []`,
   `environments: []`, `runtimeWorkspaceRoots: []`, `cwd: null`,
   `approvalPolicy: "never"`, and raw experimental events disabled; it sends no
   `sandbox`, `permissions`, `selectedCapabilityRoots`, collaboration/multi-agent
   mode, service tier, or model-provider override;
5. starts one turn with invented synthetic source text, explicit
   `model: "gpt-5.6-sol"`, `effort: "medium"`, `environments: []`, and the exact
   production strict `outputSchema`, with no workspace/tool/multi-agent fields;
6. validates only the final assistant JSON through the production validator;
7. asserts the start response reports exactly `gpt-5.6-sol`, the returned thread
   is ephemeral, no provider fallback occurred, the response satisfies the
   output schema, and the returned thread reports `ephemeral: true`; and
8. prints only a fixed safe proof summary containing CLI version, booleans,
   model/effort identifiers, elapsed time, and pass/fail categories. It must not
   print or write the synthetic prompt, raw JSON-RPC envelopes, final raw model
   output, reasoning, IDs, cwd, environment, credentials, or exception text.

The host proof must fail visibly if `gpt-5.6-sol` is unavailable, the account is
unauthorized/rate-limited, the host replaces the model, structured output is
invalid, or the filesystem sandbox prevents Codex initialization. Do not retry
through another model/provider. Run it only in a normal host context with a
disposable process and record an environment blocker instead of weakening the
contract.

The deterministic fake App Server remains the repeatable CI proof. Extend it to
assert the same exact request fields and reply with invented schema-valid
content. Its method/request evidence may retain only method names, booleans,
bounded counts, fixed model/effort strings, and an input hash/character count;
it must not log input or output bodies. Add negative fixture modes for fallback,
timeout, refusal, invalid JSON/schema, disconnect, and late completion.

## Integrated Overnight Lifecycle Proof

Use an isolated temporary SQLite file, injected clock/timers, deterministic fake
App Server, and invented sessions. The integration scenario must prove this
ordered lifecycle:

1. Start late on local day one with at least 11 eligible top-level sessions plus
   reporting, ephemeral-analysis, subagent/child, archived, and locally excluded
   fixtures. Literal recency selects exactly the newest 10.
2. Reconcile a usable observer snapshot. Automatic work remains debounced for
   exactly 30 seconds and does not start early.
3. Advance the injected timer. Exactly two jobs enter `analyzing`; the remaining
   eligible jobs stay queued. Track peak concurrency in the fake gateway and
   assert it never exceeds two.
4. Complete one job, fail another transiently, and verify a third starts without
   waiting for the failed session. The transient job retries no sooner than 30
   seconds, then no sooner than two minutes, and stops after two retries.
5. While one revision is queued, while another waits to retry, and while a third
   is analyzing, advance each source `updatedAt`. Each old generation becomes
   superseded, only the newest revision remains eligible, and late old results
   are discarded transactionally.
6. Manually refresh a current revision. It moves ahead of automatic queued work
   but does not preempt an in-flight worker, exceed two workers, or create two
   jobs for repeated clicks.
7. Complete valid jobs. The UI-facing snapshot contains safe structured results
   and truthful aggregate counts; one failure does not block the other nine.
8. Leave one job durably `analyzing`, stop the process as if interrupted, and
   reopen the same database with a later clock. Startup recovers the orphan to
   queued/stale, preserves its last-good brief and attempt state, and starts no
   analysis before an observer-ready snapshot.
9. Begin local day two with Codex initially unavailable. Cached factual rows and
   last-good structured briefs remain readable; planning, Needs You, reports,
   Settings, export, and thread-detail retained facts remain usable.
10. Reconnect the fake App Server. Recovery resumes within the approved worker
    and retry bounds, current revisions promote, and no duplicate job/result,
    observer activity, attention item, task link, or report appears.
11. Move a brief out of the newest-10 window. Cancel its queued/retry work, set
    `out_of_window_at` once, keep it absent from Today, preserve it before 24
    hours, clear the marker on re-entry, and prune it at/after the exact 24-hour
    boundary. An hourly sweep must prune it even without another observer event.
12. Close the application with active work. New work is rejected, timers and
    listeners stop, in-flight requests cancel or drain within the configured
    bound, workers reach zero, App Server exits, HTTP closes, then SQLite closes
    without late writes or unhandled rejections.

Tests must use fake time rather than sleeping for debounce/retry/retention
durations. Persist only invented structured brief data and safe lifecycle
metadata in the temporary database.

## Privacy, Export, Deletion, And Rollback Proof

Create unique synthetic sentinels for transcript text, prompt instructions,
assistant reasoning, tool payloads, command output, diffs, credential-shaped
fields, raw model output, protocol envelopes, and exception messages. Supply
them only through the deterministic in-process/fake App Server boundary; never
use a real chat.

Prove every sentinel is absent from:

- SQLite tables, including temporary job and failure columns;
- brief GET/mutation responses and `session-briefs` SSE events;
- observer/attention/report/operations DTOs;
- JSON export and diagnostics;
- Fastify logs and process stderr/stdout;
- browser `document.body`, in-memory provider snapshot serialization, storage,
  screenshots, traces, and downloaded export; and
- `dist/` and retained Playwright artifacts.

The export may contain only validated structured briefs, source/model/generation
metadata, safe job lifecycle/counters, and the established monitor-owned factual
records. It must remain deterministic in stable order and use the schema version
introduced by Slice 01. Diagnostics may expose bounded failure categories and
timestamps, never raw exceptions.

For both day deletion and delete-all, inject a generation that is blocked
immediately before promotion:

1. begin confirmed local deletion;
2. stop accepting refresh/retry and background enqueue;
3. cancel queued/retry timers and drain/cancel the blocked generation;
4. acquire the existing exclusive write boundary;
5. delete the intended brief/job rows in the same transaction as other local
   monitor data;
6. release the old completion and prove its generation token cannot recreate a
   row or publish a stale SSE snapshot;
7. resume writers/observer only after the committed post-delete snapshot exists;
   and
8. prove no App Server method capable of mutating an ordinary source thread was
   sent.

Inject a database trigger failure after brief deletion has begun and prove the
entire day/delete-all transaction rolls back, the last-good/job pair remains
consistent, writers resume once, the worker can subsequently recover, and
database/foreign-key health is still `ok`. Relevant day deletion must use the
retained timezone bounds and delete a brief/job when any approved lifecycle
timestamp belongs to that day. Delete-all must reset preferences exactly as the
existing product contract specifies.

## Diagnostics, Shutdown, And Runbook Contract

Extend the existing bounded `OperationsDiagnostics` shape rather than adding a
log viewer. Show at least:

- selected recent-session count;
- queued, retry-waiting, analyzing, ready/current, stale, unavailable, and
  failed counts;
- configured and observed peak worker concurrency;
- last successful generation time and model ID;
- last safe failure category/time;
- retry count or bounded aggregate;
- last prune time and pruned-row count;
- orphan jobs recovered at startup; and
- shutdown/drain state useful for a final process smoke.

Diagnostics must remain useful while Codex is disconnected, must not expose
thread content or raw errors, and must reconcile with retained counts/export.
Settings loading/error behavior and loopback/same-origin protection must remain
truthful.

Update `apps/codex-daily/README.md` with:

- exact recent-10 eligibility and revision semantics;
- first-user-intent plus six-recent-turn and 32,000-character transient input
  boundary;
- explicit GPT-5.6 Sol/medium/ephemeral/no-fallback/strict-schema behavior;
- debounce, two-worker, timeout, retry, restart, last-good, and 24-hour retention
  behavior;
- what is stored, exported, diagnosed, and deleted, plus what is never stored;
- ordinary-chat read-only assurance and analysis-thread exclusion;
- local run/build commands and the requirement to launch in a normal host
  context when Codex cannot initialize inside a restricted filesystem sandbox;
- opt-in host-proof command, its synthetic-only behavior, possible account/model
  cost, and its intentionally redacted output;
- troubleshooting for reconnect, unavailable Sol, timeout/refusal/invalid
  output, stale/failed cards, manual retry, database health, and graceful
  shutdown; and
- confirmation that production remains bound only to `127.0.0.1`.

Do not document an alternative model/provider fallback or ask the operator to
copy a real transcript into a test.

## Likely Files, Modules, Components, Commands, And Tests

Reconcile names with the implemented Slices 01–03 and extend their canonical
paths. Likely modifications:

- `apps/codex-daily/src/shared/session-briefs.ts`
- `apps/codex-daily/src/shared/operations.ts`
- `apps/codex-daily/src/server/briefs/session-brief-gateway.ts`
- `apps/codex-daily/src/server/briefs/session-brief-coordinator.ts`
- `apps/codex-daily/src/server/briefs/session-brief-repository.ts`
- `apps/codex-daily/src/server/briefs/session-brief-validator.ts`
- `apps/codex-daily/src/server/briefs/session-brief-routes.ts`
- `apps/codex-daily/src/server/codex/app-server-client.ts`
- `apps/codex-daily/src/server/codex/observer-service.ts`
- `apps/codex-daily/src/server/privacy/privacy-service.ts`
- `apps/codex-daily/src/server/diagnostics/diagnostics-service.ts`
- `apps/codex-daily/src/server/runtime/write-coordinator.ts`
- `apps/codex-daily/src/server/app.ts`
- `apps/codex-daily/src/server/startup.ts`
- `apps/codex-daily/src/client/data/session-briefs-context.tsx`
- `apps/codex-daily/src/client/features/session-briefs/RecentSessionBriefs.tsx`
- `apps/codex-daily/src/client/features/session-briefs/SessionBriefCard.tsx`
- `apps/codex-daily/src/client/pages/SettingsPage.tsx`
- `apps/codex-daily/test/fixtures/fake-codex-app-server.py`
- `apps/codex-daily/test/server/e2e-main.ts`
- `apps/codex-daily/playwright.config.ts`
- `apps/codex-daily/README.md`

Likely additions:

- `apps/codex-daily/scripts/prove-session-brief-host.mjs`
- `apps/codex-daily/test/server/briefs/session-brief-operational.test.ts`
- `apps/codex-daily/test/server/briefs/session-brief-host-contract.test.ts`
- `apps/codex-daily/e2e/session-briefs-lifecycle.spec.ts`

Likely focused updates:

- Slice 01–03 validator, repository, coordinator, gateway, route, provider, and
  component tests;
- `apps/codex-daily/test/server/privacy/privacy-service.test.ts`
- `apps/codex-daily/test/server/privacy/privacy-routes.test.ts`
- `apps/codex-daily/test/server/runtime/full-lifecycle.test.ts`
- `apps/codex-daily/src/server/app.test.ts`
- `apps/codex-daily/src/client/App.test.tsx`
- existing dashboard, observer, recovery/privacy, and Settings Playwright flows.

Follow actual Slice 02 names when they differ. Do not create parallel
gateway/coordinator/runtime or compatibility layers. A new production dependency
should not be necessary; use Node, Vitest, existing App Server protocol helpers,
Testing Library, Playwright, and the current injected clocks/timers.

## Existing Patterns To Follow

- `openDatabase()` and ordered migrations for transactional SQLite ownership,
  upgrade tests, foreign keys, and explicit close.
- `WriteCoordinator` plus `PrivacyService` for rejecting new writes, draining
  active work, running destructive transactions, resuming in `finally`, and
  rolling back safely.
- `ObserverService`, `AttentionService`, and `ReportScheduler` for injected
  clock/timers, idempotent start/stop, bounded reconnect, operational
  diagnostics, and listener cleanup.
- `AppServerClient` for fixed executable arguments, shell-free spawn, request
  correlation, timeouts, bounded stderr diagnostics, and process termination.
  Extend its method ownership narrowly; do not expose a generic arbitrary
  request API to the browser or unrelated services.
- Reporting gateway tests for `thread/start`/`turn/start` correlation and final
  assistant extraction, while keeping analysis work on separate ephemeral
  threads with stricter request fields and schema validation.
- Privacy tests for stable product exports, sentinel scans, exact typed
  confirmations, zero ordinary Codex mutation, retained-timezone deletion, and
  injected rollback.
- `full-lifecycle.test.ts` for persistent temporary-database restart proof;
  extend it rather than duplicating unrelated morning/report scenarios.
- Current Playwright `workers: 1`, isolated production server, desktop 1440×1000
  and mobile 390×844 projects, test-owned deterministic clock, one gated
  destructive desktop flow, and explicit overflow measurement.
- Observer/attention/report/session-brief providers for authoritative GET then
  SSE, retained last snapshot on stream loss, mutation state, and unmount
  cleanup.
- Archived hardening review lessons: host/origin rejection, no-store transient
  content, read-only GETs, connection-stable identities, independently
  reproducible browser tests, offline retained facts, and complete attention
  source visibility.

## Behavior That Must Not Regress

- Dashboard priority remains Needs You, today’s outcomes, Recent session briefs,
  recently completed factual work, then evening report.
- Exactly the newest 10 eligible top-level sessions appear in literal
  `recencyAt ?? updatedAt` order; runtime never changes ordering.
- Factual metadata, planning, Needs You, reports, Settings, export, and retained
  thread activity remain usable while Codex/model/SSE is unavailable.
- Full thread history remains transient and `Cache-Control: no-store`; bounded
  analysis input also remains process/request-memory only.
- Ordinary chats remain read-only. Analysis may create/turn only an ephemeral,
  durably excluded analysis thread and cannot call source-thread mutation
  methods.
- Chat-reported done never completes, closes, creates, or reorders an
  operator-owned outcome.
- Last-good briefs survive failure, disconnect, and restart; stale and lifecycle
  states remain separately truthful.
- Reporting threads, ephemeral analysis threads, archived threads, subagents,
  child threads, and local exclusions never become brief candidates.
- Report scheduling/narratives and session-brief generation remain distinct
  queues and persistence contracts.
- Day deletion continues recomputing retained observer activity, preserving
  cross-day task semantics, and changing local monitor data only.
- Loopback Host/Origin rejection, non-cacheable detail, coordinated writes,
  deterministic exports, database health, and graceful report/observer shutdown
  remain intact.
- No real transcript, prompt, model output, reasoning, tool payload, raw
  protocol, exception text, command, diff, or credential enters persistence,
  browser state, logs, diagnostics, export, docs, screenshots, or tests.
- Codex Daily remains outside the colcon graph. No `buddy_*`, `docs/contracts`,
  runtime asset, or unrelated repository path changes.

## Acceptance Criteria

1. A persistent overnight integration starts with at least 11 eligible sessions,
   selects exactly 10 by literal recency, analyzes them incrementally, restarts
   on the next local day, and exposes cached last-good briefs before reconnect.
2. Automatic work waits for a usable observer snapshot and a 30-second debounce.
   Peak analysis concurrency is exactly bounded at two across automatic, manual,
   and retry work.
3. A transient failure retries only after 30 seconds and two minutes, performs
   at most two retries, retains its last-good result, and never blocks other
   session jobs. Timeout fires at two minutes and cancels/settles the worker.
4. Repeated refresh/reconcile for the same thread revision creates at most one
   active job. Manual refresh of a completed unchanged revision creates one new
   front-of-queue generation without bypassing concurrency.
5. A new `updatedAt` supersedes queued, retry-waiting, and analyzing generations.
   Late success/failure from an obsolete token is discarded inside the final
   write transaction and cannot change the last-good row, job, counts, or SSE.
6. Restart converts every orphaned `analyzing` job to queued/stale, preserves
   last-good content and bounded attempt state, restores retry due-time
   semantics, and resumes only after observer readiness.
7. The deterministic App Server fixture asserts explicit
   `model: "gpt-5.6-sol"`, `effort: "medium"`, `ephemeral: true`,
   `allowProviderModelFallback: false`, strict `outputSchema`, no dynamic tools,
   empty environments and thread workspace roots, no sandbox/permissions/
   collaboration/multi-agent/provider override, and zero source-thread writes.
8. The opt-in installed-host proof uses synthetic content only, reads no local
   thread, validates the production schema, confirms exact model and ephemeral
   behavior, and prints no prompt/raw output/protocol/thread/workspace data. A
   missing/unavailable Sol fails without fallback and is recorded truthfully.
9. Invalid JSON/schema, refusal, model unavailable, timeout, disconnect, and
   source-read failure produce distinct safe categories, preserve prior briefs,
   and isolate the affected session.
10. Only first user intent plus six recent turns, in chronological order and at
    most 32,000 Unicode characters with approved markers/redaction, can reach the
    gateway. Empty usable content fails safely.
11. Sentinel transcript, prompt, raw output, reasoning, tool, command, diff,
    credential, protocol, and exception strings are absent from SQLite, API/SSE,
    export, diagnostics, logs, browser storage/HTML, traces/screenshots, and
    `dist/`.
12. Export includes stable structured brief/lifecycle data only. Diagnostics and
    retained counts truthfully expose bounded queue/worker/retry/model/prune/
    orphan state without raw content and remain available offline.
13. Delete-day and delete-all reject new brief work, cancel timers, drain/cancel
    in-flight analysis, delete the correct local rows, prevent a released late
    result from recreating them, publish only post-delete state, and send zero
    ordinary-thread mutation methods.
14. Injected deletion failure rolls back all monitor-owned changes, keeps the
    brief/job pair consistent, resumes writers once, and leaves quick-check and
    foreign-key health `ok`.
15. Out-of-window work is canceled immediately. The last-good row is hidden from
    Today, retained before 24 hours, pruned at/after 24 hours by reconciliation
    or quiet hourly sweep, and restored without regeneration if it re-enters
    before expiry.
16. Graceful SIGINT and SIGTERM stop accepting jobs, clear debounce/retry/prune
    timers, detach observer/listener/SSE resources, bound analysis drain/cancel,
    terminate App Server, close HTTP, then close SQLite with no late write,
    locked database, unhandled rejection, or orphaned child process.
17. Desktop browser proof shows automatic queued→analyzing→ready live updates,
    exact recent-10 ordering, stale last-good replacement, one isolated failure,
    refresh-all, per-card retry, disconnected cached content, and truthful
    aggregate progress without reload or focus loss.
18. Keyboard-only proof tabs to and activates refresh-all, retains focus through
    mutation/SSE updates, reaches a title-specific retry, task link/unlink, and
    thread detail, with one polite live region and no color-only status.
19. At 1440×1000 and exactly 390×844, every tested loading/ready/stale/failed/
    offline state has no body/document horizontal overflow, clipped control,
    hidden factual metadata, or inaccessible derived section.
20. Existing morning planning, prior-day review, task links, Needs You,
    completed-work facts, report generation/history/scheduling, Settings,
    privacy, thread detail, same-origin security, and offline behaviors remain
    green.
21. `npm ci`, lint, both TypeScript projects, all Vitest tests, production build,
    full independent Playwright matrix, production startup, loopback-only health,
    host/model proof where the environment permits it, and graceful signal
    smokes complete with exact recorded outcomes.
22. Repository contracts pass, `colcon list` remains the existing 16 packages,
    the full ROS build/test matrix is run and its exact outcome recorded, range
    whitespace is clean, and the full feature range contains no protected
    `buddy_*`, `docs/contracts`, or runtime-asset changes.
23. `apps/codex-daily/README.md` accurately documents the model/input/lifecycle/
    privacy/retention/run/proof/troubleshooting contracts and does not advertise
    a fallback or ask for real transcript content.

## Ordered Implementation Tasks

1. Confirm Slices 01–03 are `implemented` with their required verification and
   inspect the exact checked-out DTO, migration, repository, gateway,
   coordinator, route, provider, card, fixture, and test names. Stop if an
   upstream slice is incomplete, exposes placeholder data, or materially differs
   from the approved contract.
2. Record the installed CLI version and regenerate the experimental App Server
   schema into a fresh explicit `/tmp` directory. Compare only the used
   `thread/read`, `thread/start`, `turn/start`, response, and notification
   fields. Do not copy schemas into the repository.
3. Add failing deterministic host-contract tests asserting every production
   request field, exact model/effort, no fallback, ephemeral thread, strict
   output schema, no tools/environment/workspace, safe final-message parsing,
   and zero ordinary-thread mutation. Add fixture modes for each safe failure.
4. Add the opt-in synthetic-only host-proof script. Reuse the production gateway
   and validator, redact all output by construction, never enumerate/read local
   threads, and require exact Sol success rather than a fallback.
5. Add failing fake-time scheduler/coordinator tests for observer readiness,
   30-second debounce, peak concurrency two, manual priority, idempotency,
   two-minute timeout, 30-second/two-minute retries, maximum attempts, failure
   isolation, and cancellation on stop/deletion/window exit.
6. Add failing supersession tests at queued, retry-waiting, analyzing, and
   promotion barriers. Require durable generation tokens and a transaction-time
   target revision check before any result/failure write or SSE publication.
7. Add a persistent-database restart test with an orphaned analyzing job,
   last-good stale result, pending retry, disconnected startup, observer-ready
   resume, overnight date change, and no duplicates.
8. Add exact 24-hour retention tests for initial grace marking, stable marker,
   cancellation, pre-boundary retention, exact/post-boundary pruning, re-entry,
   quiet hourly sweep, exclusion, source deletion, and shutdown timer cleanup.
9. Add privacy sentinel tests covering extraction, gateway, repository,
   API/SSE, export, diagnostics, logs, browser, artifacts, and build. Tests must
   report only sentinel labels/locations, never echo the forbidden value.
10. Add coordinated delete-day/delete-all race tests with a worker blocked before
    promotion, late release, exact typed confirmation, zero ordinary Codex
    mutation, post-delete snapshot ordering, and injected transactional rollback.
11. Extend diagnostics/shared DTO/Settings only as needed for safe queue, worker,
    retry, model, prune, orphan, and shutdown evidence. Preserve existing
    loading/error, same-origin, and no-store contracts.
12. Extend the persistent full-lifecycle test into the complete overnight
    scenario, using invented sessions and fake time. Reuse existing morning,
    attention, and report paths to prove non-regression without coupling session
    briefs to them.
13. Extend deterministic Playwright state/fixtures for exact recent-10,
    queued→analyzing→ready, stale replacement, failure/retry, reconnect, next-day
    cached state, keyboard focus, 1440px/390px, and overflow. Keep tests
    independently reproducible and all fixture content invented.
14. Add production process smokes for fresh disposable SQLite, upgrade/restart,
    open SSE plus shutdown, active brief work plus SIGINT/SIGTERM, loopback
    binding, child-process exit, and unlocked database reopening.
15. Remove temporary placeholder/debug/test paths, inspect built output and test
    artifacts for leakage, and update the app README/runbook.
16. Run focused and full web verification, then the opt-in host proof in normal
    host context. If filesystem, account, network, model availability, or rate
    limits block the host proof, record the exact safe category and do not claim
    it passed or use another model.
17. Run repository contracts, ROS inventory, full ROS build/tests, full-feature
    whitespace, and protected-range checks. Distinguish unchanged environment or
    ROS failures with commands and path evidence; do not modify protected code.
18. Update only this plan's status block with exact test counts, production and
    host-proof outcomes, environment deviations, retained risks, and commit.
    Hand the exact commit to independent review; do not self-approve the feature.

## Verification Commands And Expected Outcomes

Run from `/home/syncrobot/buddy/apps/codex-daily`:

```bash
node --version
npm --version
npm ci
npm test -- --run test/server/briefs/session-brief-host-contract.test.ts
npm test -- --run test/server/briefs/session-brief-operational.test.ts
npm test -- --run test/server/briefs/session-brief-coordinator.test.ts
npm test -- --run test/server/briefs/session-brief-repository.test.ts
npm test -- --run test/server/briefs/session-brief-gateway.test.ts
npm test -- --run test/server/briefs/session-brief-input.test.ts
npm test -- --run test/server/privacy/privacy-service.test.ts
npm test -- --run test/server/privacy/privacy-routes.test.ts
npm test -- --run test/server/runtime/full-lifecycle.test.ts
npm test -- --run src/server/app.test.ts src/server/storage/database.test.ts
npm test -- --run test/client/features/session-briefs/session-briefs.test.tsx
npm run lint
npm run typecheck
npm test
npm run build
npm run check
npm run test:e2e -- session-briefs-lifecycle.spec.ts
npm run test:e2e
```

Adjust focused filenames to the canonical Slice 02 implementation names rather
than creating duplicates. Expected:

- Node is `v24.x` and npm is `11.x`; the lockfile install succeeds without
  changing the lockfile;
- focused tests prove exact host payloads, input/output privacy, scheduler
  bounds, supersession, restart, pruning, deletion races, diagnostics, and
  browser state;
- aggregate lint, typecheck, Vitest, build, and `check` exit zero;
- the focused Playwright scenario and full two-project matrix pass
  independently, without relying on test order; and
- no fixture/test writes a raw prompt, transcript, raw output, protocol envelope,
  or secret into an artifact.

Regenerate and inspect installed schema evidence in a fresh disposable location:

```bash
codex --version
codex app-server generate-json-schema --experimental \
  --out /tmp/codex-daily-session-brief-schema-proof
```

Expected: the installed version is recorded; generation succeeds; used v2
schemas still contain the exact fields described above. If the command cannot
initialize in the restricted filesystem sandbox, rerun in normal host context
and record that environment requirement.

Run the opt-in host model proof from a normal host context:

```bash
CODEX_DAILY_RUN_HOST_MODEL_PROOF=1 \
  node scripts/prove-session-brief-host.mjs
```

Expected: one synthetic-only analysis succeeds using exactly `gpt-5.6-sol`,
medium effort, an ephemeral thread, no provider fallback, no tools/workspace
environment, and the production strict output schema. The returned thread
reports `ephemeral: true`; the proof does not enumerate local history to make
that assertion. Output contains only the approved safe proof summary. Account,
model, rate-limit, network, or sandbox failure is reported as a safe blocker; no
alternate model/provider is attempted.

Run a production smoke with explicit disposable data:

```bash
CODEX_DAILY_DB_PATH=/tmp/codex-daily-session-brief-proof.sqlite \
CODEX_DAILY_TIMEZONE=Europe/Berlin \
CODEX_DAILY_REPORT_TIME=18:00 \
npm run start
```

Expected: the built app binds only to `127.0.0.1:4317`, migration/foreign-key
health is `ok`, session-brief diagnostics are present and redacted, cached data
remains useful if Codex is unavailable, and SIGINT/SIGTERM causes bounded clean
shutdown. Reopen the same database to prove no lock/orphan remains. Remove only
the explicitly named disposable SQLite file and adjacent `-wal`/`-shm` files
after the stopped-process proof.

Run from `/home/syncrobot/buddy`:

```bash
source /opt/ros/jazzy/setup.bash
colcon list
colcon build --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
ROS_LOG_DIR=/tmp/buddy-session-brief-test-logs \
  colcon test --ctest-args --output-on-failure
colcon test-result --verbose
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git diff --check
git diff --check f255d46..HEAD
git diff --name-only -- 'buddy_*' docs/contracts runtime_assets
git diff --name-only f255d46..HEAD -- 'buddy_*' docs/contracts runtime_assets
git status --short
```

Expected:

- `colcon list` contains the same 16 Buddy packages and Codex Daily is absent;
- the full ROS build succeeds;
- full ROS tests and repository contracts pass, or any unchanged pre-existing
  `buddy_bringup` missing-result/hang and `buddy_navigation`
  `stale_action_owner` failure is recorded exactly with unchanged protected-path
  evidence and is not “fixed” in this web feature;
- both worktree and full-feature range whitespace checks are clean;
- neither the worktree nor `f255d46..HEAD` contains protected ROS, contract, or
  runtime-asset changes; and
- status contains only intended Codex Daily/session-brief docs plus explicitly
  preserved user/concurrent changes.

If Playwright cannot bind `127.0.0.1:4317` inside the sandbox, rerun the exact
command with host-context approval and record the deviation. Never bind to a LAN
address to make the test pass.

## Risks, Dependencies, Environment Deviations, And Stop Conditions

- This slice depends on Slices 01–03 being implemented and verified. Stop if a
  dependency status is not `implemented`, its placeholder remains reachable, or
  its contract cannot support the required proof without redesign.
- A real Sol host proof can consume model capacity and depends on local Codex
  authentication, account limits, network, and model availability. Run exactly
  one bounded synthetic proof. Stop and record the safe failure category rather
  than retrying through a fallback or exposing credentials.
- Codex App Server may fail inside the restricted filesystem sandbox because it
  cannot initialize its local SQLite state. Run schema/host proofs in a normal
  host context when permitted. This is an environment deviation, not authority
  to weaken loopback security or transcript privacy.
- Playwright may require host permission to bind the loopback server. Record the
  approved escalation; do not switch hosts or reuse an operator's live app/data.
- A strict output schema proves final-message shape, not truth. Keep GPT-derived
  labels, confidence, safe evidence labels, and human-confirmed completion
  boundaries.
- Retry and shutdown races can leak worker capacity or promote obsolete output.
  Use injected fake time, generation-token transaction guards, and explicit
  worker/drain assertions. Do not rely on sleeps or best-effort cancellation.
- Destructive privacy proof can lose real local data if misconfigured. Use only
  an explicit isolated temporary database and fake App Server. Stop if a test
  resolves to the default `.codex-daily-data` path.
- Sentinel failure reporters can leak the value they are testing. Assertions and
  logs must identify only the sentinel category and surface, never echo the
  value.
- Full ROS tests may retain the archived untouched `buddy_bringup` hang/
  missing-result and `buddy_navigation` failure. Record exact commands and
  protected-path evidence. Do not alter ROS code, contracts, launch, config, or
  package discovery.
- `npm ci` may report existing dependency audit advisories or require network.
  Record advisories/network blockers; do not expand into unapproved dependency
  upgrades or weaken locked-install/build verification.
- Stop if safe host proof would require enumerating/reading real chats, printing
  raw model content, adding credentials, changing provider/model, enabling
  tools/workspace access, or persisting an analysis thread.
- Stop if deletion cannot quiesce the brief worker, shutdown cannot bound child
  work, raw content appears in any retained surface, or exact Sol/no-fallback/
  schema proof fails for an implementation reason.
- Stop if implementation requires a deferred `FUP-###`, new product semantics,
  cloud/auth/telemetry, another dependency/provider, a production debug
  backdoor, broad unrelated changes, or protected-path edits.
- Stop if required verification cannot run, the feature is materially larger
  than this proof/hardening slice, or overlapping user/concurrent changes cannot
  be preserved.

When blocked, preserve the worktree, retain the smallest safe deterministic
failing proof, mark this plan `blocked`, record the affected acceptance criterion
and exact redacted command outcome, and request the smallest missing authority or
environment change. Do not add silent skips, broaden permissions, claim
unexecuted host/ROS evidence, or introduce compatibility fallback behavior.

## Preserve Unrelated Changes

The planning worktree already contains a user-owned modification to
`docs/about/05_ux_decision_catalogue.md` and concurrent untracked slice-plan
files. Treat all pre-existing and concurrent work as user-owned. Before editing,
inspect `git status --short` and relevant diffs. Never reset, clean, stash,
overwrite, delete, reformat, stage, or commit unrelated paths.

Implementation must remain inside `apps/codex-daily/` and this feature pipeline
except for explicitly approved durable docs. Do not modify `buddy_*`,
`docs/contracts`, runtime assets, build/install/log outputs, Codex home data, or
the operator's default Codex Daily database. Stop if overlap cannot be preserved
safely.

## Expected Final Summary

Report:

- `implemented` or `blocked`, exact branch, commit, and reviewed baseline;
- the overnight lifecycle, restart/orphan recovery, source supersession,
  concurrency, timeout/retry, retention, deletion race, rollback, diagnostics,
  shutdown, responsive, and keyboard behavior proven;
- deterministic fixture proof of exact GPT-5.6 Sol/medium/ephemeral/no-fallback/
  strict-schema fields and zero ordinary-thread mutation;
- the installed CLI/schema and one synthetic-only host-proof result, including a
  truthful safe environment blocker if it could not run;
- explicit proof that no real transcript was read and no prompt/raw output/
  reasoning/protocol/credential reached persistence, logs, browser, export,
  diagnostics, docs, or artifacts;
- canonical files changed and all placeholder/debug/duplicate paths removed;
- every focused, aggregate, Playwright, production smoke, repository contract,
  ROS, whitespace, and protected-range command with exact outcome/counts;
- README/runbook changes and exact local startup/troubleshooting guidance;
- recorded deviations, remaining risks, and deferred `FUP-###`/issue scope;
- confirmation that unrelated user/concurrent changes and protected paths were
  preserved; and
- readiness for independent `5_Review`, not a claim of self-approval, merge
  authority, or cleanup readiness.

## Readiness Gate

- Exact slice: integrated operational proof and bounded hardening of implemented
  Recent Session Briefs Slices 01–03.
- Out of scope: redesign, new AI provider/model, real transcript verification,
  chat/task automation, external integration, deployment, and all deferred
  follow-ups.
- Follow-ups: none included; `FUP-001`–`FUP-005` remain deferred.
- Relevant modules, existing patterns, cleanup, non-regression boundaries,
  acceptance criteria, tasks, commands, host proof, environment deviations,
  risks, stop conditions, preservation rules, and final summary are specified.
- Implementation authority: the user's autonomous implementation request permits
  this slice only after Slices 01–03 are implemented and verified against their
  approved implementation-ready plans.
