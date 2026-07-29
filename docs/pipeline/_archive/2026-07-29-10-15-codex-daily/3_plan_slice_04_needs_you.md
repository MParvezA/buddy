# Codex Daily — Slice 04 Needs You

## Implementation Status

Status: implemented
Commit: `Slice 04: Needs You` (this status-bearing commit)
Verification: `npm run check` passed with 16 files/44 tests; independent Playwright verification passed 7 browser flows with 3 intentional duplicate mobile-flow skips; repository contracts passed 4/4; protected-path diff was empty. Focused tests prove exact 30-minute staleness, shared-live-only requests, deterministic replay/resolution, local-only acknowledge/dismiss, lifecycle history, content stripping, and zero Codex transport actions.
Deviations: Playwright required sandbox escalation to bind the loopback test server. `npm ci` reported seven existing dependency audit advisories; dependency remediation was not expanded into this slice.
Follow-ups: None. FUP-001 through FUP-006 remain deferred.

## Context And Selected Slice

- Repository: `/home/syncrobot/buddy`
- Planning branch: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Sequence: `04`
- Selected vertical slice: **Needs You**
- Dependencies: approved and implemented Slices 01–03.
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`,
  `CURRENT.md`, `docs/about/05_ux_decision_catalogue.md`, and the approved Slice
  03 plan/implementation result.

Turn Slice 03's normalized App Server observations into one deterministic,
attention-first queue. The operator can acknowledge or dismiss derived items
locally, but Codex Daily never answers an approval, question, elicitation, or
other App Server server request.

## Repository Rules

- Consulted: root `README.md`; feature design, alignment, roadmap, and current
  routing; UX decision catalogue; locally generated Codex App Server JSON schemas
  from installed `codex-cli 0.146.0-alpha.3.1`. No root `AGENTS.md` or
  `docs/rules/README.md` exists.
- Constraints applied: extend Slice 01's bounded `apps/codex-daily/` Node 24/npm
  11 Fastify + React/Vite application and Slice 03's observer/storage boundaries;
  preserve the ROS workspace; retain minimal local metadata; preserve source
  certainty; keep ordinary Codex chats strictly read-only.
- Rule updates: None

## Exact Scope

- Derive attention items from normalized observer state/events.
- Persist stable source identity, kind, certainty, lifecycle, timestamps, and
  local acknowledgement/dismissal state.
- Reconcile items on startup, live events, App Server request resolution, thread
  activity, and a clock-driven staleness sweep.
- Serve the active queue and local acknowledge/dismiss mutations.
- Replace the Needs You representative cards with the real queue while preserving
  the dashboard's primary position and source links.
- Keep resolved/acknowledged/dismissed source activity available in thread detail.
- Test derivation with fake App Server events and staleness with a fake clock.

## Explicit Non-Goals

- Approving, denying, cancelling, or otherwise responding to App Server server
  requests.
- Answering direct questions or MCP elicitations, sending prompts, steering or
  interrupting turns, or changing thread state.
- Natural-language guessing that arbitrary prose is a blocker.
- Treating routine progress, completed turns, idle threads, archived threads, or
  unknown state as attention.
- Task completion suggestions or confirmation changes.
- Report generation, scheduling, or history.
- Email, Slack, calendar, or other third-party notifications.
- Full transcript storage, autonomous remediation, escalation policies, snooze,
  assignments, teams, or remote access.

## Follow-Up Scope

- Included `FUP-###` items: none.
- Still deferred: `FUP-001` evidence-backed completion, `FUP-002` weekly review,
  `FUP-003` third-party integrations, `FUP-004` multi-device sync, `FUP-005`
  cost/limit insights, and `FUP-006` proactive chat control.
- In particular, acknowledgement/dismissal must not become the first piece of
  `FUP-006`.

## Central Issue Scope

- Included issue IDs: none.
- Still deferred issue IDs: none identified.
- Newly created issue IDs: none.
- The repository has no central issue register. If Slice 03 exposes no stable
  source identity or no explicit structured blocker signal, stop and report the
  contract gap; do not hide it with text heuristics.

## Canonical Mental Model And Cleanup

An attention item is a local projection of a still-inspectable observed source.
It is not the source event, a task, a chat message, or a Codex action.

Canonical fields:

- stable item ID and deterministic `source_key`;
- thread ID and, where available, turn/item/server-request ID;
- `kind`: `approval`, `direct_question`, `failed_turn`, `interrupted_turn`,
  `explicit_blocker`, or `possibly_stale`;
- `certainty`: `explicit` for the first five kinds and `possible` only for stale;
- source timestamp, last-derived timestamp, and compact source metadata;
- lifecycle: `open`, `acknowledged`, `dismissed`, or `source_resolved`;
- local action timestamp.

Derivation rules:

| Source | Attention result | Certainty |
| --- | --- | --- |
| Pending approval server request normalized by Slice 03 | `approval` immediately | `explicit` |
| Pending `item/tool/requestUserInput` or equivalent normalized direct elicitation | `direct_question` immediately | `explicit` |
| Turn status becomes `failed` | `failed_turn` immediately | `explicit` |
| Turn status becomes `interrupted` | `interrupted_turn` immediately | `explicit` |
| Slice 03 emits an explicit structured blocker observation | `explicit_blocker` immediately | `explicit` |
| Thread remains active with no observed activity for at least 30 minutes | `possibly_stale` | `possible` |

Do not derive a blocker from keyword matching, sentiment, an unknown state, or a
completed turn. If the implemented observer cannot produce an explicit blocker
observation, stop for a protocol/product decision.

Use one item per stable source occurrence. Replaying inventory/events must upsert,
not duplicate. `serverRequest/resolved` or equivalent observer resolution moves
the matching request-derived item to `source_resolved`. New thread activity
source-resolves its current stale item; another 30-minute quiet active episode
may create a new item keyed by the new last-activity timestamp. Acknowledgement
and dismissal alter only local projection state.

Required cleanup:

- Remove Slice 01's representative Needs You data and fake action handlers.
- Remove any combined activity/attention filter or `isImportant` heuristic.
- Keep routine activity in Live Work/recent activity.
- Keep one attention type contract and one derivation engine; no UI-only fallback,
  duplicate localStorage state, or alternate certainty names.
- Never add Approve, Deny, Answer, Interrupt, or Send controls to attention cards.

## Likely Files And Components

Extend the actual Slice 03 names; do not create a parallel observer or app.
Likely additions/modifications:

- `apps/codex-daily/src/shared/attention.ts`
- `apps/codex-daily/src/server/storage/migrations/003_attention.sql` (use the next
  migration number established by prior slices)
- `apps/codex-daily/src/server/attention/attention-repository.ts`
- `apps/codex-daily/src/server/attention/attention-engine.ts`
- `apps/codex-daily/src/server/attention/staleness-monitor.ts`
- `apps/codex-daily/src/server/attention/attention-routes.ts`
- Slice 03's normalized event sink and fake App Server source
- `apps/codex-daily/src/server/app.ts`
- `apps/codex-daily/src/client/api/attention.ts`
- `apps/codex-daily/src/client/features/attention/NeedsYou.tsx`
- `apps/codex-daily/src/client/features/attention/AttentionCard.tsx`
- the Slice 01 dashboard composition/styles
- colocated Vitest tests for repository, engine, routes, timer, and components
- `apps/codex-daily/e2e/needs-you.spec.ts`

The installed App Server schema confirms server-initiated request methods for
command/file/permission approvals and user input, plus
`serverRequest/resolved`, turn statuses including `failed`/`interrupted`, and
opaque request IDs. Consume these only through Slice 03's narrow normalized
adapter and hand-written protocol subset. Do not import raw protocol envelopes
or send a JSON-RPC response from this slice.

## Existing Patterns And Non-Regression

- Follow Slice 01's Fastify composition, shared DTOs, React query/loading/error
  states, accessibility, visual tokens, Vitest/Testing Library, and Playwright.
- Follow Slice 02's SQLite migration/repository transaction conventions.
- Follow Slice 03's narrow protocol decoder, normalized observation model,
  reconnect/deduplication behavior, connection health, source-detail routing, and
  fake event source.
- Inject `Clock` and timer scheduling; tests must not wait 30 real minutes.
- Preserve dashboard order: Needs You remains first.
- Render explicit items more strongly than `possibly stale`; stale must be visibly
  labeled low-certainty and ordered after explicit open items.
- Preserve planning and last-known observations while App Server is disconnected.
- Do not mutate task completion, thread status, App Server requests, or Codex
  history.
- Do not persist full prompts, answers, transcripts, credentials, or raw protocol
  payloads.
- Do not change files under `buddy_*` or `docs/contracts/`.

## Acceptance Criteria

1. In shared-live mode, pending approvals and direct questions received from the
   shared transport enter Needs You immediately from normalized server requests.
   In standalone-history mode, the UI explicitly states that external-client
   live approval/question coverage is unavailable and does not fabricate items.
2. Failed turns, interrupted turns, and `thread/goal/updated` with structured
   status `blocked` enter immediately with `explicit` certainty; goal clearing or
   a non-blocked goal update source-resolves the blocker.
3. An active thread enters as `possibly_stale` only when the injected clock
   reaches 30 minutes since its last observed activity; 29:59 does not qualify.
4. Routine progress, completed turns, idle/archived/unknown threads, and
   disconnected state do not create attention items.
5. Replay, reconnect, duplicate events, and repeated timer sweeps do not duplicate
   items.
6. New activity source-resolves a stale item; resolution of an App Server request
   source-resolves its matching approval/question item.
7. Acknowledge and dismiss persist locally, remove the item from the default open
   queue, and leave source activity visible in thread detail.
8. No acknowledge/dismiss route or UI action writes a JSON-RPC response, starts/
   steers/interrupts a turn, or mutates Codex.
9. Explicit items are ordered ahead of possible-stale items with readable source
   time, thread context, certainty, and a thread-detail link.
10. App Server disconnection preserves the last queue and clearly retains stale
    last-known semantics without fabricating new explicit items.
11. The local schema contains only normalized attention metadata and local state,
    not full request/question/transcript bodies.
12. Lint, typecheck, unit/integration tests, build, and Playwright flow pass without
    ROS changes.

## Ordered Implementation Tasks

1. Reconcile this contract with the implemented Slice 03 normalized event types,
   stable IDs, observation capability, structured goal events, persistence, fake
   source, and source-detail route. Stop on a missing structured-goal or
   request-resolution contract.
2. Write failing table-driven engine tests for every source mapping, exclusions,
   certainty, ordering, replay, resolution, and stale boundary using fake events
   and a fake clock.
3. Add the attention migration/repository with unique `source_key`, constrained
   kinds/certainty/lifecycle, indexed open-queue ordering, and local mutations.
4. Implement the pure derivation engine and connect it to Slice 03's initial
   reconciliation and live normalized event sink.
5. Implement an injected staleness monitor that evaluates at startup and on a
   short scheduled cadence without real-time sleeps in tests.
6. Add Fastify read/acknowledge/dismiss routes. Keep them local-state-only and
   prove the App Server transport receives zero outbound responses/actions.
7. Replace only the representative Needs You UI with accessible real cards,
   certainty treatment, source links, pending/error feedback, and empty state.
8. Remove superseded attention fixtures/heuristics, run full verification, and
   record exact evidence in the status block.

## Verification Commands And Expected Outcomes

From `apps/codex-daily/`:

```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run check
```

Expected: clean install; lint/typecheck pass; all earlier and new Vitest suites
pass; production build succeeds; Playwright proves immediate explicit attention,
30-minute fake-clock staleness, local acknowledgement/dismissal, persistence, and
zero App Server responses; the aggregate gate is green.

From the repository root:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git status --short
```

Expected: no whitespace errors, no ROS/frozen-contract changes, repository
contract tests pass, and only intended Codex Daily plus pre-existing unrelated
changes appear.

## Risks, Dependencies, And Stop Conditions

- App Server is evolving; use Slice 03's narrow decoder and normalization
  boundary, never raw ad hoc method strings outside fixtures.
- Server requests require client responses in controlling clients, but this
  monitor is not that controller. Shared-live mode may observe and display them
  but must not claim ownership or respond. Standalone-history mode must show its
  lower capability instead of promising those events.
- The explicit-blocker source is the normalized structured thread-goal status.
  Stop and report if the installed stable protocol removes that source rather
  than replacing it with prose parsing.
- Timer races can duplicate or instantly resurrect stale items. Key stale episodes
  by thread plus last activity and test dismissal across repeated sweeps.
- Reconnection can reorder events. Upsert by source identity and make resolution
  monotonic.
- If implementation requires full request bodies, transcript retention, Codex
  mutation, new authentication, broad observer rewrites, or any deferred
  `FUP-###`, stop for replanning.
- If Slice 03 is not implemented/verified, verification cannot run, unrelated
  changes overlap required files, or the slice exceeds this bounded queue path,
  mark the status `blocked` and report exact evidence.

When blocked, preserve a minimal failing test/fixture where safe, record the
command and contract mismatch, and request a decision. Do not add a compatibility
fallback.

## Preserve Unrelated Changes

The planning worktree already contains untracked `docs/about/` and
`docs/pipeline/` content. Treat all pre-existing/concurrent changes as user-owned.
Inspect `git status --short` and relevant diffs before editing; do not reset,
clean, stash, reformat, overwrite, or commit unrelated paths. Stop if an overlap
cannot be preserved safely.

## Expected Final Summary

Report:

- `implemented` or `blocked`, branch, and commit;
- derived kinds/certainty and exact stale timing delivered;
- schema, engine, routes, components, and removed fixture paths;
- proof that acknowledge/dismiss are local-only and no App Server request was
  answered;
- verification commands and outcomes;
- deviations, risks, and any `FUP-###`/issue references;
- confirmation that unrelated changes and ROS behavior were preserved; and
- the next approved Slice 05 implementation source, not `3_plan.md`.
