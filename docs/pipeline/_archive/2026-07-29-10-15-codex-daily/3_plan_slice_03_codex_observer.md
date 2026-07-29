# Codex Daily — Slice 03 Codex Observer Plan

## Implementation Status

Status: implemented
Commit: `Slice 03: Codex Observer` (this status-bearing commit)
Verification: `npm run check` passed with 11 files/33 tests; full Playwright passed repeatedly and independently (6 passed, 2 intentional duplicate mobile-flow skips); repository contracts passed 4/4; protected-path diff was empty; focused protocol/privacy tests proved content stripping, request-key isolation, repeated blocker episodes, reconnect, pagination, SSE, links, and exclusions.
Deviations: The deterministic fake App Server uses Python because Node subprocess stdin was unreliable in this environment; production remains Node/TypeScript. A real-session smoke was skipped to avoid unnecessary transcript exposure. The full ROS matrix was not green in untouched packages (`buddy_task_executor`, `buddy_navigation`, and a hanging `buddy_bringup` run); narrowed repository-boundary verification passed.
Follow-ups: None. FUP-001 through FUP-006 remain deferred.

## Context

- Repository: `/home/syncrobot/buddy`
- Planning branch: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Selected vertical slice: `03 — Codex Observer`
- Sequence number: `03`
- Depends on: Slice 01 Daily Dashboard and Slice 02 Morning Planning
- Source docs: `1_design.md`, `2_alignment.md`, `3_plan.md`, `CURRENT.md`,
  and `docs/about/05_ux_decision_catalogue.md`

Implement one read-only observer path through the existing
`apps/codex-daily/` application: spawn the local `codex app-server` over stdio,
discover ordinary top-level threads, normalize inventory and live protocol
signals, persist only the small observer model, stream changes to the browser,
and let the operator explicitly link tasks and threads.

The protocol reconnaissance used the current local
`codex-cli 0.146.0-alpha.3.1`, its `codex app-server --help`, its generated
stable TypeScript schema, and the current Codex App Server manual. The
implementation must remain tolerant of compatible later CLI versions rather
than hard-coding this version.

## Repository Rules

- Consulted: root `README.md`, the source feature docs above, and the `3-plan`
  skill; no root project `AGENTS.md` or `docs/rules/README.md` exists.
- Constraints applied: extend the bounded `apps/codex-daily/` Node 24/npm 11
  Fastify/React/Vite application established by Slice 01; use Slice 02's
  database, repository, planning-service, and API patterns; do not alter Buddy
  ROS packages or root ROS build behavior.
- Rule updates: None

## Scope

The vertical result is a dashboard whose Live Work and Recently Completed
surfaces use observed local Codex data, whose connection state is always
visible, whose changes arrive through server-sent events (SSE), and whose tasks
can have explicit many-to-many links to threads. A secondary thread detail
request may read full history transiently from App Server, but the application
must not persist, log, index, or include that content in SSE events.

The adapter uses the stable JSONL-over-stdio surface in two explicit modes:

- `standalone_history` (default) spawns `codex app-server --stdio`. It discovers
  all stored sessions and polls for updates, but must not claim that approvals or
  live events owned by another Codex process are visible.
- `shared_live` spawns `codex app-server proxy` and connects to an
  operator-managed App Server daemon. It can expose live events for chats routed
  through that same daemon. Codex Daily does not start, stop, or reconfigure the
  daemon.

Both modes use the same protocol lifecycle:

1. Spawn the mode's fixed executable and argument list directly, without a shell
   or user-provided command string.
2. Send one `initialize` request with Codex Daily client metadata, await its
   response, then send the `initialized` notification.
3. Page through `thread/list`, explicitly including the top-level interactive
   sources `cli`, `vscode`, and `appServer`.
4. Use `thread/read` only for an operator-requested detail view; use
   `includeTurns: true` there and keep the result in request memory only.
5. Consume supported notifications and server requests from stdout when the
   selected mode can observe them, while
   periodic inventory refreshes reconcile changes that are not delivered to
   this observer connection.
6. Never call `thread/start`, `thread/resume`, `turn/start`, approval-response,
   archive, delete, name, metadata-update, or other mutating/control methods.

Do not opt into `experimentalApi`.

## Explicit Non-Goals

- Deriving, displaying, acknowledging, or dismissing Needs You items; Slice 04
  owns attention policy.
- Creating the dedicated reporting thread or generating reports; Slice 05 owns
  that work.
- Prompting, steering, interrupting, approving, archiving, deleting, naming, or
  otherwise changing ordinary Codex threads.
- Suggested/automatic task-thread links or completion suggestions.
- Treating a completed turn as completion of a daily task.
- Persisting full transcripts, prompts, responses, reasoning, diffs, command
  output, raw App Server messages, or arbitrary item payloads.
- Direct WebSocket/Unix-socket transports, daemon lifecycle management,
  remote-host, cloud, multi-user, or non-Codex integrations. The fixed
  `codex app-server proxy` child is the sole shared-daemon bridge.
- Vendoring the full generated App Server schema or supporting experimental
  methods.

## Follow-Up Scope

- Included: no deferred `FUP-###` item.
- Still deferred: FUP-001 evidence-backed completion, FUP-002 weekly review,
  FUP-003 third-party integrations, FUP-004 multi-device sync, FUP-005
  cost/limit insights, and FUP-006 proactive chat control.
- Slice 05 compatibility seam: reserve a durable observer-exclusion repository
  keyed by thread ID with reason `reporting`. Apply exclusions before observer
  persistence, API snapshots, and SSE publication. Do not create a reporting
  thread or expose report behavior in this slice.

## Central Issue Scope

- Included register IDs: none.
- Still deferred register IDs: none.
- Newly created register IDs: none. No `docs/issues/register.md` exists, and
  reconnaissance found no central issue overlapping this slice.

## Canonical Mental Model And Required Cleanup

The day remains the canonical unit. A Codex thread is observed evidence that can
be linked to zero or more daily tasks; it is not a task and cannot own or change
task completion.

Replace Slice 01 representative Live Work and Recently Completed data with the
observer API while preserving explicit offline and empty states. Remove any
fixture-only production imports made obsolete by this slice. Do not introduce
a second application package, database wrapper, HTTP server, event bus, task
model, or generic chat-history navigation. Unknown protocol statuses and
notifications must remain unknown/diagnostic rather than being coerced to idle,
successful, or completed.

## Observer Contract

### Narrow protocol client

`AppServerClient` owns one child process, newline framing, JSON parsing,
monotonic request IDs, request/response correlation, request timeouts, and
shutdown. Treat stderr as bounded diagnostics, never as protocol input. Reject
all pending calls when the child exits. Initialization timeout, invalid JSONL,
stdin failure, or unexpected process exit moves health out of `connected` and
enters bounded exponential reconnect with jitter; successful initialization
and a full inventory sync reset the backoff.

Unknown notification methods and unknown object fields are ignored and counted
as diagnostics so a compatible protocol extension does not crash the observer.
Malformed envelopes or known methods with invalid required fields fail the
current connection and force a clean resync. Inject the executable path,
process factory, clock, timers, and retry policy for deterministic tests.

### Canonical normalized model

- `ObserverConnectionHealth`: `connecting | connected | reconnecting |
  disconnected`, plus observation capability (`standalone_history |
  shared_live`), last successful sync time, last inventory refresh time, and a
  safe diagnostic message.
- `ObservedThread`: Codex thread ID, session ID, optional title, cwd, source,
  CLI version, created/updated/recency timestamps, archive flag, last-observed
  time, runtime state, active flags, and last normalized activity time.
- `ObservedThreadRuntime`: `unknown | not_loaded | idle | active |
  system_error`; preserve `waiting_on_approval` and
  `waiting_on_user_input` as separate flags.
- `ObservedActivity`: stable source key, thread ID, optional turn/item IDs,
  timestamp, category, lifecycle/status, and a short content-free label.

Normalize only signals needed by later slices:

- inventory and `thread/started`, `thread/status/changed`,
  `thread/archived`, `thread/unarchived`, and `thread/closed`;
- `thread/goal/updated` and `thread/goal/cleared`, preserving the structured goal
  status needed for an explicit `blocked` observation without retaining the goal
  text;
- `turn/started` and `turn/completed` statuses `completed`, `interrupted`, and
  `failed`;
- `item/started` and `item/completed` as content-free item-type/lifecycle
  facts;
- pending and resolved command/file/permission approvals,
  `item/tool/requestUserInput`, MCP elicitation, and
  `serverRequest/resolved`, without storing prompt or command content; and
- protocol/runtime errors as safe diagnostics.

Use semantic source keys derived from protocol IDs and lifecycle, backed by a
database unique constraint, so initial sync, polling, reconnect, and duplicate
notifications are idempotent.

### Persistence and API

Add one migration after Slice 02 with:

- `observed_threads`;
- `observed_activities`;
- `task_thread_links` with a composite task/thread uniqueness constraint and
  foreign keys;
- `observer_thread_exclusions` keyed by thread ID and constrained to known
  reasons, initially `reporting`.

Store no `preview`, turns, item bodies, raw JSON, command strings, diffs, or
message text. Retain only normalized activity needed for the daily timeline.
Do not introduce automatic pruning in this slice; inspect/export/deletion policy
belongs to Slice 06.

Expose:

- `GET /api/observer` for connection health, thread inventory, normalized
  activity, and task links;
- `GET /api/observer/events` for SSE snapshots/changes with event IDs,
  keepalives, disconnect cleanup, and no raw protocol payloads;
- `GET /api/observer/threads/:threadId` for transient on-demand detail through
  `thread/read`;
- `PUT /api/tasks/:taskId/threads/:threadId` to create an explicit link; and
- `DELETE /api/tasks/:taskId/threads/:threadId` to remove only that local link.

Validate IDs, return not-found for absent tasks/threads, make link creation
idempotent, and never translate these routes into Codex mutation calls. SSE
reconnection starts from a fresh authoritative observer snapshot; it must not
require retaining raw event streams.

## Likely Files And Modules

Extend these Slice 01/02 paths rather than create parallel infrastructure:

- `apps/codex-daily/src/shared/observer-types.ts`
- `apps/codex-daily/src/server/codex/app-server-protocol.ts`
- `apps/codex-daily/src/server/codex/app-server-client.ts`
- `apps/codex-daily/src/server/codex/activity-normalizer.ts`
- `apps/codex-daily/src/server/codex/observer-service.ts`
- `apps/codex-daily/src/server/codex/observer-routes.ts`
- `apps/codex-daily/src/server/storage/migrations/002_codex_observer.sql`
- `apps/codex-daily/src/server/storage/observer-repository.ts`
- the existing server composition/startup and graceful-shutdown modules
- the existing client API adapter/store
- `apps/codex-daily/src/client/features/live-work/`
- the existing dashboard and secondary thread-detail components

Likely tests and fixtures:

- `apps/codex-daily/test/fixtures/fake-codex-app-server.mjs`
- `apps/codex-daily/test/fixtures/app-server/*.jsonl`
- `apps/codex-daily/test/server/codex/app-server-client.test.ts`
- `apps/codex-daily/test/server/codex/activity-normalizer.test.ts`
- `apps/codex-daily/test/server/codex/observer-service.test.ts`
- `apps/codex-daily/test/server/storage/observer-repository.test.ts`
- `apps/codex-daily/test/server/codex/observer-routes.test.ts`
- `apps/codex-daily/test/client/features/live-work/live-work.test.tsx`
- `apps/codex-daily/e2e/codex-observer.spec.ts`

Follow the final file naming and composition conventions actually committed by
Slices 01–02 if they differ; update this list in the implementation summary
without creating duplicate layers.

## Existing Patterns To Follow

- Slice 01's single-package Node/Fastify lifecycle, shared API contracts,
  React query/state handling, Vitest/Testing Library, and Playwright setup.
- Slice 02's migration runner, injected database/repository pattern,
  transaction boundaries, validation/error responses, and task ownership.
- Root repository isolation: all web code and npm commands stay under
  `apps/codex-daily/`; ROS build and test entry points remain unchanged.
- Current App Server stable lifecycle: `initialize` response before
  `initialized`, cursor pagination for `thread/list`, and
  `thread/read(includeTurns: true)` without resume/subscription.

## Behavior That Must Not Regress

- Planning remains usable while Codex is absent, starting, or reconnecting.
- A new day and task remain independent of chats.
- Task completion remains operator-confirmed.
- One task can link to many threads and one thread can link to many tasks.
- Unlinked threads remain visible as unplanned observed work.
- A disappearing thread is not treated as deleted or completed.
- Archival changes thread metadata only and never task state.
- Deleting a local link or retained observer activity never mutates Codex.
- The dashboard keeps the approved attention-first order and responsive,
  accessible shell from Slice 01.
- Existing Buddy ROS tests and runtime behavior are untouched.

## Ordered Implementation Tasks

1. Reconcile the checked-out Slice 01/02 modules with the likely paths above;
   stop if their contracts materially conflict with this plan.
2. Add failing protocol tests and a fake executable/JSONL fixture covering
   handshake ordering, paginated list, on-demand read, notifications, server
   requests, malformed JSON, timeout, exit, restart, and graceful shutdown.
3. Implement the narrow protocol envelope decoder and stdio client with injected
   process/timing seams; do not vendor the full generated protocol.
4. Add the observer migration and repository tests for minimal columns,
   uniqueness/deduplication, many-to-many links, and reporting-thread exclusion.
5. Implement normalization as pure functions, including unknown-safe mapping and
   content stripping; prove raw messages, commands, diffs, reasoning, and item
   bodies cannot enter persisted/SSE DTOs.
6. Implement the observer service: fixed standalone/proxy mode selection,
   initialize, inventory pagination, periodic resync, exclusion-before-write,
   normalized event ingestion, capability-aware health transitions, bounded
   reconnect, and shutdown.
7. Add validated snapshot, transient detail, link/unlink, and SSE routes; wire
   them into the existing Fastify lifecycle.
8. Replace representative Live Work/Recently Completed production data with the
   observer snapshot/SSE adapter, add connection/empty/unknown states, transient
   detail, and explicit task-link controls.
9. Add route, component, and Playwright coverage for connected, disconnected,
   reconnecting, linked, unlinked, and excluded-reporting-thread behavior.
10. Remove superseded production fixtures/imports, run the focused and full
    verification below, and inspect the database plus HTTP/SSE output for
    retention violations.

## Acceptance Criteria

- The service starts and cleanly stops one injected/default fixed-argument
  App Server or proxy child without orphaning it.
- Default standalone mode labels itself `standalone_history`, refreshes stored
  sessions without claiming universal live approval/question coverage, and
  keeps last-known activity current through polling.
- Shared-live mode uses `codex app-server proxy`, fails visibly when the managed
  daemon is unavailable, and labels itself `shared_live`; deterministic tests
  prove that server requests/events received from that shared transport reach
  the normalized boundary.
- The wire order is `initialize` request, successful response, then
  `initialized`; no request is sent before initialization completes.
- All `thread/list` pages for `cli`, `vscode`, and `appServer` top-level threads
  are reconciled idempotently; excluded and child/subagent threads do not reach
  storage or UI.
- An operator can request thread detail through `thread/read` without resuming
  or mutating the thread, and no returned content is persisted or emitted over
  SSE.
- Runtime status, turn lifecycle, item lifecycle, approval/input request
  lifecycle, structured blocked/cleared goal state, archival, and safe errors
  normalize deterministically.
- Duplicate notifications, polling, and reconnect do not duplicate normalized
  activity.
- Health is visible as connecting/connected/reconnecting/disconnected, and
  loss of Codex does not block planning or cached observer data.
- SSE delivers an authoritative snapshot and subsequent normalized changes,
  sends keepalives, frees listeners on disconnect, and exposes no raw protocol
  payload.
- The operator can create and remove idempotent many-to-many task-thread links;
  neither operation changes task completion or the Codex thread.
- The database contains only approved metadata/normalized facts and no full
  transcript, preview, message, reasoning, command output, or diff.
- A thread ID recorded with exclusion reason `reporting` is filtered at
  inventory, persistence, snapshot, detail, and SSE boundaries, while no report
  feature is implemented.
- Unknown compatible fields/methods do not crash monitoring; invalid known
  envelopes force a visible reconnect rather than fabricated state.
- Existing Slice 01/02 tests and root ROS repository contracts still pass.

## Verification Commands

Run from `/home/syncrobot/buddy/apps/codex-daily` unless noted:

```bash
npm test -- --run test/server/codex/app-server-client.test.ts
npm test -- --run test/server/codex/activity-normalizer.test.ts
npm test -- --run test/server/codex/observer-service.test.ts
npm test -- --run test/server/storage/observer-repository.test.ts
npm test -- --run test/server/codex/observer-routes.test.ts
npm test -- --run test/client/features/live-work/live-work.test.tsx
npm run test:e2e -- codex-observer.spec.ts
npm run lint
npm run typecheck
npm run test
npm run build
npm run check
```

Expected: all focused fake-protocol, persistence, API/SSE, UI, and browser tests
pass; the package-wide quality gate passes; the production build contains no
representative observer fixture import.

From `/home/syncrobot/buddy`:

```bash
git diff --check
ROS_LOG_DIR=/tmp/buddy-test-logs colcon test --ctest-args --output-on-failure
colcon test-result --verbose
```

Expected: no whitespace errors; existing ROS packages build/test as before; the
test-result summary has zero failures.

A live `codex app-server` smoke check is useful when available but is not a
substitute for the deterministic fake-process suite. It must list/read only,
must not expose thread content in logs, and must not mutate any Codex thread.

## Risks And Dependencies

- App Server is evolving. Keep the decoder narrow and forward-compatible, record
  the runtime CLI version in diagnostics, and fail visibly on incompatible
  required fields.
- Standalone history mode does not receive every event produced through another
  Codex process. Periodic paginated inventory reconciliation is mandatory, and
  the UI must disclose this capability limit. Shared-live mode is the supported
  path for full live events from clients routed through the same managed daemon;
  do not use `thread/resume` merely to obtain subscriptions.
- Stdio errors can leak process lifetime or hang shutdown. Bound every request,
  initialization, retry timer, and child termination.
- Full-history detail is sensitive. Keep it request-scoped, exclude it from
  structured logs/errors/SSE, and test the storage boundary negatively.
- SSE reconnect and process reconnect can duplicate delivery. Database source
  uniqueness and authoritative snapshots, not browser assumptions, own
  idempotency.
- This slice depends on the exact Slice 01 server/client composition and Slice
  02 task/storage contract being present.

## Stop Conditions And Blocked Procedure

Stop and report rather than widening the slice when:

- Slices 01–02 are absent or their committed contracts materially contradict
  this plan.
- The installed stable App Server no longer supports stdio, `initialize`,
  `thread/list`, or `thread/read` as documented.
- Stored-session observation would require `thread/resume`, an experimental API,
  direct parsing of Codex session files/state DB, or mutation of a work thread.
- Minimal-retention guarantees cannot be enforced at storage, logging, API, or
  SSE boundaries.
- Implementation requires another web package/server/database, broad ROS
  changes, attention derivation, reporting, or proactive chat control.
- Required focused or package verification cannot run, or the slice is
  materially larger than planned.

When blocked, preserve the failing fixture/test and exact App Server
request/response or sanitized error, document the conflict and affected
acceptance criteria, and return to planning/alignment instead of adding a
compatibility fallback.

## Preservation Instructions

Inspect `git status` before editing and before committing. Preserve all unrelated
user and concurrent-agent changes, especially the currently untracked feature
documentation. Do not reset, rewrite, delete, stage, or commit unrelated paths.
Adapt to the implemented Slice 01/02 naming only where necessary and explain
every deviation.

## Expected Final Summary

The implementing agent must report:

- implementation status and commit hash;
- App Server lifecycle, inventory/read methods, normalized signals, health
  model, and reconnect behavior delivered;
- migrations, minimal-retention boundary, task-thread linking, and reporting-thread
  exclusion delivered;
- UI/SSE behavior and representative-data cleanup;
- tests and exact verification commands with outcomes;
- confirmation that no transcript/raw payload is persisted and no Codex thread
  mutation method is called;
- deviations, remaining risks, follow-ups, and unrelated changes preserved.

## Readiness Gate

This plan defines the exact slice, non-goals, deferred scope, likely files,
existing patterns, required cleanup, acceptance criteria, verification, risks,
stop conditions, preservation rules, and handoff format. It is implementation
ready only after explicit approval; `3_plan.md` alone is not an implementation
source.
