# Codex Daily — Slice 01 Daily Dashboard

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
- Selected vertical slice: `01 — Daily Dashboard`
- Sequence: `01 of 06`
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`,
  `CURRENT.md`, and `docs/about/05_ux_decision_catalogue.md`

Implement a runnable, local dashboard that demonstrates the complete day-first,
attention-first product model with deterministic representative data. This slice
establishes the bounded web application, UI hierarchy, shared view contract, and
test foundation that later slices replace with persistence and Codex observation.

## Repository Rules

- Consulted: root `README.md`, repository inventory and integration-validation
  contracts, existing repository boundary tests, the source documents above, and
  current Git status. `docs/rules/` does not exist, so no `docs/rules/README.md` or
  rule file was available.
- Constraints applied: keep the application outside all `buddy_*` ROS packages;
  preserve the ROS 2 Jazzy/Gazebo build and test boundary; use Node 24; bind local
  servers to loopback; do not reuse or modify generated/vendor web code under
  ignored `runtime_assets/`; keep all new web dependencies in one app-local npm
  package and lockfile.
- Rule updates: None.

## Scope

Create `apps/codex-daily/` as one npm package:

- Node 24, TypeScript, Fastify, and `@fastify/static` for the local service.
- React, React Router, and Vite for the browser interface.
- Plain CSS with app-owned tokens rather than a new design-system dependency.
- Vitest and Testing Library for shared/server/component tests.
- Playwright Chromium for responsive navigation and ordering smoke tests.

The local service supplies deterministic representative data through
`GET /api/day` and connection/demo status through `GET /api/health`. In
development Vite proxies `/api` to the loopback service; in production the same
service serves the built client. The browser must not import server fixtures
directly. Keep the shared `DashboardSnapshot` contract narrow so later slices can
replace the source without rewriting the page.

The primary route is the daily dashboard. It renders, in this exact order:

1. Needs your attention.
2. Today's outcomes and progress.
3. Active Codex chats.
4. Recently completed work.
5. Evening-report preview.

Provide working secondary routes for representative thread detail, report
history, and settings. They may be read-only placeholders, but must preserve the
shell, return navigation, and responsive behavior.

## Explicit Non-Goals

- Persistence, `node:sqlite`, morning editing, task completion actions, or
  carry-forward behavior (Slice 02).
- Codex App Server connection, live events, reconnection, or real thread content
  (Slice 03).
- Attention derivation, acknowledgement, or dismissal (Slice 04).
- Report generation, scheduling, history storage, or intelligent narrative
  (Slice 05).
- Recovery/privacy tooling beyond showing that this slice uses representative
  local data (Slice 06).
- Full transcript storage, completion inference that mutates a task, chat
  controls, cloud hosting, authentication, teams, integrations, or changes to
  existing ROS packages.

## Follow-Up Scope

- Included deferred items: none.
- Still deferred: FUP-001 evidence-backed completion, FUP-002 weekly review,
  FUP-003 third-party integrations, FUP-004 multi-device sync, FUP-005 cost and
  limit insights, and FUP-006 proactive chat control.
- Do not fold any deferred item into fixtures, controls, acceptance criteria, or
  architecture during this slice.

## Central Issue Scope

- Included issue-register IDs: none.
- Newly created issue-register IDs: none.
- Still deferred issue-register IDs: none known.
- The repository has no `docs/issues/register.md`; do not create one merely for
  this slice. Stop if implementation discovers durable architecture debt or a
  blocking issue that needs central tracking.

## Canonical Mental Model And Cleanup

The day owns intent, observed work, attention, and reconciliation. Chats are
evidence attached to daily outcomes; a finished turn is not a finished outcome.
Representative data must visibly distinguish confirmed, suggested, pending, and
blocked work, and distinguish factual report content from generated
interpretation.

Do not introduce a chat-history-first home page, undifferentiated notification
feed, automatic completion/carry-forward, transcript mirroring, or thread-control
actions. Remove all Vite starter counters, logos, names, styles, and tests. Keep
one shared snapshot contract, one representative server fixture, and one route
map; do not add duplicate client fixtures, compatibility adapters, or alternate
status names. Routine progress and completed turns belong outside Needs You.

## Likely Files And Modules

All implementation files should remain under `apps/codex-daily/`:

- `package.json`, `package-lock.json`, `.gitignore`, `README.md`
- `tsconfig*.json`, `vite.config.ts`, `vitest.config.ts`,
  `playwright.config.ts`, `eslint.config.js`, `index.html`
- `src/shared/dashboard.ts` — discriminated status types and
  `DashboardSnapshot`
- `src/server/app.ts`, `src/server/main.ts`,
  `src/server/representative-day.ts` — testable Fastify builder, loopback entry
  point, health/day endpoints, and production static fallback
- `src/client/main.tsx`, `src/client/App.tsx`,
  `src/client/api/dashboard-client.ts`
- `src/client/pages/DashboardPage.tsx`, `ThreadDetailPage.tsx`,
  `ReportsPage.tsx`, `SettingsPage.tsx`
- Focused components for the app shell, connection indicator, attention list,
  outcomes, work lists, report preview, and status badges
- `src/client/styles.css` with dark-default tokens, layouts, focus states, and
  responsive breakpoints
- Co-located `*.test.ts`/`*.test.tsx` files and
  `e2e/daily-dashboard.spec.ts`

Expected app-local scripts:

- `npm run dev` — run Vite and the Fastify service on loopback.
- `npm run build` and `npm run start` — build both sides and serve the built app.
- `npm run lint`, `npm run typecheck`, `npm test`, `npm run test:e2e`.
- `npm run check` — lint, type-check, unit/component tests, and build.

## Existing Patterns And Non-Regression

- Follow existing repository practice of bounded components with tests owned by
  their package and deterministic fakes at unavailable integration boundaries.
- Keep entry points thin and put service construction in an importable function,
  matching the repository's testable-core/entry-point separation.
- Use semantic landmarks, headings, lists, buttons/links, visible keyboard focus,
  non-color status labels, and readable timestamps.
- Keep connection health visible while every local representative surface remains
  usable; label the data as representative and Codex as not connected.
- Preserve sparse status color, dark default, dense readable layout, and explicit
  uncertainty for `possibly stale`.
- Do not edit `buddy_*`, ROS launch/config/interface files, `runtime_assets/`, or
  existing contracts. The new directory must not contain `package.xml` or enter
  the colcon package graph.
- Preserve all unrelated untracked or modified user files. Before editing and
  before committing, inspect `git status`; never revert, reformat, stage, or
  include paths outside this slice except the plan status update requested by the
  workflow.

## Acceptance Criteria

1. From `apps/codex-daily/`, a clean `npm ci` followed by `npm run check`
   succeeds on Node 24, and `npm run start` serves the built application only on
   `127.0.0.1`.
2. `GET /api/health` and `GET /api/day` return typed, deterministic
   representative responses; the client handles loading and failure without a
   blank page.
3. The dashboard renders the five approved primary sections in exact priority
   order at desktop and mobile widths.
4. Needs You demonstrates approval, direct-question, failure/interruption,
   explicit-blocker, and low-certainty `possibly stale` states. Routine progress
   and completed work are absent from that section.
5. Outcomes demonstrate confirmed, suggested, pending, and blocked states.
   Suggested completion is visibly unconfirmed and no UI action silently confirms
   it.
6. Active chats, recently completed work, the factual-first report preview, and
   connection health are visible. Unlinked activity is presented as unplanned
   work rather than hidden.
7. Representative thread detail, report history, and settings routes are
   reachable through real links, have useful empty/read-only content, and return
   to Today without losing the shell.
8. The interface is usable without horizontal overflow at 390 CSS pixels and
   remains dense/readable at 1440 pixels. Keyboard navigation, visible focus,
   semantic headings, and text status labels are covered.
9. No endpoint writes data, no browser storage or external service is used, no
   full transcript is represented as retained data, and no control suggests
   approving, prompting, archiving, or mutating Codex work.
10. Unit/component tests cover contract rendering, hierarchy, attention
    separation, suggested-versus-confirmed completion, API errors, and secondary
    navigation. Playwright covers built-app startup, route navigation, section
    order, and desktop/mobile overflow.
11. Existing ROS source, contracts, package discovery, build configuration, and
    tests remain unchanged.

## Ordered Implementation Tasks

1. Confirm Node 24, capture `git status`, create the isolated npm package, install
   the selected runtime/test tooling, commit the generated lockfile, and add only
   app-local ignores for dependencies, builds, coverage, and browser-test output.
2. Configure TypeScript, Vite proxy/build output, ESLint, Vitest environments,
   Playwright web-server startup, and the scripts listed above.
3. Define the shared discriminated snapshot contract and one deterministic
   representative fixture covering all accepted states without transcript
   bodies.
4. Build the importable Fastify app, health/day routes, loopback entry point,
   production static serving, and server contract tests.
5. Build the API client and explicit loading/error handling; do not fall back to a
   second hidden fixture.
6. Implement the responsive shell, navigation, connection state, and five ordered
   dashboard sections using accessible, small components.
7. Add representative secondary routes and ensure every primary item linking to
   detail has a valid target.
8. Apply app-owned visual tokens and responsive/accessibility behavior; keep
   `possibly stale`, failures, suggestions, facts, and generated copy visually and
   textually distinct.
9. Add component and Playwright coverage for all acceptance criteria, then remove
   every scaffold artifact and unused dependency.
10. Run the verification matrix, inspect the final diff for scope, update this
    plan's implementation status, and report without touching unrelated changes.

## Verification And Expected Outcomes

Run from `apps/codex-daily/` unless noted:

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

Expected: Node reports `v24.x`; dependency installation follows the committed
lockfile; lint and both TypeScript boundaries pass; all Vitest suites pass; the
production client/service build succeeds; Playwright Chromium passes at desktop
and mobile viewports; the aggregate check exits zero.

Manual smoke:

```bash
npm run start
```

Expected: the built app is reachable at the documented loopback URL, the health
and day endpoints respond, the five primary sections are in the approved order,
secondary navigation works, and a failed day request produces a visible error
state. Stop the process after verification.

Run from the repository root:

```bash
colcon list
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
git status --short
```

Expected: `colcon list` contains only the existing ROS packages and not
`codex-daily`; the diff has no whitespace errors; the scoped ROS/contracts diff is
empty; status contains only intended app files, this plan's status update, and
pre-existing unrelated user changes. Full ROS build/test is not required for this
isolated UI slice unless any ROS-owned path changes, in which case stop because
the slice boundary has been violated.

## Risks, Dependencies, And Stop Conditions

- Dependency installation and Playwright browser provisioning may require network
  access. If unavailable, report the exact failed command; do not replace the
  stack or claim browser verification passed.
- Representative content can accidentally imply real monitoring. Keep a visible
  demo/not-connected label and deterministic fixture ownership on the server.
- Static serving and SPA fallback can differ from Vite development behavior.
  Exercise both development component tests and the built-service Playwright path.
- Responsive density can hide priority on small screens. Preserve section order
  instead of moving primary sections into separate mobile-only navigation.
- Stop and report if the approved source documents conflict, Node 24 is
  unavailable, implementation needs persistence/App Server/report scheduling,
  tests cannot run, a new root-wide toolchain is required, or files outside the
  bounded app and plan status must change.
- Stop and return to planning if the shared snapshot cannot support the approved
  states without designing later-slice domain behavior, or if the slice grows
  beyond a representative read-only dashboard.
- When blocked, preserve the working tree, record the failing command and
  observed output, list the smallest decision or dependency needed, and do not
  add compatibility fallbacks or silently weaken verification.

## Expected Final Summary

The implementing agent's final response must contain:

- **Implemented:** concise UI/service behavior and exact major paths added.
- **Verification:** every command run and its pass/fail outcome, including
  Playwright viewport coverage and the ROS-boundary checks.
- **Deviations:** any difference from this plan, or `None`.
- **Follow-ups:** newly discovered work with an existing stable ID, or `None`;
  keep FUP-001 through FUP-006 deferred.
- **Unrelated changes preserved:** paths seen before implementation that were not
  modified or staged.
- **Implementation status:** resulting commit hash and confirmation that this
  plan block was updated to `implemented`, or the precise blocker if not.
