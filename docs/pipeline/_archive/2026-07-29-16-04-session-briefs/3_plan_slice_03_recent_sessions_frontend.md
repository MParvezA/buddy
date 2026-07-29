# Codex Daily — Slice 03 Recent Sessions Frontend Plan

Archived after completed implementation review and cleanup.

## Implementation Status

Status: implemented
Commit: `Slice 03: Recent Sessions Frontend` (this status-bearing commit)
Verification: `npm run check` passed with 41 files/152 tests; full Playwright passed 20 runnable flows with 8 intentional mobile mutation skips; focused frontend coverage passed 8/8; repository contracts passed 4/4; protected-path and whitespace checks were clean. Browser proof covers exact newest-10 selection from 11 sessions, queued-to-ready live updates, refresh/retry, task linking, thread navigation, stale/offline/failure states, keyboard focus retention, and no horizontal overflow at 390×844.
Deviations: Playwright required host-context execution after the sandboxed `tsx` IPC socket failed with `EPERM`. One test fixture was made independent after a prior privacy-deletion flow removed shared planning/link data; product behavior was unchanged.
Follow-ups: None. `FUP-001` through `FUP-005` remain deferred.

## Context And Selected Slice

- Repository: `/home/syncrobot/buddy`
- Planning branch target: `dev`
- Recommended implementation branch:
  `feature/2026-07-29-16-04-session-briefs`
- Feature folder:
  `docs/pipeline/2026-07-29-16-04-session-briefs/`
- Selected vertical slice: `03 — Recent Sessions Frontend`
- Sequence number: `03`
- Depends on: implemented and verified Slices 01–02
- Source docs: `1_design.md`, `2_alignment.md`, `3_plan.md`, `CURRENT.md`,
  the approved Slice 01 and Slice 02 implementation plans/results, and
  `docs/about/05_ux_decision_catalogue.md`
- Baseline implementation: reviewed Codex Daily application ending at `f255d46`

Replace Priority 03's metadata-only, runtime-first 20-card list with the one
canonical **Recent session briefs** surface. It must present the newest 10
eligible ordinary sessions in literal recency order, keep each card useful from
factual observer metadata before or without generation, and progressively add
the structured GPT-5.6 result and lifecycle delivered by Slices 01–02.

This slice owns browser data access, state presentation, interaction feedback,
responsive layout, accessibility, and frontend/browser regression coverage. It
does not own session selection, source revision calculation, scheduling,
transcript reads, model execution, retry policy, or persistence.

## Repository Rules

- Consulted: the feature design, alignment, roadmap, and current routing; the UX
  decision catalogue; archived Codex Daily Slice 01, Slice 03, Slice 04, and
  Slice 06 implementation plans; current dashboard, observer/attention/planning/
  report providers, client API modules, component tests, Playwright fixtures,
  and responsive styles. No root `AGENTS.md` or `docs/rules/README.md` exists.
- Constraints applied: preserve the bounded Node 24/npm 11 Fastify + React/Vite
  package under `apps/codex-daily/`; preserve the attention-first Today
  hierarchy, human-confirmed completion, minimal local retention, facts before
  generated interpretation, loopback-only security, read-only ordinary chats,
  and protected Buddy ROS paths.
- Rule updates: None

## Exact Scope

- Add a dedicated browser API adapter and provider for the session-brief read
  snapshot, SSE updates, refresh-all mutation, and per-session retry mutation
  established by Slice 01.
- Merge the server-selected brief rows with factual observer thread metadata
  without putting brief state into the observer, attention, planning, or report
  providers.
- Render at most 10 cards in server-owned literal recency order. With 10 or more
  eligible sessions the surface renders exactly 10; with fewer, it renders every
  eligible session and truthfully explains the smaller available count.
- Keep factual title, source, working directory, runtime state, recency,
  thread-detail link, unplanned marker, and outcome-link controls on each card.
- Render structured derived fields under the exact headings **Going on**,
  **Chat-reported done**, **What you should do**, and **Blockers**.
- Display explicit derived provenance, confidence, generation time, source
  freshness, and lifecycle labels.
- Stream queued/analyzing/ready/stale/unavailable/failed progress into the
  mounted Today view without a full-page reload.
- Add one **Refresh 10 briefs** control, aggregate progress feedback, and one
  retry control on each eligible failed/unavailable card.
- Preserve the separate Priority 04 recently-completed factual turn list.
- Add component and browser proof for normal, loading, live progress, stale,
  offline, failed, retry, refresh-all, keyboard, and 390px behavior.

## Explicit Non-Goals

- Implementing or changing the brief schema, migration, repository, coordinator,
  scheduler, prompt builder, transient transcript reader, GPT-5.6 gateway,
  structured-output validation, retry timing, or shutdown recovery.
- Re-sorting recent sessions by runtime, attention, brief lifecycle, confidence,
  task links, or generated content.
- Selecting more than 10 sessions, adding pagination, infinite scroll, filters,
  user-configurable count, or a second sessions page.
- Fetching transcripts or calling GPT from the browser.
- Persisting brief or transcript data in localStorage, IndexedDB, service-worker
  caches, browser logs, analytics, diagnostics, or another client-owned store.
- Turning suggested actions into Needs You items or morning outcomes; marking
  any outcome complete; sending prompts, approvals, answers, retries, or other
  mutations to an ordinary source chat.
- Folding briefs into daily-report narratives or replacing Priority 04's
  factual completed-turn feed.
- Redesigning navigation, planning, Needs You, reports, settings, thread detail,
  app-wide visual tokens, or unrelated mobile layouts.
- Pulling in weekly synthesis, external notifications, repository/test
  verification of chat claims, or configurable analysis depth.

## Follow-Up Scope

- Included `FUP-###` items: none.
- Still deferred:
  - `FUP-001` user-tunable session count;
  - `FUP-002` per-session analysis depth;
  - `FUP-003` weekly cross-session synthesis;
  - `FUP-004` external notifications; and
  - `FUP-005` automatic ordinary-chat actions.
- Do not add disabled, hidden, or placeholder controls for any deferred item.

## Central Issue Scope

- Included register IDs: none.
- Still deferred register IDs: none identified.
- Newly created register IDs: none.
- No `docs/issues/register.md` exists. If implementation exposes a durable
  cross-slice contract defect, stop and report it rather than creating a
  frontend compatibility branch.

## Canonical Mental Model And Required Cleanup

A recent-session card is one factual observed session plus, when available, one
structured model-derived brief for the same source revision. The factual shell
is authoritative observer metadata. The brief is an orientation aid, not the
chat, an attention item, a morning outcome, a daily report, or proof that work
is complete.

The Priority 03 ordering is literal:

1. exclude archived, reporting, analysis, subagent, child, and locally excluded
   sessions on the server as established by Slices 01–02;
2. order the eligible top-level sessions by `recencyAt`, falling back to
   `updatedAt`, newest first; and
3. expose only the first 10.

The client must preserve the selected order in the session-brief snapshot. It
must not repeat the current `runtime === "active"` sort or independently expand
the set from the observer's larger inventory. If an SSE update changes the
window, reconcile by stable `threadId` keys so retained cards update in place,
new cards enter in their canonical position, and cards leaving the window
disappear without stale duplicates.

Required removals and renames:

- Rename the visible Priority 03 heading from **Active and recent Codex chats**
  to **Recent session briefs**.
- Remove the `active first` comparator, `.slice(0, 20)`, `20 most relevant`
  wording, and the `observedThreads.length` count as the Priority 03 selection
  policy.
- Remove tests and selectors that encode the old heading, `.work-card`
  runtime-first semantics, or a 20-card cap.
- Do not retain a second metadata-only recent-chat list or an adjacent AI
  summaries panel.
- Keep one reusable session-card implementation and one session-brief provider;
  do not place brief fetch/SSE/mutation state inside individual cards.
- Extract or rename Priority 04's factual completed-work rendering if necessary
  so deleting the old list does not delete or duplicate that section.
- Preserve thread-detail navigation and task-link behavior on the canonical new
  card; do not add a legacy adapter that renders the old and new cards
  conditionally.

## Frontend Data And Interaction Contract

### Provider and API ownership

Follow Slice 01's exact `src/shared/session-briefs.ts` contract:

- `SessionBriefAnalysisStatus`: `queued | analyzing | ready | unavailable |
  failed`;
- `SessionBriefFreshness`: `missing | current | stale`;
- `SessionBriefContent`: `currentState`, `done`, `operatorActions`, `blockers`,
  `confidence`, and `evidence`;
- ordered `SessionBriefItem`: `threadId`, `targetUpdatedAt`, `analysisStatus`,
  `freshness`, nullable `lastGood` (content, `sourceUpdatedAt`, `generatedAt`,
  `modelId`, and `generator`), safe nullable `failure`, and lifecycle
  timestamps; and
- `SessionBriefSnapshot`: observer connection/capability, `selectedAt`, at most
  10 ordered items, and aggregate progress counts.

The exact route surface is:

- `GET /api/session-briefs`;
- `GET /api/session-briefs/events`, event name `session-briefs`;
- `POST /api/session-briefs/refresh`; and
- `POST /api/session-briefs/:threadId/refresh`.

Both mutations return the canonical snapshot with HTTP 202 and are
server-idempotent. The per-session endpoint backs the UI's retry wording; do not
invent a `/retry` alias. Slice 01's temporary
`generator: "deterministic_placeholder"`/`modelId: null` compatibility path must
have been removed by Slice 02 before this slice starts. Slice 03 renders only
the canonical GPT result and must stop if placeholder results remain reachable.

Add a `SessionBriefProvider` beside the existing observer, attention, planning,
and report providers. It owns:

- last authoritative session-brief snapshot;
- initial-load state distinct from live-stream degradation;
- a safe read/SSE error while preserving the last snapshot;
- refresh-all pending state;
- per-thread retry pending state;
- the current EventSource lifecycle and reconnect cleanup; and
- mutation methods that consume and atomically install the returned canonical
  snapshot when the server returns one.

Open SSE only after the initial read succeeds, follow the observer/attention
provider cleanup pattern, parse only the typed session-brief event, preserve the
last snapshot on malformed events or stream loss, and close EventSource on
unmount. Do not use polling as a silent second source of truth unless Slice 01's
approved contract explicitly requires it.

Provider mutation rules:

- **Refresh 10 briefs** invokes the single refresh-all endpoint once, remains
  disabled while its request is pending or the snapshot says Codex cannot
  accept analysis work, and relies on server idempotency, concurrency, and queue
  ownership. It does not reproduce the 30-second automatic debounce; the server
  owns immediate front-of-queue manual semantics while respecting the two-worker
  limit.
- Per-session retry invokes only the thread-scoped refresh endpoint and disables
  only that card's retry while pending; when Codex is disconnected, keep the
  control visible but disabled with adjacent explanatory copy. When enabled, the
  server owns immediate front-of-queue retry and its two-attempt transient retry
  policy; the browser starts no timers.
- A mutation failure shows the server's safe message without erasing the last
  snapshot or last good brief.
- Successful mutation feedback reflects the returned/SSE lifecycle; the client
  must not optimistically claim analysis started, finished, or succeeded.
- The initiating button remains mounted and retains keyboard focus after the
  mutation response and subsequent SSE updates.

### Factual card shell

Every selected row must retain, from the canonical server row or its observer
join:

- title with a real link to `/threads/:threadId`;
- source and working directory;
- runtime status and last activity/recency time in the planning timezone;
- task-thread link chips, unlink actions, and outcome-link form;
- `Unplanned work` only when the session has no explicit outcome link; and
- factual metadata even when brief loading, generation, or connectivity fails.

The session-brief provider must not replace `ObserverProvider`. Task link
mutations continue through the existing observer contract and update cards from
the observer snapshot. No brief mutation may alter those links.

### Derived sections and labels

A last-good brief renders four consistently ordered blocks:

1. **Going on** — `currentState`;
2. **Chat-reported done** — zero to five items;
3. **What you should do** — zero to five imperative suggestions; and
4. **Blockers** — zero to five items.

For an empty list render the aligned non-authoritative copy:
`No completed work inferred`, `No action inferred`, or `No blocker inferred`.
Do not say `None`, `Complete`, `No action required`, or other authoritative
claims. A missing current-state paragraph is a contract error and must use the
truthful failure state rather than fabricated prose.

Alongside the blocks, show text labels for:

- `GPT-5.6 derived`;
- confidence: `High confidence`, `Medium confidence`, or `Low confidence`;
- generation time;
- freshness: `Current` or `Stale`; and
- lifecycle/progress: queued, analyzing, ready, unavailable, or failed as
  supplied by the server.

Evidence labels are bounded provenance hints, not transcript quotes. Present
them compactly under the derived result when Slice 01's DTO includes them; do
not turn them into excerpts, links, tool payloads, or hidden accessible raw
content. Status must use visible text and may additionally use the existing
`StatusBadge`; color alone is insufficient.

### Truthful lifecycle states

- **Initial loading:** render a stable section and up to 10 non-animated
  skeleton/status card shells only if the snapshot supplies selected rows;
  otherwise show one `Loading recent session briefs…` status. Do not hide
  already loaded factual observer metadata behind a full-panel spinner.
- **Queued:** show factual metadata and `Queued for GPT-5.6 analysis`.
- **Analyzing:** show factual metadata and `GPT-5.6 analysis in progress`.
- **Ready/current:** render all structured blocks and current/fresh labels.
- **Stale with refresh pending:** retain and visibly label the last good brief
  as stale, show the current queued/analyzing lifecycle separately, and never
  dim or replace it with an empty skeleton.
- **Failed with last good:** retain the stale brief, show the safe failure
  category/message, and offer per-session retry.
- **Failed without last good:** keep factual metadata, show that no generated
  brief is available, and offer per-session retry.
- **Unavailable/offline:** retain any last good brief and explain that refresh is
  unavailable while factual metadata remains visible. A disconnected global
  observer must not make planning, Needs You, factual completed work, or reports
  look failed.
- **SSE interrupted:** retain the snapshot and show `Live brief updates paused`
  separately from per-session generation failure.
- **No eligible sessions:** show a single factual empty state and no fake cards
  or refresh work.

If Slice 02 supplies more specific safe failure categories, display a concise
operator-facing mapping while keeping the exact category available only where
the shared DTO intends it. Never render raw model output, prompt text, transcript
content, protocol envelopes, stack traces, or credential-shaped values.

### Aggregate progress and accessibility

The section header contains:

- eyebrow `Priority 03`;
- heading `Recent session briefs`;
- a count such as `10 recent` or `4 available`;
- **Refresh 10 briefs**; and
- a polite live progress summary derived from the snapshot, for example
  `2 analyzing · 3 queued · 4 ready · 1 failed`.

Use Slice 01's aggregate progress from the current recent window; do not keep a
second client counter. Include queued, analyzing, ready, failed, and unavailable
analysis counts and stale freshness when nonzero so the header reconciles to the
visible cards.

Use a single stable `aria-live="polite"`/`role="status"` progress node so SSE
updates do not repeatedly announce every card. Mutation failures may use
`role="alert"`. Every retry control has an accessible name containing its
session title, for example `Retry brief for Onboarding refresh`. Native buttons,
links, headings, lists, and list items remain the interaction structure; no
clickable `div` or hover-only action is acceptable.

Keyboard proof must cover tabbing to **Refresh 10 briefs**, activating it with
the keyboard, retaining focus through pending/SSE updates, reaching a
per-session retry, and then following a thread link. Disabled controls must
explain their state in adjacent visible copy rather than only a tooltip.

### Responsive layout

At desktop width, use the existing two-column dashboard rhythm only if the four
brief blocks remain readable. At `<=900px`, use one card per row. At exactly
390px:

- no document or body horizontal overflow;
- section controls wrap vertically without truncating their labels;
- title, cwd, source, timestamps, evidence, and failure copy wrap safely;
- the four derived blocks use one column;
- task-link select/actions fit or wrap without clipping;
- badges do not become the only status communication; and
- all buttons and links remain visible, reachable, and focusable.

Respect `prefers-reduced-motion`; loading status must not depend on animation.

## Likely Files, Modules, Components, Commands, And Tests

Reconcile these paths with Slices 01–02 and extend their canonical contracts
rather than creating parallel modules.

Likely additions:

- `apps/codex-daily/src/client/api/session-briefs-client.ts`
- `apps/codex-daily/src/client/data/session-briefs-context.tsx`
- `apps/codex-daily/src/client/features/session-briefs/RecentSessionBriefs.tsx`
- `apps/codex-daily/src/client/features/session-briefs/SessionBriefCard.tsx`
- `apps/codex-daily/test/client/features/session-briefs/session-briefs.test.tsx`
- `apps/codex-daily/e2e/session-briefs.spec.ts`

Likely modifications:

- the Slice 01 shared session-brief DTO module
- `apps/codex-daily/src/client/App.tsx`
- `apps/codex-daily/src/client/components/DashboardSections.tsx`
- `apps/codex-daily/src/client/features/live-work/LiveWorkSections.tsx`
- `apps/codex-daily/src/client/components/StatusBadge.tsx`
- `apps/codex-daily/src/client/styles.css`
- `apps/codex-daily/src/client/App.test.tsx`
- `apps/codex-daily/test/client/features/live-work/live-work.test.tsx`
- `apps/codex-daily/e2e/daily-dashboard.spec.ts`
- `apps/codex-daily/e2e/codex-observer.spec.ts`
- `apps/codex-daily/e2e/recovery-privacy.spec.ts` only if its offline assertions
  share the replaced Priority 03 card
- the deterministic e2e server/fake App Server fixture only as needed to expose
  safe structured brief states and deterministic SSE transitions

If `LiveWorkSections.tsx` would retain only Priority 04 after the replacement,
rename or split it to match its factual completed-work responsibility and update
imports/tests. Do not keep a misleading live-work wrapper merely to avoid a
small cleanup.

Commands are the existing package scripts in
`apps/codex-daily/package.json`: `lint`, `typecheck`, `test`, `build`,
`test:e2e`, and `check`. No dependency addition should be necessary.

## Existing Patterns To Follow

- `ObserverProvider` and `AttentionProvider` for an initial authoritative GET,
  dedicated EventSource, content-safe parse failure, retained last snapshot, and
  unmount cleanup.
- `ReportProvider` for explicit pending/error mutation state without hiding the
  last successful result.
- `LiveWorkSections` and `ThreadLinks` for factual thread metadata, runtime
  badges, thread-detail links, task links, and timezone-aware timestamps.
- `NeedsYou` for attention-before-activity hierarchy, capability-aware offline
  copy, honest empty/loading/error states, and local-only action messaging.
- `ReportDigest`/`ReportPreview` for visibly separating factual content from
  generated interpretation and retaining useful facts when generation fails.
- `StatusBadge`, `.panel`, `.section-heading`, `.work-grid`, existing button
  classes, focus-visible rules, and mobile breakpoints rather than a separate
  visual system.
- Testing Library `MemoryRouter` tests with stubbed fetch and user-event for
  semantic assertions, and the existing deterministic Playwright server with
  one mutable desktop flow plus read-only desktop/mobile coverage.
- Existing Playwright overflow measurement using
  `scrollWidth - clientWidth <= 0`.

## Behavior That Must Not Regress

- Dashboard order remains:
  1. Needs your attention;
  2. Today’s outcomes and progress;
  3. Recent session briefs;
  4. Recently completed work; and
  5. Evening report.
- Needs You remains deterministic and first; generated blockers/actions never
  enter it.
- Today's outcome completion remains operator-confirmed. `Chat-reported done`
  cannot confirm, close, reorder, or create a task.
- Planning remains usable while Codex, SSE, or GPT-5.6 is unavailable.
- Priority 04 remains an observer-factual completed-turn feed and never adopts
  model-derived completion language.
- Report scheduling, report history, factual digests, and optional report
  narratives retain their existing ownership and semantics.
- Thread detail remains transient/no-store for full history; session cards link
  to it without embedding transcript content in the dashboard.
- Task-thread link/unlink remains explicit, local, idempotent, and independent of
  brief refresh.
- Existing observer capability labels and connection indicator remain truthful;
  standalone history does not claim visibility into another client's live
  requests.
- Ordinary chats remain read-only. Refresh and retry schedule ephemeral analysis
  only through the session-brief service.
- No raw transcript, prompt, reasoning, model envelope, tool payload, command,
  diff, or secret reaches browser state, HTML, SSE, logs, snapshots, or tests.
- Loopback Host/Origin security, `Cache-Control: no-store` transient details,
  local SQLite behavior, diagnostics, export/delete, and graceful shutdown do
  not regress.
- No files under `buddy_*`, `docs/contracts/`, runtime assets, or unrelated
  repository components change.

## Acceptance Criteria

1. Priority 03 is titled **Recent session briefs** and is the only recent-session
   card surface. The old heading, runtime-first comparator, 20-card cap, and old
   explanatory copy are absent from production and tests.
2. With at least 10 eligible sessions, exactly 10 cards render in canonical
   `recencyAt ?? updatedAt` descending order even when an older session is
   runtime-active. With fewer than 10, all available sessions render and the
   count is truthful.
3. Every card shows factual title, source, cwd, runtime, recency, thread-detail
   link, unplanned state when applicable, and functioning outcome link/unlink
   controls before, during, and after analysis.
4. A ready brief renders **Going on**, **Chat-reported done**, **What you should
   do**, and **Blockers** in that order, with aligned empty-list wording and no
   implication of operator-confirmed completion.
5. Every generated result visibly states `GPT-5.6 derived`, confidence,
   generation time, current/stale freshness, and lifecycle using text in
   addition to color.
6. The initial GET and later SSE events update aggregate counts, card lifecycle,
   and structured results without page reload, duplicate cards, lost task-link
   controls, or focus jumps.
7. Queued and analyzing cards retain factual metadata and show stable, truthful
   progress content.
8. A newer source revision leaves the last good brief visible and labeled stale
   while replacement is queued/analyzing. A failed replacement cannot overwrite
   or hide that last good brief.
9. Unavailable/offline and stream-interrupted states preserve the last snapshot,
   distinguish global live-update degradation from per-session failure, and
   leave planning, Needs You, factual completed work, and reports usable.
10. Failed/unavailable sessions expose a title-specific retry. It is disabled
    with explanatory copy while the snapshot says Codex cannot accept analysis
    work. Retry affects only that card; refresh-all affects the canonical recent
    window. Duplicate clicks cannot create duplicate client requests.
11. **Refresh 10 briefs** reports aggregate queued/analyzing/ready progress,
    disables only while its mutation is pending or the server snapshot says
    analysis work is unavailable, retains keyboard focus, and does not
    optimistically claim model success.
12. Empty, loading, read failure, mutation failure, malformed SSE, and no-last-good
    cases have distinct truthful copy. Raw server/model/transcript content is
    never rendered.
13. Keyboard-only browser proof reaches and activates refresh-all, a per-session
    retry, outcome-link controls, and a thread link; focus indicators and
    accessible names remain visible through live updates.
14. At a 390×844 viewport the section and every tested state have no body or
    document horizontal overflow, clipped controls, inaccessible content, or
    color-only status.
15. Existing App/dashboard, live-work, observer, Needs You, planning, reports,
    settings, privacy/recovery, build, and package-wide tests remain green.

## Ordered Implementation Tasks

1. Reconcile the checked-out Slice 01–02 `session-briefs.ts` DTO, exact route
   paths, lifecycle values, snapshot ordering, HTTP 202 mutation responses, and
   `session-briefs` SSE event against this plan. Stop if the upstream contract
   does not expose ordered selected thread IDs, aggregate progress,
   last-good-plus-current-lifecycle state, or safe error data needed for
   truthful rendering, or if Slice 01's deterministic placeholder remains.
2. Update/add failing client tests for the exact dashboard hierarchy, canonical
   10-card order, fewer-than-10 empty/count behavior, factual shell, four derived
   blocks, labels, lifecycle states, and old-heading/20-card removal.
3. Implement the thin session-brief API adapter using the canonical Slice 01
   types and routes. Parse server errors through the existing safe JSON error
   convention; do not add transcript or model-call code.
4. Implement the provider with initial GET, dedicated SSE, retained last
   snapshot, stream-error state, refresh-all pending state, per-thread retry
   pending state, EventSource cleanup, and authoritative mutation/SSE updates.
5. Add `RecentSessionBriefs` and one `SessionBriefCard`, reusing/extracting
   factual thread/task-link presentation. Render stable factual shells and the
   exact structured headings, labels, empty-list copy, errors, and controls.
6. Replace only Priority 03 in dashboard composition. Preserve or cleanly
   extract Priority 04, remove the runtime-first 20-card logic and superseded
   copy/tests/selectors, and keep one recent-session implementation.
7. Extend existing styles for aggregate header controls, derived blocks,
   lifecycle/freshness labels, stale last-good treatment, stable loading shells,
   safe wrapping, focus states, reduced motion, one-column `<=900px`, and exact
   390px behavior.
8. Add provider/component tests using controlled fetch and EventSource doubles
   for live queued→analyzing→ready, stale refresh, last-good failure, offline,
   malformed/disconnected SSE, refresh-all idempotency/focus, per-card retry,
   task links, and unmount cleanup.
9. Extend the deterministic e2e fixture with at least 11 eligible factual
   sessions so Playwright proves literal recency selection caps at 10 and does
   not promote an older active session. Supply only invented bounded structured
   briefs; never copy a real chat transcript.
10. Add Playwright flows for desktop live progress/manual controls and desktop +
    390px read-only state/accessibility/overflow. Preserve independent test state
    or gate the single mutating flow to desktop as current tests do.
11. Update all old dashboard/live-work/observer selectors and assertions to the
    canonical heading/card semantics, run focused and full verification, inspect
    rendered HTML/test artifacts for forbidden content, and record exact results
    in the implementation status block.

## Verification Commands And Expected Outcomes

Run from `/home/syncrobot/buddy/apps/codex-daily`:

```bash
npm test -- --run test/client/features/session-briefs/session-briefs.test.tsx
npm test -- --run test/client/features/live-work/live-work.test.tsx
npm test -- --run src/client/App.test.tsx
npm run test:e2e -- session-briefs.spec.ts daily-dashboard.spec.ts codex-observer.spec.ts
npm run lint
npm run typecheck
npm test
npm run build
npm run check
npm run test:e2e
```

Expected:

- focused component/provider tests prove canonical ordering, all lifecycle
  branches, last-good preservation, live SSE updates, refresh/retry request
  ownership, focus retention, and provider cleanup;
- focused browser tests prove exactly 10 cards from an 11-session fixture,
  recency rather than runtime ordering, queued/analyzing/ready progress, stale
  and offline/failure rendering, keyboard use, task links/thread links, and no
  390px overflow;
- lint and both TypeScript projects pass;
- every Vitest suite and production build passes; and
- the full Playwright matrix passes without relying on test order.

From `/home/syncrobot/buddy`:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts runtime_assets
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git status --short
```

Expected: no whitespace errors; no protected ROS/contract/runtime-asset changes;
repository contracts pass; and status contains only intended session-brief
frontend work plus preserved pre-existing/concurrent changes.

If Playwright cannot bind `127.0.0.1:4317` inside the sandbox, rerun the exact
`npm run test:e2e` command with the required host-context approval and record the
deviation. Do not switch to a non-loopback host.

## Risks And Dependencies

- Slices 01–02 must expose one canonical snapshot that can represent ordered
  selected thread IDs, aggregate lifecycle, a last good result, current source
  revision/freshness, and safe failure at once. The factual shell comes from the
  independent observer join by `threadId`. A flattened `summary | null` alone
  cannot render stale/failing truthfully.
- Independent observer and brief SSE streams may arrive in either order. Join by
  stable thread ID, preserve server selection order, and test source-window and
  task-link updates without fabricating absent metadata.
- Re-rendering cards on SSE can steal focus or reset the outcome-link select.
  Use stable keys and stable controls; test focus across multiple updates.
- EventSource errors are normal during reconnect. Keep stream degradation
  separate from generation failure and do not clear last-known data.
- Ten rich cards can become dense. Preserve scannable headings and one-column
  mobile layout without hiding required fields behind collapsed disclosure in
  this slice.
- Existing `.work-card` selectors are shared by tests. Rename deliberately and
  update all consumers so old semantics cannot silently survive.
- Deterministic e2e live progress may require a fixture control seam. Keep it
  test-owned and content-free; do not add production debug mutation routes.
- App Server access can fail when the app is launched inside a restricted
  filesystem sandbox. That runtime limitation must produce the aligned offline
  UI, not be masked by browser fixtures.

## Stop Conditions And Blocked Handling

Stop and report rather than improvising when:

- Slice 01 or Slice 02 is not implemented and verified.
- Their canonical DTO/routes cannot express server-selected order, last-good
  stale content plus current lifecycle, safe failure, observer availability, or
  aggregate progress.
- The checked-out implementation conflicts materially with this plan or would
  require a second brief schema/provider/API shape.
- A truthful UI would require fetching or exposing raw transcript/model content
  to the browser.
- Refresh/retry would mutate ordinary chats, use a browser GPT call, or bypass
  server concurrency/idempotency.
- Preserving task links, Priority 04, or existing provider semantics requires a
  broad unrelated dashboard rewrite.
- Required focused/full verification cannot run, or Playwright fixtures cannot
  exercise the approved lifecycle without a production-only test backdoor.
- Concurrent/user changes overlap required files and cannot be preserved.
- The slice expands into any deferred `FUP-###` item or becomes materially
  larger than this bounded frontend integration.

When blocked, keep a minimal failing component/browser test when safe, record the
exact contract mismatch and command output in the status block, set
`Status: blocked`, and request a product/plan decision. Do not add compatibility
fallbacks or silently weaken the acceptance criteria.

## Preserve Unrelated Changes

The planning worktree already contains concurrent changes in
`docs/about/05_ux_decision_catalogue.md` and the current feature pipeline.
Treat all pre-existing and concurrent work as user-owned. Before editing, inspect
`git status --short` and the relevant diff; do not reset, clean, stash, reformat,
stage, commit, overwrite, or delete unrelated paths. Restrict implementation to
the Codex Daily frontend, its deterministic test fixture, and this slice's tests.
Stop if an overlapping change cannot be preserved safely.

## Expected Final Summary

Report:

- `implemented` or `blocked`, branch, and commit;
- the canonical Priority 03 hierarchy and confirmation that the old runtime-first
  20-card surface was removed;
- provider/API/SSE ownership, refresh-all and per-session retry behavior;
- exact lifecycle, stale/offline/failure, derived/confidence/freshness labels,
  and empty-list wording delivered;
- proof of exactly 10 literal-recency cards, factual metadata/task-link
  preservation, keyboard focus, and 390px no-overflow behavior;
- focused and full verification commands with pass/fail counts;
- confirmation that Needs You, planning, factual completed work, reporting,
  privacy/read-only boundaries, unrelated changes, and ROS paths were preserved;
- deviations, risks, and any `FUP-###`/issue references; and
- the next approved Slice 04 implementation source, not `3_plan.md`.

## Readiness Gate

- Exact slice: canonical Recent session briefs frontend for the server behavior
  implemented by Slices 01–02.
- Out of scope: model/storage/scheduler implementation, chat control, task
  automation, report integration, and all deferred follow-ups.
- Follow-ups: none included; `FUP-001`–`FUP-005` remain deferred.
- Relevant modules, patterns, cleanup, non-regression boundaries, acceptance
  criteria, commands, risks, stop conditions, preservation rules, and final
  summary are specified above.
- Implementation authority: the user's autonomous implementation request permits
  work only after the dependent slice plans are approved and Slices 01–02 are
  implemented and verified.
