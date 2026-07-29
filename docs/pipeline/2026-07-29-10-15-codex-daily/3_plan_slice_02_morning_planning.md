# Codex Daily — Slice 02 Morning Planning

## Implementation Status

Status: implemented
Commit: `Slice 02: Morning Planning` (this status-bearing commit)
Verification: `npm run check` passed with 5 files/18 tests; Playwright passed the complete planning lifecycle plus dashboard regression (5 passed, 1 intentional duplicate mobile-flow skip); restart/schema smoke proved persistence and planning-only tables; repository contracts passed 4/4; protected-path diff was empty.
Deviations: Browser/loopback verification and clean install required sandbox escalation. The mutating lifecycle runs once on desktop while the dashboard regression remains desktop/mobile. `npm ci` reported seven dependency advisories; dependency remediation was not expanded into this slice.
Follow-ups: None. FUP-001 through FUP-006 remain deferred.

## Implementation Context

- Repository: `/home/syncrobot/buddy`
- Branch during planning: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder:
  `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Selected vertical slice: **02 — Morning Planning**
- Sequence number: `02`
- Dependency: Slice 01 — Daily Dashboard must be approved and implemented before
  this slice starts.
- Source documents:
  - `1_design.md`
  - `2_alignment.md`
  - `3_plan.md`
  - `CURRENT.md`
  - `docs/about/05_ux_decision_catalogue.md`
  - the approved Slice 01 plan and its implementation result

Implement the smallest durable morning loop through the local service and
dashboard:

1. load the operator's local day;
2. resolve every unfinished task from the immediately previous local date with an
   explicit carry-forward, reschedule, or close decision;
3. create, edit, clarify, and order today's outcomes; and
4. let only an explicit operator action confirm or reopen completion.

This slice replaces Slice 01's representative data only for the morning-review and
today-outcomes surfaces. Other Slice 01 representative surfaces remain in place
until their owning slices.

## Repository Rules

- Consulted: root `README.md`, `1_design.md`, `2_alignment.md`, `3_plan.md`,
  `CURRENT.md`, and `docs/about/05_ux_decision_catalogue.md`.
  `docs/rules/README.md` and a root `AGENTS.md` do not exist. The only discovered
  `AGENTS.md` files are inside ignored third-party runtime sources and do not
  govern this application.
- Constraints applied: keep Codex Daily in the bounded TypeScript local-web
  application established by Slice 01; use Node 24's `node:sqlite` for local
  persistence; preserve the existing ROS 2 packages, build, launch, and test
  behavior; store daily product state but no copied Codex transcripts; use the
  configured local timezone with `Europe/Berlin` as the default; never infer
  task completion or carry work automatically.
- Rule updates: None

## Exact Scope

Deliver one working path from SQLite-backed planning state to the Today UI:

- a migration-backed store for days, daily tasks, and prior-day review decisions;
- a planning repository/service with transactions and explicit domain validation;
- local HTTP endpoints used by the browser, with typed request/response contracts;
- a prior-day review gate showing exactly the three aligned decisions;
- a durable today-outcomes editor with add, edit/clarify, reorder, confirm-complete,
  and reopen behavior;
- deterministic local-date handling and injectable clock/database configuration;
  and
- server, storage, UI, and browser-flow tests proving persistence and the absence
  of automatic carry-forward or completion.

The implementation remains single-user and local. It does not add authentication.

## Explicit Non-Goals

- Codex App Server connection, thread discovery, live events, or connection
  health; these belong to Slice 03.
- Task-to-thread links or suggested links; these belong to Slice 03.
- Completion suggestions from observed Codex activity. This slice supports only
  operator-confirmed completion.
- Attention derivation, acknowledgement, or dismissal; these belong to Slice 04.
- Evening factual digests, intelligent narrative, report history, scheduling, or
  missed-run recovery; these belong to Slice 05.
- Configurable timezone UI. Use the existing application configuration boundary
  and default to `Europe/Berlin`; later slices may expose the preference.
- Full-transcript persistence, transcript search, a chat-history viewer, or any
  direct read of Codex private session files.
- Automatic completion, automatic carry-forward, bulk carry-all, or a default
  rollover choice.
- Automatic creation or mutation of Codex chats, approvals, prompts, archives, or
  other Codex state.
- Weekly review, team accounts, cloud sync, third-party integrations, cost/limit
  analysis, or repository-aware completion evidence.
- General privacy/history deletion controls beyond keeping the local database
  inspectable and its path explicit; complete controls belong to Slice 06.
- Redesigning Slice 01's theme, navigation, attention-first dashboard order, or
  representative states outside the morning-planning surface.

## Follow-Up Scope

- Included follow-up items: none.
- Still deferred:
  - `FUP-001` — evidence-backed completion.
  - `FUP-002` — weekly review.
  - `FUP-003` — third-party integrations.
  - `FUP-004` — multi-device sync.
  - `FUP-005` — cost and limit insights.
  - `FUP-006` — proactive chat control.
- Do not use a future observer, Git evidence, or generated text to expand this
  slice's completion semantics.

## Central Issue Scope

- Included register issues: none.
- Still deferred register issues: none identified.
- Newly created register issues: none.
- `docs/issues/README.md` and `docs/issues/register.md` do not exist. Do not create
  either merely to record this feature plan. If implementation uncovers durable
  architecture debt or a verification gap outside this contract, stop and report
  it for separate triage instead of absorbing it into this slice.

## Canonical Mental Model

The day owns the operator's intent. A task belongs to exactly one local calendar
day. Future chats may provide evidence for a task, but they do not own it and
cannot complete it.

Use these canonical planning concepts:

- **Day:** a row keyed by ISO local date (`YYYY-MM-DD`), not a UTC 24-hour bucket.
- **Task:** an outcome attached to one day, with operator-authored title,
  optional clarification, explicit ordering, and lifecycle state.
- **Task lifecycle:** `open`, `confirmed_complete`, or `closed`. Only a direct
  operator request may enter `confirmed_complete`; reopening returns it to
  `open`. `closed` means intentionally ended without claiming completion.
- **Review decision:** one durable disposition for an open task from the
  immediately previous date:
  - `carry_forward` creates a new open task for today;
  - `reschedule` creates a new open task for a specified later date; or
  - `close` closes the source task without creating a successor.
- **Task lineage:** carry-forward and reschedule create a new task referencing the
  source. They never move the source row to a different day or rewrite its
  historical title.
- **Unresolved prior task:** an `open` task on the immediately previous local date
  that has neither a review decision nor operator-confirmed completion.

The review decision and any successor creation are one database transaction.
There is at most one decision per source task. A safe retry of the same decision
must not create a second successor; a conflicting second decision must be
rejected rather than silently replacing history.

### Required Cleanup And Removal

- Remove Slice 01's in-memory/fixture-backed behavior from the prior-day review
  and today's-outcomes surfaces once the real planning query is wired.
- Keep representative data for Needs You, active chats, recent completions, and
  report preview; those surfaces are not owned by this slice.
- Remove any Slice 01 button handlers that pretend to save, complete, carry,
  reschedule, or close without reaching the service.
- Do not leave a second browser-local planning store, `localStorage` fallback,
  mock API branch, or dual schema alongside SQLite.
- Rename generic UI concepts such as “chat task” or “completed turn” if they were
  introduced in Slice 01; the canonical label is a daily outcome/task and
  completion is operator-confirmed.
- Do not add compatibility aliases for superseded fixture fields. Update the
  planning components and their tests to one typed server contract.
- Do not delete or rewrite unrelated Slice 01 dashboard fixtures or existing ROS
  code.

## Storage Contract

This slice owns the initial persistence boundary. Add a minimal append-only
numbered migration runner that records applied versions and applies each
migration once inside a transaction, then add migration `001` for morning
planning. Slice 01 intentionally establishes no persistence.

The schema should represent, at minimum:

- `days`
  - stable ID;
  - unique `local_date`;
  - created and updated timestamps.
- `tasks`
  - stable ID;
  - owning day ID;
  - non-empty title;
  - optional clarification;
  - integer sort position unique enough to produce deterministic ordering within
    a day;
  - lifecycle constrained to `open`, `confirmed_complete`, or `closed`;
  - optional immediate `origin_task_id` for carry/reschedule lineage;
  - created, updated, and completion/closure timestamps as appropriate.
- `task_review_decisions`
  - stable ID;
  - unique source task ID;
  - action constrained to `carry_forward`, `reschedule`, or `close`;
  - target local date and successor task ID only when the action creates a
    successor;
  - decision timestamp.

Enable and test foreign keys. Keep IDs opaque (for example,
`crypto.randomUUID()`), keep date strings separate from UTC timestamps, and make
the database path configurable so tests can use isolated temporary databases.
The development default must live in an ignored, visibly named application data
directory. Do not add transcript, prompt, response, or raw Codex item columns.

The service, not the UI, enforces:

- valid ISO local dates;
- non-blank bounded task text;
- valid lifecycle transitions;
- review-before-planning for a day with unresolved prior work;
- a reschedule target later than today;
- exactly one decision per source task;
- atomic decision and successor creation; and
- stable task ordering after create, reorder, carry, and reschedule.

## HTTP And UI Contract

Follow the transport and error-envelope pattern established by Slice 01. Keep
SQLite rows private to the server and return explicit DTOs. The route names may
match Slice 01's established prefix, but the implemented API must provide these
operations as one coherent planning resource:

- load the planning view for an ISO local date, including today's ordered tasks
  and unresolved prior-day review items;
- create, edit, and reorder a task for a day;
- explicitly confirm completion and reopen a task;
- apply one prior-day review decision with an optional reschedule date; and
- return validation/conflict/not-found errors that the UI can explain without
  discarding the current form.

The planning-view response should expose whether review is required. Do not rely
on hiding controls alone: task creation for today must be rejected by the service
while unresolved previous-day items remain.

The dashboard flow must:

1. show the prior-day review before today's outcome editor when review is
   required;
2. show each unresolved task's historical date and exactly three choices:
   **Carry forward**, **Reschedule**, and **Close**;
3. require a future date before submitting Reschedule;
4. apply decisions individually with a visible pending/error state;
5. reveal today's editor only after all required decisions are resolved;
6. show carried tasks in today's ordered list and rescheduled tasks only on their
   selected date;
7. support adding, editing/clarifying, and keyboard-accessible reordering of
   outcomes;
8. label completion as an operator confirmation, not an observed or inferred
   result; and
9. allow the operator to reopen an accidentally confirmed task.

Use accessible form labels, native buttons, visible focus, and a status/error
region. Do not require drag-and-drop as the only reordering mechanism.

## Likely Files, Modules, Components, And Commands

Slice 01 is expected to establish a bounded TypeScript application at
`apps/codex-daily/`. Extend its actual module names rather than creating a parallel app.
If Slice 01 establishes a different root or incompatible architecture, stop and
reconcile the plan before coding.

Likely files to add:

- `apps/codex-daily/src/server/storage/migrations/001_morning_planning.sql` — planning
  schema; use the next available number if Slice 01 already owns `001`.
- `apps/codex-daily/src/server/storage/database.ts` — database open/configuration,
  foreign keys, migration entry point, and test injection, if not already
  established.
- `apps/codex-daily/src/server/storage/planning-repository.ts` — SQL queries and
  transaction primitives.
- `apps/codex-daily/src/server/planning/types.ts` — lifecycle, decision, and request/
  response contracts shared at the service boundary.
- `apps/codex-daily/src/server/planning/planning-service.ts` — date, transition,
  review-gate, retry, and ordering rules.
- `apps/codex-daily/src/server/planning/planning-routes.ts` — local HTTP transport.
- `apps/codex-daily/src/client/api/planning.ts` — typed browser API calls.
- `apps/codex-daily/src/client/features/planning/PriorDayReview.tsx` or Slice 01's
  framework-equivalent component.
- `apps/codex-daily/src/client/features/planning/TodayOutcomes.tsx` or the established
  equivalent.
- `apps/codex-daily/src/client/features/planning/OutcomeEditor.tsx` or the established
  equivalent.
- `apps/codex-daily/test/server/planning-repository.test.ts`
- `apps/codex-daily/test/server/planning-service.test.ts`
- `apps/codex-daily/test/server/planning-routes.test.ts`
- `apps/codex-daily/test/client/morning-planning.test.tsx` or the established browser
  component-test equivalent.
- `apps/codex-daily/test/e2e/morning-planning.spec.ts` if Slice 01 establishes browser
  automation.

Likely files to modify:

- `apps/codex-daily/src/server/app.ts` — compose the planning service and routes.
- `apps/codex-daily/src/client/App.tsx` and/or Slice 01's Today/dashboard composition —
  replace only the planning fixtures.
- `apps/codex-daily/src/client/styles.css` or feature-local styles — review gate,
  forms, ordering, and responsive/error states using Slice 01 tokens.
- `apps/codex-daily/package.json` — only for missing planning test scripts or a
  necessary package already consistent with Slice 01; SQLite itself must use
  built-in `node:sqlite`.
- `apps/codex-daily/.gitignore` — ignore the explicit Codex Daily runtime database
  files and SQLite sidecars without widening the root repository ignore policy.

Expected working-directory commands:

```bash
cd /home/syncrobot/buddy/apps/codex-daily
npm ci
npm run typecheck
npm test
npm run build
npm run test:e2e
```

If Slice 01 uses a single `npm run check` or a different established test script,
retain that canonical script and document the exact equivalent in the final
summary. Do not introduce a second package manager or a nested lockfile.

## Existing Patterns To Follow

- Preserve Slice 01's application root, package manager, TypeScript settings,
  server composition, HTTP error shape, client rendering approach, visual tokens,
  responsive layout, test runner, and browser-test harness.
- Keep domain validation in a framework-independent service so it is directly
  testable with an injected clock and isolated database.
- Keep SQL in the storage boundary; UI components do not know table names or
  SQLite semantics.
- Use deterministic fixtures and temporary databases in tests. Do not share the
  development database across tests.
- Follow the repository's broader pattern of small core modules with focused unit
  tests and explicit boundary tests, as seen in the existing Buddy packages.
- Keep generated/runtime files out of Git, as the root already does for ROS build,
  install, log, and runtime assets.

## Behavior That Must Not Regress

- Slice 01's primary order remains: Needs You, today's outcomes, active chats,
  recently completed work, evening-report preview.
- Slice 01's navigation, responsive layout, calm dark visual treatment, secondary
  views, and visible status semantics remain usable.
- Planning remains available without Codex connectivity; this slice must not add a
  Codex dependency.
- Representative non-planning surfaces remain stable until their owning slices.
- A task is not automatically completed by time, UI reload, or fixture activity.
- No task moves to another date without a recorded operator decision.
- Historical source tasks retain their original day and text.
- The database contains no full transcripts or credentials.
- No API mutates a Codex chat or ordinary thread.
- No files under `buddy_*`, ROS contracts, or existing launch/config paths change.

## Acceptance Criteria

1. Starting with an empty database on a local date creates or loads an empty
   planning view without requiring a chat.
2. The operator can add a non-blank outcome, add or edit its clarification, change
   its order, reload the application/server, and see the same ordered values.
3. Only an explicit operator command changes an `open` task to
   `confirmed_complete`; the operator can reopen it. No load, elapsed-time, or
   fixture path confirms it.
4. When the immediately previous local date has unresolved open tasks, the Today
   UI shows the review gate before task creation and the server rejects bypassed
   create requests until all review items have decisions.
5. Every review item displays exactly Carry forward, Reschedule, and Close. No
   choice is preselected or applied automatically.
6. Carry forward atomically records the decision and creates one new open task for
   today with source lineage. The source remains attached to its historical day.
7. Reschedule requires a date later than today, atomically records the decision,
   and creates one new open task on that date with source lineage. It does not
   appear in today's list.
8. Close records the decision, changes the source to `closed`, creates no successor,
   and never presents the item as completed.
9. Repeating the same successful decision does not create a duplicate successor;
   attempting a different decision for the same source returns a conflict.
10. After the final prior-day item is resolved, today's editor appears and accepts
    new outcomes.
11. The local date and prior-date calculation are deterministic for an injected
    clock and correctly use `Europe/Berlin` by default across at least one UTC
    date-boundary test.
12. Validation, not-found, persistence, and conflict failures produce an
    understandable inline/status message and preserve unsaved form input where
    practical.
13. Database schema and persistence tests demonstrate foreign-key enforcement,
    migration idempotence, isolated configurable database paths, and absence of
    transcript/prompt/response storage.
14. Automated UI or browser coverage proves the full review-to-plan flow and
    operator-only completion behavior.
15. `npm run typecheck`, `npm test`, `npm run build`, and the established browser
    test command pass from a clean dependency install.
16. The implementation changes no ROS package behavior and introduces no writes to
    Codex.

## Ordered Implementation Tasks

1. **Reconcile with Slice 01.** Inspect its implementation-status block, final
   summary, app root, package scripts, server/client boundary, fixture ownership,
   and tests. Confirm it is implemented and verified. Map the likely paths above
   to its canonical equivalents; do not create competing roots or conventions.
2. **Lock behavior with failing tests.** Add focused service/repository tests for
   date boundaries, persistence, ordering, lifecycle transitions, the review gate,
   each decision, transaction rollback, idempotent retry, and conflicting retry.
   Add a UI/browser test for the complete prior-day-review-to-today-plan flow.
3. **Add the migration and database boundary.** Create the minimal schema,
   constraints, indexes, migration tracking if needed, foreign-key configuration,
   configurable path, and temporary-test database helper. Add a narrowly scoped
   ignore rule for local SQLite files.
4. **Implement the planning repository.** Add prepared queries for day lookup/
   creation, ordered task CRUD, prior-day unresolved lookup, lifecycle updates,
   and transactional review decisions with successor lineage.
5. **Implement domain/date rules.** Add an injected clock and timezone-aware local
   date helper, request validation, review-before-create enforcement, transition
   rules, stable ordering, and retry/conflict behavior in the planning service.
6. **Expose the local planning API.** Add typed DTO mapping and route handlers using
   Slice 01's local-only transport and error envelope. Verify malformed,
   not-found, and conflict responses.
7. **Replace only planning fixtures in the UI.** Wire the planning-view load,
   prior-day gate, exact three review actions, reschedule-date validation, outcome
   editor, ordering controls, explicit completion, reopening, pending states, and
   error/status feedback.
8. **Remove superseded planning paths.** Delete unused planning fixture fields,
   fake mutation handlers, browser-local storage/fallbacks, and duplicate types.
   Confirm non-planning fixtures remain owned by later slices.
9. **Verify persistence and product boundaries.** Run the targeted and full Node
   suites, production build, browser flow, database inspection, diff checks, and
   ROS-boundary check below. Record the exact commands and results in the
   implementation-status block and final summary.

## Verification And Expected Outcomes

Run from a fresh install:

```bash
cd /home/syncrobot/buddy/apps/codex-daily
npm ci
```

Expected: the existing lockfile installs reproducibly with no second package
manager or unexpected lockfile change.

```bash
npm run typecheck
```

Expected: server, shared planning contracts, client, and tests type-check with no
errors.

```bash
npm test
```

Expected: all Slice 01 tests plus new storage/service/route/UI tests pass. Coverage
must include migration idempotence, restart persistence, review gating, three
decision paths, same-decision retry, conflicting retry, completion/reopen, stable
ordering, invalid requests, and Europe/Berlin local-date boundaries.

```bash
npm run build
```

Expected: the production client and local service compile successfully, with no
runtime database or test fixture included as a shipped source asset.

```bash
npm run test:e2e
```

Expected: using an isolated temporary database, the browser first resolves prior
work, then creates/edits/reorders today's outcomes, explicitly confirms and
reopens one task, reloads, and observes durable state. The flow must also prove
that no default carry or completion occurred. If Slice 01 names this script
differently, run its exact canonical equivalent.

Perform one manual persistence/inspection smoke using Slice 01's start command and
an explicitly temporary database path:

```bash
CODEX_DAILY_DB_PATH=/tmp/codex-daily-slice-02.sqlite npm run dev
```

Expected: the app is bound only as Slice 01 specifies for local development;
planning survives a server restart; the database contains planning metadata only;
and every source task remains associated with its original day. Remove the
temporary database and its sidecars after the smoke.

From the repository root:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git status --short
```

Expected:

- no whitespace errors;
- no changed ROS package or frozen-contract paths;
- repository boundary tests pass; and
- status contains only the intended Codex Daily slice files plus any unrelated
  pre-existing user changes, which remain untouched.

## Risks And Mitigations

- **Slice 01 contract drift:** its actual paths or scripts may differ from the
  likely list. Extend its canonical structure and update this plan's implementation
  record; stop if doing so changes the architecture or scope.
- **`node:sqlite` API maturity:** isolate imports and SQL lifecycle inside the
  database/repository boundary. Do not introduce a second database library or an
  ORM without stopping for approval.
- **Partial rollover writes:** use one SQLite transaction for the decision, source
  transition when applicable, successor creation, and ordering. Test rollback.
- **Duplicate successors after retries:** enforce a unique source decision and
  check the existing decision before creating a successor.
- **Historical mutation:** successor tasks are new rows with lineage; never move or
  rewrite the source task.
- **Timezone bugs:** derive local dates in one injected helper and test around UTC
  midnight and a Europe/Berlin offset boundary. Do not scatter `new Date()` across
  repository/UI code.
- **UI-only gate bypass:** enforce review-before-create in the service as well as
  the UI.
- **Scope leak into observer/reporting:** keep thread IDs, transcript content,
  generated completion, and report fields out of this migration.
- **Concurrent writes:** the first release is one local operator, but conflicting
  or repeated requests still need deterministic transactions and HTTP conflicts.
- **Native database test leakage:** every automated test uses a fresh temporary or
  in-memory database and closes it reliably.

## Dependencies

- Approved and implemented Slice 01 with a runnable bounded TypeScript local web
  app, its package lock, visual shell, transport boundary, and test harness.
- Node 24, whose built-in `node:sqlite` is the approved storage mechanism.
- Existing npm dependencies and browser harness selected by Slice 01.
- No Codex App Server, network service, ROS runtime, external database, plugin, or
  third-party integration is required for this slice.

## Stop Conditions And Blocked Handling

Stop implementation and report back before broadening scope when:

- Slice 01 is not implemented/verified or its architecture contradicts this plan.
- The application cannot use Node 24 or `node:sqlite` in the target environment.
- Durable planning would require modifying existing ROS packages, launch files, or
  frozen contracts.
- A correct rollover transaction requires a broad storage framework or a second
  database implementation.
- The aligned previous-day, reschedule, completion, or historical-lineage semantics
  conflict with existing implemented behavior.
- Tests cannot isolate the database, cannot inject local time, or cannot run the
  established browser flow.
- Implementation would require full transcript storage, Codex control, automatic
  completion/carry-forward, authentication, cloud services, or any deferred
  `FUP-###` item.
- Unrelated user changes overlap the exact files this slice needs and cannot be
  preserved safely.
- The slice grows beyond one durable morning-planning vertical path.

When blocked, preserve the failing test or minimal reproduction where safe, record
the exact command/output and conflicting files or contract, leave the status as
`blocked`, and request a design/planning decision. Do not add compatibility
fallbacks or silently omit an acceptance criterion.

## Preserve Unrelated Changes

The planning worktree was already dirty: `docs/about/` and `docs/pipeline/` were
untracked on `main`. Treat all pre-existing and concurrent changes as user-owned.
Before each edit and before commit:

- inspect `git status --short` and the diff for every file to be touched;
- edit only the bounded `apps/codex-daily/` files, narrow `.gitignore` entry, and this
  slice's implementation-status block required by the plan;
- do not reset, clean, stash, overwrite, reformat, or commit unrelated paths;
- do not replace concurrent edits made by other planning or implementation work;
  and
- stop if an overlapping change cannot be incorporated without losing intent.

## Expected Final Summary

The implementing agent's final response must include:

- outcome: whether Slice 02 is `implemented` or `blocked`;
- commit hash and branch, if committed;
- concise behavior delivered: durable days/tasks, review gate, each review choice,
  operator-confirmed completion/reopen, and persistence;
- schema/migration and canonical API/component paths actually used;
- representative-data handlers or other superseded planning code removed;
- verification commands with pass/fail results, including typecheck, unit/
  integration tests, build, browser flow, database inspection, and ROS boundary
  check;
- any deviations from this plan and why;
- remaining risks or follow-ups, referencing `FUP-###` or issue IDs where
  applicable;
- confirmation that unrelated changes were preserved; and
- the next implementation source: approved Slice 03, not `3_plan.md`.
