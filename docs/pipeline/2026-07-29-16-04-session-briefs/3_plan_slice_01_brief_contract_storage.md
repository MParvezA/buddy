# Codex Daily — Slice 01 Brief Contract And Storage Plan

## Implementation Status

Status: planned
Commit:
Verification:
Deviations:
Follow-ups:

## Context And Selected Slice

- Repository: `/home/syncrobot/buddy`
- Planning branch target: `dev`
- Recommended implementation branch:
  `feature/2026-07-29-16-04-session-briefs`
- Feature folder:
  `docs/pipeline/2026-07-29-16-04-session-briefs/`
- Selected vertical slice: `01 — Brief Contract And Storage`
- Sequence: `01 of 04`
- Dependencies: reviewed Codex Daily baseline ending at `f255d46`; no feature
  slice dependency.
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`, `CURRENT.md`,
  `docs/about/05_ux_decision_catalogue.md`, and the archived Codex Daily slice
  plans and review under
  `docs/pipeline/_archive/2026-07-29-10-15-codex-daily/`.

Implement one runnable, privacy-bounded session-brief contract from observed
thread selection through durable SQLite state, HTTP/SSE delivery, browser data
ownership, export, deletion, retention, and restart recovery. Exercise the
contract with a deterministic placeholder analyzer that never reads a turn and
cannot be mistaken for GPT-5.6 output.

This slice deliberately does not perform live model work. Slice 02 must replace
the temporary placeholder analyzer and regenerate its rows before the generated
brief UI is shipped.

## Repository Rules

- Consulted: the source documents above, root `README.md`,
  `apps/codex-daily/README.md`, current Fastify/React/SQLite code and tests, the
  archived Codex Daily plans, and the `3-plan` skill. No root `AGENTS.md` or
  `docs/rules/README.md` exists.
- Constraints applied: extend the single `apps/codex-daily/` Node 24/npm 11
  Fastify/React/Vite package; preserve loopback and same-origin enforcement,
  read-only ordinary Codex sessions, coordinated SQLite writes, minimal local
  retention, facts-before-generated-interpretation, human-confirmed completion,
  and the ROS protected-path boundary.
- Rule updates: None

## Exact Scope

- Define one shared, runtime-validated structured brief and lifecycle DTO.
- Select at most the 10 newest eligible observed sessions by literal recency.
- Persist a last-good structured brief separately from the latest generation
  job so stale content can remain readable while a replacement is queued or
  running.
- Reconcile source revisions, deduplicate refresh intent, discard superseded
  results, recover orphaned work after restart, and publish state changes.
- Add read, refresh-all, per-session refresh, and SSE endpoints.
- Add a browser API adapter and provider for the same snapshot contract. Do not
  render a second or provisional session-card UI in this slice.
- Retain out-of-window last-good briefs for 24 hours, cancel their queued jobs,
  and prune expired rows.
- Add structured briefs and safe job metadata to diagnostics counts and JSON
  export.
- Coordinate relevant day deletion and delete-all with brief work so a finishing
  job cannot recreate deleted local data.
- Use a deterministic placeholder analyzer to prove the complete state path
  without `thread/read`, `thread/start`, `turn/start`, GPT, transcript content,
  workspace access, or ordinary-session mutation.

## Explicit Non-Goals

- Transient turn extraction, first-intent/recent-six selection, redaction, prompt
  construction, or the 32,000-character input cap; Slice 02 owns them.
- Calling `gpt-5.6-sol`, selecting reasoning effort, creating ephemeral analysis
  threads, requesting structured model output, or extending the fake App Server
  for model calls; Slice 02 owns them.
- The final debounce, two-worker concurrency, two-minute timeout, retry schedule,
  refusal handling, or model-unavailable policy; Slice 02 owns them.
- Replacing “Active and recent Codex chats,” changing runtime-first card order,
  showing generated sections, manual-refresh controls, responsive brief cards,
  or accessibility polish; Slice 03 owns them.
- Claiming placeholder content is `GPT-5.6 derived`, treating chat-reported work
  as confirmed completion, or inserting inferred actions into Needs You or the
  morning plan.
- More than 10 sessions, user settings for count/depth/model, weekly synthesis,
  notifications, external integrations, accounts, remote access, or ordinary
  chat control.
- A second database, app package, generic job framework, generic AI abstraction,
  persistent transcript cache, browser persistence, or compatibility API.
- Changes to Buddy ROS packages, launch/config contracts, or root build behavior.

## Follow-Up Scope

- Included `FUP-###` items: none.
- Still deferred: `FUP-001` user-tunable session count, `FUP-002` per-session
  analysis depth, `FUP-003` weekly synthesis, `FUP-004` external notifications,
  and `FUP-005` automatic ordinary-chat actions.
- The deterministic placeholder is an explicitly roadmap-approved temporary
  implementation seam, not deferred product scope. Its removal condition is
  successful Slice 02 host-model verification and regeneration of placeholder
  rows.

## Central Issue Scope

- Included issue IDs: none.
- Still deferred issue IDs: none identified.
- Newly created issue IDs: none.
- No `docs/issues/register.md` exists. If implementation discovers durable debt
  outside this slice, stop and report it rather than silently absorbing it.

## Canonical Mental Model And Required Cleanup

A session brief is a model-derived interpretation associated with one observed
thread revision. It is neither the transcript nor a task, attention item, daily
report, or proof of completion.

Persist two related records:

1. A **last-good brief** keyed by thread ID. It contains only validated structured
   content, the source `updatedAt`, generation metadata, and retention metadata.
2. A **latest job** keyed by thread ID. It contains one generation token, target
   source `updatedAt`, reason, analysis status, bounded attempt/timing metadata,
   and a safe failure category.

This separation is required. `freshness` is derived by comparing the last-good
source revision to the current target revision; `analysisStatus` describes the
latest job. Therefore a stale last-good brief can truthfully coexist with a
queued, analyzing, unavailable, or failed replacement. Do not collapse these
axes into one ambiguous status string or keep historical job rows.

The source revision is exactly `{threadId, updatedAt}`. Recency uses
`recencyAt ?? updatedAt`; ties are resolved by thread ID for deterministic
ordering. Eligibility is non-archived, top-level ordinary threads already
admitted by the observer and not present in `observer_thread_exclusions`.
Reporting threads remain excluded by the observer boundary. When fewer than 10
eligible sessions exist, select all of them.

Required cleanup:

- Add one `session-briefs` contract; do not add a free-text summary field,
  report-narrative reuse, attention projection, or observer-snapshot extension.
- Keep the existing observer DTO factual. The browser merges brief items with
  observer threads by `threadId`.
- Do not change the existing Today card selection or heading in this slice;
  Slice 03 removes the metadata-only 20-card/runtime-first policy exactly once.
- Do not serialize `undefined`, raw analyzer envelopes, arbitrary error messages,
  prompts, turns, reasoning, tool payloads, or protocol objects.
- Mark placeholder rows with generator `deterministic_placeholder` and
  `modelId: null`; never label them GPT-derived.
- Slice 02 must remove the production placeholder branch, migrate or delete
  placeholder rows, and queue the current selected revisions. Do not retain
  “placeholder or live model” as a permanent compatibility behavior.

## Shared Contract

Create `src/shared/session-briefs.ts` as the sole server/client contract.

Canonical public types:

- `SessionBriefAnalysisStatus`:
  `queued | analyzing | ready | unavailable | failed`.
- `SessionBriefFreshness`: `missing | current | stale`.
- `SessionBriefConfidence`: `high | medium | low`.
- `SessionBriefContent`:
  - `currentState`: one non-empty paragraph, maximum 600 characters;
  - `done`: zero to five non-empty items, maximum 280 characters each;
  - `operatorActions`: zero to five non-empty imperative suggestions, maximum
    280 characters each;
  - `blockers`: zero to five non-empty items, maximum 280 characters each;
  - `confidence`;
  - `evidence`: zero to six labels, maximum 120 characters each, matching
    `(user|assistant):(first-intent|recent-[1-6])`.
- `SessionBriefLastGood`: the content plus `sourceUpdatedAt`, `generatedAt`,
  `generator`, and nullable `modelId`.
- `SessionBriefFailure`: a bounded category and timestamp only. Reserve the
  categories `observer_unavailable`, `source_missing`,
  `empty_usable_content`, `analysis_unavailable`, `timeout`, `refusal`,
  `invalid_output`, and `internal`; never expose the originating exception.
- `SessionBriefItem`: `threadId`, `targetUpdatedAt`, `analysisStatus`,
  `freshness`, nullable `lastGood`, nullable safe `failure`, and nullable
  `queuedAt`/`startedAt` plus `updatedAt`.
- `SessionBriefSnapshot`: observer connection state/capability, `selectedAt`,
  the selected ordered `items` array (maximum 10), and aggregate `total`,
  `queued`, `analyzing`, `ready`, `stale`, `unavailable`, and `failed` counts.
- `SessionBriefSseEvent`: monotonic process-local event ID and snapshot.

Use a strict runtime validator at the analyzer-to-repository boundary. Require
exact object keys, trim text, reject invalid counts/enums, control characters,
HTML markup, embedded-credential URLs, and malformed evidence labels. Persist
JSON arrays only after this validator succeeds. Repository reads must validate
and fail safely rather than pass corrupt JSON to the browser.

`ready` means there is no active job and the last-good source equals the target.
`freshness` is `missing` without a last-good brief, `current` on an exact source
match, and `stale` otherwise. A failed manual refresh may therefore expose
`analysisStatus: failed`, `freshness: current`, and the prior current result.

## Persistence And Retention Contract

Add migration `006_session_briefs.sql` using the existing ordered, transactional
migration runner.

Create:

- `session_briefs`, keyed by `thread_id` with an `ON DELETE CASCADE` foreign key
  to `observed_threads`, source revision, generated time, generator/model,
  bounded structured fields/JSON arrays, confidence, `updated_at`, and nullable
  `out_of_window_at`;
- `session_brief_jobs`, keyed by `thread_id` with an `ON DELETE CASCADE` foreign
  key, unique generation `job_id`, target source revision, reason
  `automatic | manual | retry`, status
  `queued | analyzing | unavailable | failed`, bounded attempt/timing fields,
  safe failure category/time, and `updated_at`; and
- indexes needed for grace-period pruning and queued-job lookup.

Do not persist a `ready` job row. Successful promotion must atomically:

1. verify the current job ID and source revision still match;
2. validate/write the last-good structured brief;
3. clear its out-of-window marker; and
4. delete the job row.

If the generation token or revision no longer matches, discard the result
without altering the last-good row. A newer observer revision replaces queued
intent for the prior revision. A second refresh while the same revision is
queued/analyzing is idempotent; a later refresh after completion may create a
new generation token for the unchanged revision.

On selection reconciliation:

- clear `out_of_window_at` for selected rows;
- create automatic work for a selected missing/stale revision only after an
  observer snapshot has become usable;
- delete jobs immediately for threads leaving the selected window;
- set `out_of_window_at` once for last-good rows leaving the window; and
- delete last-good rows whose marker is at least 24 hours old.

Run pruning at startup, on observer reconciliation, and on an injected hourly
retention sweep so quiet expired rows do not remain indefinitely. A missing,
deleted, or newly excluded observed thread cascades brief and job rows
immediately.

On startup, atomically recover every orphaned `analyzing` job to `queued`, clear
its start time, retain its attempt count, and do not erase the last-good brief.
Do not begin work until the observer has supplied a usable snapshot. On
disconnect, keep selected facts and last-good briefs visible; new automatic or
manual placeholder work remains unavailable rather than pretending Codex is
usable.

The placeholder analyzer receives only thread ID and source revision, never an
observer detail or transcript. It returns deterministic non-claiming content:
the session metadata is ready for future GPT-5.6 analysis, with empty done,
action, blocker, and evidence lists and low confidence. Its output is explicitly
identified as placeholder data.

## API, SSE, And Browser Ownership

Add:

- `GET /api/session-briefs`;
- `GET /api/session-briefs/events`, using SSE event name `session-briefs`,
  monotonic IDs, an initial authoritative snapshot, keepalives, and listener
  cleanup;
- `POST /api/session-briefs/refresh` for the current selected window; and
- `POST /api/session-briefs/:threadId/refresh` for one currently eligible
  selected session.

GET and mutation responses must use `Cache-Control: no-store`. Successful refresh
requests return `202` with the authoritative snapshot. Refreshing already
queued/analyzing work is idempotent. Validate IDs with the existing bounded ID
policy. Return a safe `404` for an unknown thread, `409` for a known but
non-selected session, and `503` with `observer_unavailable` when disconnected;
queue nothing in those cases. One session failure must not change another.

The read/SSE DTO contains no transcript, prompt, output envelope, raw exception,
workspace file contents, command, diff, or reasoning. The refresh routes express
local analysis intent only and must send no ordinary Codex mutation.

Add a dedicated client API adapter and `SessionBriefProvider` following the
observer/attention provider patterns:

- initial GET followed by EventSource subscription;
- last-snapshot preservation on SSE error;
- truthful loading/error state;
- refresh-all and per-thread methods;
- EventSource cleanup on unmount; and
- no `localStorage`, `sessionStorage`, IndexedDB, service-worker, or browser-cache
  persistence.

Mount the provider once in `App.tsx` so the server-to-browser contract is
runnable and tested. Do not render placeholder content or add a competing
session list. Slice 03 consumes this provider and performs the one canonical UI
replacement.

## Privacy, Export, Deletion, And Lifecycle Coordination

Extend the existing operations contract rather than creating a second privacy
service:

- add retained-count categories `sessionBriefs` and `sessionBriefJobs`;
- increment `CodexDailyExport.schemaVersion` to `2`;
- export structured last-good briefs and safe job/lifecycle metadata in stable
  order;
- include generator/model/source/timestamps and structured lists only; and
- prove sentinel transcript, prompt, secret, exception, and raw-output strings
  cannot appear.

Relevant day deletion removes a brief and its latest job when any of its source
revision, generated/queued/started/failure/updated timestamps falls inside that
day's existing timezone-aware bounds. Delete-all removes both tables and
preserves the existing report-preference reset behavior. Both operations retain
`codexHistoryChanged: false` and the rediscovery notice.

Integrate the brief service into the existing `WriteCoordinator` and
pause/resume lifecycle:

- stop accepting new brief work before destructive maintenance;
- prevent background repository mutations while maintenance owns the database;
- cancel queued work and drain/cancel bounded in-flight placeholder work before
  deletion;
- publish the post-delete authoritative snapshot only after writers resume; and
- stop the retention timer, detach observer listeners, drain work, then close
  SQLite during application shutdown.

Do not delete or archive an ordinary Codex session. Do not allow a finishing
generation token to recreate a deleted row.

## Likely Files, Modules, Components, And Tests

Extend these existing paths and patterns:

- `apps/codex-daily/src/shared/session-briefs.ts`
- `apps/codex-daily/src/shared/operations.ts`
- `apps/codex-daily/src/server/storage/migrations/006_session_briefs.sql`
- `apps/codex-daily/src/server/briefs/session-brief-validator.ts`
- `apps/codex-daily/src/server/briefs/session-brief-repository.ts`
- `apps/codex-daily/src/server/briefs/session-brief-service.ts`
- `apps/codex-daily/src/server/briefs/placeholder-brief-analyzer.ts`
- `apps/codex-daily/src/server/briefs/session-brief-routes.ts`
- `apps/codex-daily/src/server/privacy/privacy-service.ts`
- `apps/codex-daily/src/server/diagnostics/diagnostics-service.ts`
- `apps/codex-daily/src/server/app.ts`
- `apps/codex-daily/src/client/api/session-briefs-client.ts`
- `apps/codex-daily/src/client/data/session-briefs-context.tsx`
- `apps/codex-daily/src/client/App.tsx`

Likely focused tests:

- `apps/codex-daily/test/server/briefs/session-brief-validator.test.ts`
- `apps/codex-daily/test/server/briefs/session-brief-repository.test.ts`
- `apps/codex-daily/test/server/briefs/session-brief-service.test.ts`
- `apps/codex-daily/test/server/briefs/session-brief-routes.test.ts`
- `apps/codex-daily/test/client/data/session-briefs-context.test.tsx`
- updates to `src/server/storage/database.test.ts`,
  `test/server/privacy/privacy-service.test.ts`,
  `test/server/privacy/privacy-routes.test.ts`,
  `test/server/runtime/full-lifecycle.test.ts`, `src/server/app.test.ts`, and
  `src/client/App.test.tsx`
- a narrowly scoped API/SSE browser assertion in the existing observer or
  recovery/privacy Playwright workflow; do not create final brief-card browser
  coverage before Slice 03.

Follow actual committed naming if a small local convention differs, but do not
create parallel repository, lifecycle, API, or provider layers.

## Existing Patterns To Follow

- `database.ts`: ordered SQL migrations under one `BEGIN IMMEDIATE`.
- Observer/planning/report repositories: injected `DatabaseSync`, explicit row
  mapping, stable sort order, foreign keys, and transaction ownership.
- `ObserverService` and `AttentionService`: injected clocks/timers, EventEmitter
  snapshots, start/stop idempotence, and listener cleanup.
- Observer and attention routes: authoritative initial SSE snapshot, event IDs,
  keepalives, cleanup, bounded validation, and safe error DTOs.
- `observer-context.tsx`: initial fetch, EventSource subscription, retained last
  snapshot on live-update failure, and provider-owned mutations.
- `WriteCoordinator` plus `PrivacyService`: quiesce writers around destructive
  local-data operations and resume them in `finally`.
- Operational-hardening export: deterministic product DTOs, explicit retained
  counts, local-only deletion, and no raw thread detail.
- Vitest temporary/in-memory databases, injected clocks, Testing Library, the
  deterministic fake App Server, and Playwright's isolated production server.

## Behavior That Must Not Regress

- Needs You remains Priority 01, today's outcomes Priority 02, the current
  metadata session section Priority 03 until Slice 03, and factual completed
  turns Priority 04.
- Planning, task links, attention, report history, settings, export, and deletion
  remain usable with Codex disconnected.
- Ordinary sessions remain read-only. No brief route or worker calls any Codex
  mutating method.
- Full thread turns remain confined to the existing no-store detail request and
  never enter the brief repository, API, SSE, export, diagnostics, browser
  provider, logs, or tests.
- Factual observed completion never marks a morning outcome complete.
- Reporting-thread exclusion remains durable and such threads never become
  eligible.
- Day deletion continues recomputing observed `last_activity_at`, preserving
  cross-day successor tasks, and deleting only local monitor data.
- Same-origin loopback rejection, write coordination, graceful shutdown, missed
  report recovery, and last-good offline behavior remain intact.
- Existing migration files remain immutable; add migration `006`.
- Codex Daily remains outside the colcon package graph and no `buddy_*` or
  `docs/contracts` path changes.

## Acceptance Criteria

1. A fresh and an upgraded database apply migration `006`; foreign-key and
   migration health checks pass.
2. The newest eligible sessions are selected in literal
   `recencyAt ?? updatedAt` order with a thread-ID tie-break, never exceed 10,
   and exclude archived/reporting/non-top-level sessions.
3. Source freshness compares exact thread ID and `updatedAt`. A newer revision
   immediately yields stale last-good content and one replacement job.
4. Last-good content and latest-job state are stored separately, so queued,
   analyzing, unavailable, and failed refreshes preserve prior content and its
   freshness.
5. Duplicate reconciliation and repeated refresh during the same pending job do
   not create duplicate work. A manual refresh after completion may create one
   new job for an unchanged revision.
6. Atomic promotion succeeds only for the current generation token/revision;
   superseded or deleted work cannot overwrite or recreate state.
7. Restart converts orphaned analyzing work to queued and resumes only after
   observer readiness. Disconnect retains cached briefs and rejects manual
   refresh without queueing.
8. The placeholder analyzer produces deterministic, visibly non-GPT,
   non-claiming structured content without calling `thread/read`, App Server
   creation/turn methods, tools, a model, or a workspace.
9. Runtime validation enforces exact fields, list and character limits, safe
   evidence labels, enums, and content restrictions before persistence.
10. GET and SSE return one authoritative ordered snapshot, truthful aggregate
    counts, separate freshness/status, no-store/no-cache headers as appropriate,
    keepalives, and no listener leaks.
11. Refresh-all and per-thread refresh return `202`, remain idempotent while
    pending, and give safe unknown/not-selected/disconnected errors without
    affecting other sessions.
12. The browser provider loads and receives live changes, preserves the last
    snapshot on SSE error, exposes refresh actions, cleans up, and persists
    nothing in browser storage. No duplicate/provisional session UI is added.
13. A row leaving the recent window has its job canceled, remains retained but
    absent from the public snapshot for 24 hours, re-entry clears the grace
    marker, and expiry pruning removes it.
14. Export schema version 2 contains stable structured briefs and safe lifecycle
    metadata only. Retained counts include both new categories.
15. Relevant day deletion and delete-all quiesce brief work, remove the intended
    rows, cannot be undone by a finishing analyzer, never mutate Codex history,
    and preserve rollback/resume behavior on failure.
16. Sentinel raw turn text, prompts, model envelopes, secrets, credential URLs,
    reasoning, exception messages, commands, and diffs are absent from SQLite,
    logs, diagnostics, API/SSE, export, browser state, and built artifacts.
17. Existing planning, observer, attention, reporting, privacy, browser, and
    repository contract tests pass without protected-path changes.

## Ordered Implementation Tasks

1. Confirm the baseline app and current working diff match the paths and
   contracts above. Stop if overlapping user edits cannot be preserved.
2. Add failing shared-validator tests for exact keys, bounds, evidence grammar,
   safe text, placeholder provenance, and raw-content rejection.
3. Add migration `006` and failing repository tests for last-good/job separation,
   source matching, idempotent enqueue, token-guarded promotion, restart recovery,
   selection marking, 24-hour pruning, cascades, and deterministic reads.
4. Implement the shared DTO/validator and repository against those tests. Keep
   persisted JSON limited to validated structured arrays.
5. Add failing service tests for literal recent-10 selection, observer readiness,
   revision invalidation, supersession, manual unchanged refresh, disconnect,
   failure isolation, retention sweep, start/stop, and deletion races.
6. Implement the deterministic placeholder analyzer and brief service with
   injected clock/timers/analyzer, observer subscription, process-local SSE
   sequence, coordinated background writes, and bounded drain/cancel behavior.
7. Add failing route/SSE tests for initial snapshot, progress events, refresh
   status codes, idempotence, validation, no-store behavior, keepalive cleanup,
   and content/privacy boundaries; then register the routes in the existing app.
8. Add the browser adapter/provider and focused Testing Library tests for
   GET-to-SSE transition, refresh methods, retained snapshot on failure, and
   cleanup. Mount it in `App.tsx` without changing the dashboard session UI.
9. Extend diagnostics counts, export schema/version, relevant-day deletion,
   delete-all, pause/resume, and shutdown. Add explicit privacy and rollback race
   tests before changing these paths.
10. Add one bounded Playwright API/SSE assertion proving production composition
    reaches the browser without raw content. Do not implement Slice 03 cards.
11. Inspect SQLite, API/SSE, export, logs, and built output with sentinel content;
    remove temporary debug output and any superseded duplicate contract.
12. Run the focused and full verification below. Update only this plan's status
    block with exact results, commit, deviations, and follow-ups.

## Verification Commands And Expected Outcomes

Run from `/home/syncrobot/buddy/apps/codex-daily`:

```bash
npm test -- --run test/server/briefs/session-brief-validator.test.ts
npm test -- --run test/server/briefs/session-brief-repository.test.ts
npm test -- --run test/server/briefs/session-brief-service.test.ts
npm test -- --run test/server/briefs/session-brief-routes.test.ts
npm test -- --run test/client/data/session-briefs-context.test.tsx
npm test -- --run test/server/privacy/privacy-service.test.ts
npm test -- --run test/server/privacy/privacy-routes.test.ts
npm test -- --run test/server/runtime/full-lifecycle.test.ts
npm test -- --run src/server/storage/database.test.ts src/server/app.test.ts
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run check
```

Expected: all focused contract, repository, lifecycle, privacy, and client tests
pass; package-wide tests and the production build pass; the existing browser
workflows remain green; the new bounded browser assertion observes API/SSE
updates with no transcript content; and no live GPT/App Server mutation is made
by session-brief code.

Run the migration/privacy inspection against a disposable database, using a
test helper or route fixture rather than shell-inserting malformed data:

```bash
CODEX_DAILY_DB_PATH=/tmp/codex-daily-session-briefs.sqlite npm run start
```

Expected: the built app binds only to `127.0.0.1`, reports migration
`006_session_briefs.sql`, starts with a clean brief snapshot, keeps planning
usable when Codex is unavailable, and shuts down cleanly. Remove only the
explicitly named disposable SQLite file and sidecars after the process exits.

Run from `/home/syncrobot/buddy`:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
colcon list
git status --short
```

Expected: no whitespace errors; no protected ROS/contract paths changed; all
repository contract tests pass; package discovery remains the same 16 Buddy
packages; and status contains only intended Codex Daily/feature-pipeline changes
plus explicitly preserved pre-existing user work.

If the repository's known untouched ROS failures are relevant to a broader
verification run, report their exact commands and unchanged-path evidence. Do
not modify ROS code to make this web slice pass.

## Risks, Dependencies, And Stop Conditions

- SQLite migration errors can make existing local data unreadable. Require both
  fresh and upgrade-path tests; stop rather than editing prior migrations.
- One status field cannot represent stale content plus an active replacement.
  Stop if implementation attempts to collapse freshness and job status or add
  historical-job compatibility rows.
- Background completion can race with observer updates and deletion. Require a
  generation-token check in the final write transaction and coordinated
  pause/drain tests; do not rely on timing alone.
- The placeholder can be mistaken for real analysis. It must contain no
  chat-specific claims, use `modelId: null`, and remain unrendered. Stop if the
  only implementation path would label it GPT-derived.
- Raw-content leakage is a release blocker. Stop if repository, export, SSE,
  diagnostics, logs, or browser state can accept arbitrary transcript/model
  envelopes.
- A thread may leave/re-enter the recent window during work. Require immediate
  job cancellation, stable grace timestamps, and token-guarded results.
- App Server availability inside restricted sandboxes is environment-dependent.
  This slice does not need live content/model access; do not weaken tests or add
  a second provider to work around it.
- Stop if the slice requires the Slice 02 transcript/model pipeline, Slice 03 UI,
  a new dependency, a generic queue framework, broad lifecycle refactoring,
  external services, a deferred `FUP-###`, or changes outside app/docs scope.
- Stop if required tests cannot run, the plan conflicts materially with current
  code, the implementation becomes larger than this contract/storage slice, or
  unrelated user changes overlap required files.

When blocked, preserve the worktree, leave a minimal failing proof when safe,
mark this plan `blocked`, record the affected acceptance criterion and exact
command, and request the smallest missing decision. Do not add silent skips,
dual schema shapes, or compatibility fallbacks.

## Preserve Unrelated Changes

The worktree already contains a user-owned modification to
`docs/about/05_ux_decision_catalogue.md` and untracked feature-pipeline files.
Inspect `git status --short` and relevant diffs before editing. Never reset,
clean, stash, overwrite, reformat, stage, or commit unrelated paths. Preserve
concurrent slice-plan files produced by other agents. Stop if overlap cannot be
resolved without discarding another change.

## Expected Final Summary

Report:

- status (`implemented` or `blocked`), branch, and commit;
- the shared DTO, SQLite tables, selection/revision, retention, API/SSE, browser
  provider, export, deletion, and restart behavior delivered;
- explicit proof that placeholder analysis read no turns, called no model, made
  no Codex mutation, and was never labeled GPT-derived;
- canonical files changed and any temporary/superseded paths removed;
- every focused, package-wide, browser, production-smoke, repository-contract,
  and protected-path verification command with outcome;
- migration upgrade and foreign-key health evidence;
- privacy sentinel and deletion-race evidence;
- deviations, remaining risks, and deferred `FUP-###`/issue references;
- confirmation that unrelated user/concurrent changes were preserved; and
- readiness for Slice 02 implementation and independent review, not a claim of
  self-approval or merge authority.
