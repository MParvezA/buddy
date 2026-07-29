# Codex Daily — Slice 02 GPT-5.6 Background Analysis

Archived after completed implementation review and cleanup.

## Implementation Status

Status: implemented
Commit: `Slice 02: GPT-5.6 Background Analysis` (this status-bearing commit)
Verification: `npm run check` passed with 40 files/145 tests; focused brief coverage passed 8 files/43 tests; focused Codex/report regressions passed 10 files/38 tests; privacy/runtime coverage passed 4 files/8 tests; full Playwright passed 16 runnable flows with 6 intentional mobile duplicate-flow skips; repository contracts passed 4/4; `colcon list` remained 16; protected-path and whitespace checks were clean. Deterministic integration proves the exact GPT-5.6 Sol/medium/ephemeral/no-fallback/no-tools/no-environment payload, 32,000-code-point bound, exact thread/turn correlation, retries, supersession, durable promotion epoch, and content-leak prevention.
Deviations: Playwright required host-context execution after the sandboxed `tsx` IPC socket failed with `EPERM`. The active coordinator epoch is stored in a singleton SQLite row added by migration 007 and checked inside the same `BEGIN IMMEDIATE` promotion transaction; this uses the existing job token and timestamps without adding a parallel job-history model.
Follow-ups: None. `FUP-001` through `FUP-005` remain deferred.

## Context

- Repository: `/home/syncrobot/buddy`
- Planning branch target: `dev`
- Recommended implementation branch:
  `feature/2026-07-29-16-04-session-briefs`
- Feature folder:
  `docs/pipeline/2026-07-29-16-04-session-briefs/`
- Selected vertical slice: `02 — GPT-5.6 Background Analysis`
- Sequence: `02 of 04`
- Depends on: Slice 01 Brief Contract And Storage implemented and verified
- Source documents: `1_design.md`, `2_alignment.md`, `3_plan.md`,
  `CURRENT.md`, and the implemented
  `3_plan_slice_01_brief_contract_storage.md`
- Baseline application: reviewed Codex Daily implementation ending at `f255d46`
- Protocol evidence: installed Codex App Server JSON schemas generated from
  `codex-cli 0.146.0-alpha.3.1` under
  `/tmp/codex-daily-gpt56-schema/`

Replace Slice 01's deterministic placeholder analyzer with the real,
privacy-bounded background path: transiently read one eligible ordinary thread,
extract its first user intent plus the six most recent turns, send at most 32,000
Unicode characters to an ephemeral `gpt-5.6-sol` analysis thread at medium
reasoning effort, validate the schema-constrained final assistant JSON, and
atomically promote only a current result. A debounced two-worker coordinator
must isolate failure, retry only bounded transient faults, supersede obsolete
revisions, recover after restart, and stop safely before shutdown or deletion.

This slice ends at the durable API/SSE lifecycle established by Slice 01. Slice
03 owns the final recent-session card presentation, aggregate progress UI, and
interactive frontend polish.

## Repository Rules

- Consulted: approved design/alignment/roadmap/current routing, the UX decision
  catalogue, archived Codex Daily slice-plan format, current observer,
  App Server, reporting, privacy, startup, database, and test boundaries, and
  the locally generated installed App Server schemas. No
  `docs/rules/README.md` or `docs/issues/register.md` exists.
- Constraints applied: extend the single Node 24/npm application under
  `apps/codex-daily/`; preserve loopback-only access, local SQLite, read-only
  ordinary chats, attention before activity, human-confirmed completion,
  minimal local retention, facts before generated interpretation, and the
  protected ROS boundary; use the installed App Server rather than a second API
  key or provider.
- Rule updates: None.

## Slice Scope

Implement one complete observer-to-analysis-to-brief path that:

- consumes Slice 01's canonical recent-10 selection and lifecycle records only
  after the observer has produced a usable connected snapshot;
- detects a missing, manually requested, or newer source revision;
- debounces automatic revision churn for 30 seconds;
- runs no more than two per-session analysis jobs concurrently;
- fetches the ordinary source with transient `thread/read` and never mutates it;
- renders only the first user intent plus the six most recent turns, bounded to
  32,000 Unicode code points including labels and truncation markers;
- creates one ephemeral internal analysis thread per attempt;
- explicitly requests `gpt-5.6-sol`, medium effort, no provider fallback, no
  tools, no environment, no workspace roots, and no multi-agent mode;
- supplies a strict `outputSchema` on `turn/start`;
- accepts only the final assistant JSON associated with the exact started
  analysis thread and turn;
- validates and persists only the structured brief;
- preserves the last good brief as stale when replacement is queued, running,
  unavailable, or failed;
- retries a transient attempt at most twice, after 30 seconds and then two
  minutes, while letting other sessions continue;
- rejects results from superseded revisions, canceled generations, sessions
  outside the recent window, or deleted local state;
- recovers orphaned work after restart and resumes only when the observer is
  usable; and
- publishes the resulting Slice 01 lifecycle changes through the existing brief
  read API and SSE stream without including transcript or raw model content.

Automatic refresh and manual refresh share one coordinator and one job identity
model. Automatic source changes wait for the 30-second debounce. An explicit
all-session or per-session refresh for an eligible current source revision moves
that work to the front immediately, but still respects the two-worker limit and
does not create duplicate work for an already queued or analyzing generation.

## Explicit Non-Goals

- The Slice 03 recent-session card UI, aggregate progress controls, responsive
  layout, or accessibility browser workflows.
- More than the canonical 10 eligible sessions, configurable analysis depth,
  configurable model choice, or a configurable worker count.
- A persistent all-session analysis thread, one 10-session batch, or reuse of
  the dedicated daily-report thread.
- A separate OpenAI API integration, API-key management, provider fallback,
  prompt caching controls, Pro mode, multi-agent mode, dynamic tools, MCP tools,
  skills, repository inspection, shell access, workspace access, or environment
  access.
- Writing prompts, approvals, answers, metadata, archive state, or any other
  mutation to an ordinary source thread.
- Treating a model result as authoritative completion, changing morning tasks,
  creating Needs You entries, or feeding inferred actions into planning.
- Daily-report narrative integration, weekly synthesis, external
  notifications, accounts, synchronization, usage reporting, or cross-device
  retention.
- Persisting source turns, rendered prompts, raw App Server envelopes, raw model
  output, reasoning, command/tool payloads, or transcript excerpts.
- A production run against real ordinary-chat content in this slice. The host
  model contract and overnight proof belong to Slice 04; this slice uses the
  deterministic fake App Server and synthetic secrets.

## Follow-Up Scope

- Included deferred items: none.
- Still deferred:
  - `FUP-001` user-tunable session count;
  - `FUP-002` per-session analysis depth;
  - `FUP-003` weekly cross-session synthesis;
  - `FUP-004` external notifications; and
  - `FUP-005` automatic ordinary-chat actions.
- The fixed first-intent-plus-six-turn policy is the approved bounded policy,
  not an implementation of `FUP-002`.

## Central Issue Scope

- Included issue-register IDs: none.
- Newly created issue-register IDs: none.
- Still deferred issue-register IDs: none known.
- No `docs/issues/register.md` exists. Do not create one solely for this slice.
  If implementation reveals durable architecture debt or a verification gap
  outside this feature, stop and report it for separate triage.

## Canonical Mental Model And Required Cleanup

A session brief is one validated, model-derived interpretation of one ordinary
thread at one desired source generation. The source revision is the thread ID
plus its observer `updatedAt`; a manual refresh of an unchanged revision advances
the desired generation without changing the source revision. The coordinator
owns desired generations, leases/attempts, retry timing, and lifecycle. The
analyzer owns transient input and model I/O. The repository owns the last good
structured result and the compare-before-promote transaction.

The result is current only when all of these still match at promotion time:

1. source thread ID;
2. source `updatedAt`;
3. desired generation/token;
4. current recent-10 membership; and
5. the coordinator's active deletion/shutdown epoch.

Keep Slice 01's exact durable and public vocabulary:

- `src/shared/session-briefs.ts` remains the sole shared contract;
- `session_briefs` remains the last-good table;
- `session_brief_jobs` remains the one latest-job-per-thread table, with its
  `job_id` as the desired generation token;
- `analysisStatus` remains
  `queued | analyzing | ready | unavailable | failed`; and
- `freshness` remains `missing | current | stale`.

Do not store a `ready` job row. Successful promotion writes the validated
last-good row and deletes the matching job, allowing the service to derive
`analysisStatus: ready`. Persist successful real rows with generator
`codex_app_server` and `modelId: "gpt-5.6-sol"` so placeholder, transport, and
model provenance cannot be confused.

Failure metadata never replaces the last good structured fields. A source update
marks that result stale immediately. A successful current generation atomically
promotes the new structured result and clears its safe failure/retry state.
Obsolete completion is discarded without publishing ready.

Required cleanup and consolidation:

- Remove Slice 01's deterministic placeholder analyzer, its production wiring,
  and tests that assert placeholder copy.
- Delete every `session_briefs` row whose generator is
  `deterministic_placeholder`, clear any placeholder-era latest job, and
  reconcile the current selected revisions through real analysis. Preserve any
  non-placeholder validated last-good row. There must be no permanent
  placeholder/live dual branch.
- Do not retain a placeholder fallback when GPT-5.6 is unavailable; expose a
  truthful unavailable or failed lifecycle instead.
- Keep one canonical session-brief DTO, lifecycle vocabulary, repository, queue,
  refresh route, and SSE event. Do not introduce a second `summary`, free-text
  response, compatibility adapter, or model-specific browser contract.
- Generalize the current reporting-only App Server request seam and internal
  thread-creation buffering where necessary so reports and briefs share one
  narrow App Server client without sharing prompts, output schemas, persistence,
  or thread identities. Rename misleading reporting-only helpers rather than
  adding a duplicate client method for the same `thread/start`/`turn/start`
  protocol.
- Preserve the dedicated persistent reporting-thread workflow unchanged.
  Session-brief analysis always uses a new ephemeral thread and must never reuse
  or register the reporting thread.
- Extend the observer's internal-thread exclusion/buffering pattern for ephemeral
  analysis threads. A `thread/started` notification may arrive before
  `thread/start` resolves; buffer that creation window, register/exclude the
  returned ID before replay, and never project the analysis thread as an
  ordinary session, attention source, report fact, or recent-10 candidate.
- Use Slice 01's exact migration and repository shape. Add the next migration
  only if an implementation-critical attempt, retry-due, or generation field was
  intentionally left out of Slice 01; do not create a parallel queue database.

## Transient Transcript Extraction Contract

`thread/read` is called with the selected ordinary `threadId` and
`includeTurns: true`. The returned thread ID must equal the requested ID and its
turn collection must pass the established protocol shape guard. The complete
response exists only in the current request/job memory.

The extractor is a pure, fail-closed boundary:

1. Walk turns in source order and locate the earliest non-empty supported
   `userMessage` text item. That text is the first user intent.
2. Select the final six turns by source order, regardless of turn status.
3. Build the union of the first-intent turn and the final-six turn IDs. If the
   first-intent turn is already in the final six, render it once and mark its
   first supported user text as the intent.
4. For a first-intent turn outside the recent six, retain only its first
   supported user text; do not pull the old assistant/tool remainder into the
   request.
5. From the final six turns accept only plain text from `userMessage` text inputs
   and `agentMessage.text`. Preserve turn order, item order, and explicit
   `USER`/`ASSISTANT` plus stable turn-position labels.
6. Drop reasoning items and summaries, plans, command execution, file changes,
   tool/MCP calls and results, approval bodies, diffs, images, local-image paths,
   URLs, audio, arbitrary raw fields, hook prompts, protocol errors, and unknown
   content types. Do not stringify unsupported objects.
7. Drop credential-shaped structured fields such as token, password, secret,
   authorization, cookie, URL-userinfo, and environment maps by virtue of the
   text-only allowlist. Do not claim that arbitrary secrets embedded by the user
   inside otherwise supported chat text can be detected.
8. Normalize line endings and remove disallowed control characters without
   changing ordinary Unicode text.
9. Render deterministic section/role/turn labels and visible
   `[TRUNCATED …]` markers. Count with Unicode code points rather than JavaScript
   UTF-16 code units. The complete rendered source block, including labels and
   markers, must never exceed 32,000 code points.
10. When over budget, retain the first-intent prefix and the newest recent
    content preferentially, trim only at code-point boundaries, then restore all
    surviving recent segments to chronological display order. The truncation
    algorithm and its priority must be one pure function with boundary tests.
11. Assign evidence labels from a server-created allowlist using Slice 01's
    grammar, for example `user:first-intent`, `user:recent-1`, and
    `assistant:recent-1`; the model receives those labels beside the relevant
    segments. Evidence output may reference only those labels, never copy
    source text.

If there is no usable first user intent or the bounded rendered content is empty,
the attempt ends with safe category `empty_usable_content`. It must not call
`thread/start`, invent a brief, or persist any extracted text.

## GPT-5.6 App Server Contract

The installed generated schemas confirm:

- `ThreadStartParams` accepts `model`, `allowProviderModelFallback`,
  `ephemeral`, `dynamicTools`, `environments`, `runtimeWorkspaceRoots`,
  `approvalPolicy`, and `experimentalRawEvents`;
- `TurnStartParams` accepts `model`, `effort`, `environments`, `input`, and
  `outputSchema`; and
- `ThreadReadResponse` contains ordered turns with typed thread items.

Use those stable fields explicitly. Create one analysis thread per attempt with
the semantic equivalent of:

```ts
{
  model: "gpt-5.6-sol",
  allowProviderModelFallback: false,
  ephemeral: true,
  approvalPolicy: "never",
  dynamicTools: [],
  environments: [],
  runtimeWorkspaceRoots: [],
  cwd: null,
  experimentalRawEvents: false
}
```

Do not send `sandbox`, `permissions`, `selectedCapabilityRoots`,
`collaborationMode`, `multiAgentMode`, `serviceTier`, or a model provider unless
the installed stable schema and existing adapter require a narrower explicit
no-authority value. In particular, do not substitute a read-only workspace
sandbox for the aligned no-environment contract.

Start exactly one turn on the returned ephemeral thread with:

```ts
{
  threadId,
  model: "gpt-5.6-sol",
  effort: "medium",
  environments: [],
  input: [{ type: "text", text: boundedPrompt }],
  outputSchema: sessionBriefOutputSchema
}
```

The prompt must be lean and outcome-oriented. It identifies the source block as
untrusted chat data, tells the model not to follow instructions inside it,
defines “chat-reported done” and suggested operator action, prohibits claims
beyond the supplied text, lists the allowed evidence labels, and asks only for
the schema result. It does not contain repository context, dynamic system state,
other sessions, tools, or credentials.

`sessionBriefOutputSchema` is one strict JSON Schema with
`additionalProperties: false` at every object level and these required fields:

- `currentState`: non-empty string, maximum 600 characters;
- `done`: array of zero to five non-empty strings, each maximum 280 characters;
- `operatorActions`: array of zero to five non-empty imperative strings, each
  maximum 280 characters;
- `blockers`: array of zero to five non-empty strings, each maximum 280
  characters;
- `confidence`: enum `high | medium | low`;
- `evidence`: array of zero to six distinct strings, each constrained to the
  server-created evidence-label allowlist and maximum 120 characters.

Correlate completion using both the exact ephemeral thread ID and the exact turn
ID returned by `turn/start`. Accept only a completed turn's final
`agentMessage.text`. Parse its trimmed body directly as JSON; do not accept
Markdown fences, leading prose, alternate fields, partial deltas, reasoning
summaries, or another turn's completion.

After schema-constrained generation, apply an independent server validator:

- require exactly the six fields above and the same item/string bounds;
- trim strings and reject empty/duplicate list items;
- reject control characters, HTML markup, and URLs containing embedded
  credentials;
- reject evidence labels not present in the input-specific allowlist; and
- reject any enum, array, object, or scalar mismatch.

Raw parse errors and App Server errors must be mapped to safe categories without
including the rejected value or source content. Validated output remains
model-derived; it is never promoted to operator-confirmed state.

## Background Coordinator, Retry, And Supersession Contract

Use an injected clock and timers. Do not use an untestable interval loop or a
second process.

- Subscribe to the observer's authoritative snapshot event and reconcile only
  after at least one successful connected inventory snapshot.
- Ask Slice 01's selection service for the literal newest 10 eligible sessions;
  do not independently reimplement runtime-first ordering.
- On an automatic source revision change, persist stale/desired state
  immediately, replace any older queued timer, and schedule eligibility for 30
  seconds after the latest observation.
- Maintain a maximum of two worker promises. Use a stable queue order: explicit
  refresh first, then due automatic/retry time, recent-10 recency, enqueue time,
  and thread ID as the final deterministic tie-breaker.
- Enforce at most one queued or analyzing job for a thread revision and desired
  generation. Repeated observer snapshots and repeated refresh clicks are
  idempotent.
- A manual refresh of an eligible unchanged revision advances its desired
  generation once and is immediately eligible at the front of the queue. A
  manual request while the same manual generation is queued/analyzing returns
  the existing state. A disconnected refresh queues nothing and returns the
  established safe unavailable response.
- Mark an attempt `analyzing` transactionally before transient `thread/read`.
  Increment the attempt count when the worker claims it, not when a timer is
  scheduled.
- Bound each model turn to two minutes independently of the ordinary App Server
  request timeout. Timeout must detach exact-turn listeners and ignore later
  completion.
- Retry only transient categories such as App Server disconnect/transport,
  service overload, or timeout. The first retry is due 30 seconds after failure;
  the second is due two minutes after the next failure. Three total attempts are
  therefore possible.
- Treat empty input, model refusal, unavailable requested Sol model, malformed
  source shape, invalid JSON/schema, and validation rejection as terminal for
  that generation. They remain manually retryable but do not silently switch
  models or analyzers.
- Map analyzer faults into Slice 01's one canonical public failure vocabulary:
  `observer_unavailable`, `source_missing`, `empty_usable_content`,
  `analysis_unavailable`, `timeout`, `refusal`, `invalid_output`, and
  `internal`. Transport disconnect/read failures become
  `observer_unavailable`; a missing/deleted source becomes `source_missing`; an
  unavailable requested Sol model becomes `analysis_unavailable`; restart
  interruption is recoverable job state rather than a new public category. Keep
  any finer retry classification process-local and never persist upstream
  messages.
- After any attempt, fill the next free worker slot even when another session
  failed. One slow or failed session must never block the other nine.
- When a source revision changes, advance the desired generation, cancel its
  queued retry/debounce timer, mark the last good result stale, and enqueue only
  the newest revision. A running obsolete attempt may finish in memory but may
  not promote or consume retry allowance for the new revision.
- When a thread leaves the recent-10 window, cancel its queued work and reject
  later promotion. Slice 01's 24-hour grace retention remains responsible for
  pruning its stored last good brief.

The final repository operation must use a transaction/conditional update that
checks revision, desired generation/token, membership, lifecycle lease, and
active coordinator epoch at write time. An in-memory check before the database
write is insufficient.

## Restart, Shutdown, And Deletion Safety

At startup, use Slice 01's repository recovery to convert every orphaned
`analyzing` job to queued, clear its start time, retain its attempt count and
last-good brief, and avoid inventing a new failure category. Reconcile persisted
queued/retry-due rows only after the observer's first usable connected snapshot.
A newer inventory revision supersedes recovered old work before any worker
starts. No row may remain permanently analyzing after a process restart.

Integrate the brief coordinator into the existing application lifecycle:

- Start it before or alongside observer startup in a waiting state, then begin
  selection only on the usable observer snapshot.
- `stopAndDrain` first stops accepting refresh/reconcile work, unsubscribes from
  observer events, clears debounce/retry timers, advances/cancels the active
  coordinator epoch, and aborts exact pending App Server calls/listeners.
- Local cancellation does not send `turn/interrupt` or any ordinary-thread
  mutation. Late protocol responses are ignored.
- Await every worker promise after cancellation before closing SQLite.
- App shutdown stops/drains briefs before stopping the observer connection and
  closing the database.
- Privacy delete-day/delete-all enters the existing `WriteCoordinator`
  exclusive section, stops/drains briefs before the deletion transaction, then
  restarts the coordinator in a waiting state and reconciles only from the
  post-delete observer snapshot.
- The delete transaction and conditional promotion share the same generation
  and coordinator-epoch guard, so a finishing job cannot recreate a deleted
  brief, job row, exclusion, or export record.
- Delete-all removes all brief state and resets no hidden in-memory queue.
  Relevant day deletion follows the Slice 01 ownership rule and cannot be
  repopulated by a pre-delete result.

If the existing App Server client cannot detach/abort a pending request safely,
extend its pending-call correlation with an optional `AbortSignal`. Aborting
must clear the request timeout, reject with a safe local error, remove the
pending entry, and ignore any later response ID. Do not terminate or recreate
the observer solely to approximate per-job cancellation.

## Privacy And Data-Boundary Proof

Only these analysis products may cross the durable boundary:

- validated `currentState`, `done`, `operatorActions`, `blockers`,
  `confidence`, and evidence labels;
- source thread ID and `updatedAt`;
- desired generation, lifecycle, attempt count, retry-due time, generated/stale
  timestamps, explicit model ID `gpt-5.6-sol`, and safe failure category; and
- bounded operational counters already approved by Slice 01.

The following remain request/process-local and must never enter SQLite, logs,
API/SSE DTOs, export, diagnostics, browser state, fixtures copied from real
sessions, exception messages, or test snapshots:

- complete or partial source transcript text;
- the rendered prompt/source block;
- raw model output before validation;
- App Server request/response/notification envelopes;
- reasoning, command/tool payloads, diffs, paths from unsupported items,
  credentials, or protocol previews.

Do not add a debug mode that logs prompts or raw output. Fastify request logging
must not serialize model parameters. Errors must be categorized at the boundary
and tested with synthetic secret markers. Export and retained-count support are
owned by Slice 01; Slice 02 must prove that successful, failed, retried,
superseded, restarted, and deleted attempts do not expand those DTOs.

## Likely Files, Modules, Components, Commands, And Tests

Extend the actual Slice 01 paths if their final names differ. Do not create
parallel contracts.

Likely additions:

- `apps/codex-daily/src/server/briefs/session-brief-input.ts` — pure
  first-intent/recent-six allowlist, rendering, truncation, and evidence labels
- `apps/codex-daily/src/server/briefs/session-brief-output.ts` — strict
  `outputSchema`, parse, and independent validation
- `apps/codex-daily/src/server/briefs/session-brief-gateway.ts` — ephemeral
  GPT-5.6 thread/turn lifecycle and exact completion correlation
- `apps/codex-daily/src/server/briefs/session-brief-coordinator.ts` — observer
  reconciliation, debounce, two-worker queue, retry, supersession, and drain
- focused tests under
  `apps/codex-daily/test/server/briefs/`

Likely modifications:

- Slice 01's canonical shared session-brief types, repository, service, routes,
  SSE publisher, and placeholder analyzer wiring
- `apps/codex-daily/src/server/codex/app-server-client.ts`
- `apps/codex-daily/src/server/codex/app-server-protocol.ts`
- `apps/codex-daily/src/server/codex/observer-service.ts`
- `apps/codex-daily/src/server/reports/observer-reporting-gateway.ts`
- `apps/codex-daily/src/server/reports/reporting-thread.ts` only where needed to
  preserve the renamed shared App Server seam
- `apps/codex-daily/src/server/app.ts`
- `apps/codex-daily/src/server/startup.ts` only for bounded configuration that
  is not a product preference
- `apps/codex-daily/src/server/privacy/privacy-service.ts`
- `apps/codex-daily/src/server/diagnostics/diagnostics-service.ts` only for safe
  counters/categories already established by Slice 01
- the next numbered migration only if Slice 01 did not include a required
  generation/attempt/retry field
- `apps/codex-daily/test/fixtures/fake-codex-app-server.py`
- existing App Server client, observer, reporting gateway, privacy, lifecycle,
  route, repository, and diagnostics tests

No new production client component is expected in this slice. Slice 01's client
API test may be updated only if it asserts placeholder behavior; Slice 03 owns
the canonical frontend.

Use the current scripts: `npm run lint`, `npm run typecheck`, `npm test`,
`npm run build`, `npm run test:e2e`, and `npm run check`. Do not add another
package manager, lockfile, database library, queue process, model SDK, or
application root.

## Existing Patterns To Follow

- The current testable-core/thin-entry-point architecture and explicit
  dependency injection for clocks, timers, process factories, and database
  paths.
- `AppServerClient` JSONL framing, monotonic request IDs, correlation, timeout,
  bounded stderr diagnostics, fixed executable/arguments, and initialized
  lifecycle.
- `ObserverService` as the sole owner of the connected App Server client,
  request-scoped `thread/read`, exact known-event normalization, and buffered
  exclusion before internal-thread projection.
- `ReportingThreadNarrativeProvider` as evidence that generated work can retain
  only validated output while transient source messages remain request-local.
  Share the narrow transport pattern, not its persistent reporting thread,
  prompt, Markdown-fence compatibility, or suggestion schema.
- Prepared synchronous SQLite statements, explicit `BEGIN IMMEDIATE`
  transactions, migration idempotence, injected temporary databases, and
  compare-before-write behavior.
- `WriteCoordinator` exclusivity and the application `pauseWriters` /
  `resumeWriters` lifecycle for destructive local-data work.
- EventEmitter-backed server updates and typed HTTP/SSE DTOs. Publish canonical
  repository state, not raw protocol events or queue implementation details.
- Deterministic Python fake App Server for protocol integration, combined with
  pure Vitest fixtures for extraction, scheduling, validation, and database
  races.

## Behavior That Must Not Regress

- Ordinary Codex threads remain read-only. The only ordinary-session App Server
  method added is transient `thread/read`.
- Observer inventory, live state, task links, per-thread detail, reporting-thread
  exclusion, request-episode identity, reconnect, pagination, and cached
  disconnected behavior remain intact.
- The dedicated daily reporting thread remains durable and excluded, and evening
  factual reports/narratives retain their existing lifecycle and timeout
  behavior.
- Needs You remains deterministic and does not consume model-derived operator
  actions or blockers.
- Morning planning and operator-confirmed completion semantics do not change.
- A stale or failed refresh never erases the last good brief.
- The browser/API remains useful from cached structured state while Codex is
  disconnected; manual analysis does not falsely claim to have queued work.
- Loopback Host/Origin enforcement, no-store transient detail responses, local
  SQLite, inspect/export/delete controls, automatic-report scheduling, graceful
  shutdown, and existing diagnostics remain intact.
- No raw transcript, prompt, response, reasoning, tool payload, or credential is
  retained or streamed.
- No `buddy_*`, ROS contract, launch, configuration, or runtime file changes.

## Acceptance Criteria

1. A pure extractor selects the earliest supported user intent and the six most
   recent turns, deduplicates an overlapping intent turn, preserves chronological
   role-labelled content, drops every unsupported item type, and returns no more
   than 32,000 Unicode code points including deterministic truncation markers.
2. Empty or unsupported-only input ends safely as `empty_usable_content` without
   creating an analysis thread or writing source content.
3. The fake App Server proves every analysis `thread/start` explicitly uses
   `model: "gpt-5.6-sol"`, `allowProviderModelFallback: false`,
   `ephemeral: true`, empty dynamic tools/environments/workspace roots, no
   ordinary-chat mutation authority, and no experimental raw events.
4. The fake proves every analysis `turn/start` explicitly uses
   `model: "gpt-5.6-sol"`, `effort: "medium"`, empty environments, a text-only
   bounded prompt, and the strict six-field `outputSchema`.
5. The analyzer correlates the exact returned thread and turn, parses only the
   final assistant JSON, independently validates all field/item/character/evidence
   limits, and rejects prose, fences, extra fields, invalid enums, HTML,
   credential-bearing URLs, malformed JSON, partial events, and another turn's
   completion.
6. Successful analysis persists only the canonical structured result, source
   revision/generation, lifecycle/timestamps, model ID, attempts, and safe
   counters. Synthetic transcript, prompt, raw output, reasoning, and protocol
   markers are absent from SQLite, logs, API, SSE, export, diagnostics, and
   browser DTOs.
7. Automatic source changes become stale immediately, debounce for 30 seconds,
   coalesce repeated revision events, and run with exactly two maximum concurrent
   workers. A third eligible job waits while completed/failed jobs release slots.
8. Manual all-session/per-session refresh prioritizes eligible work immediately,
   respects concurrency, reanalyzes an unchanged revision once, and remains
   idempotent while that desired generation is queued or analyzing. Disconnected
   refresh queues nothing and reports unavailable truthfully.
9. A transient failure gets at most two retries, due after 30 seconds and two
   minutes. Terminal validation/refusal/unavailable-model faults do not
   auto-retry, never trigger fallback, and do not block other sessions.
10. A newer revision, newer manual generation, window exit, coordinator stop, or
    delete epoch supersedes an in-flight result. Tests pause immediately before
    promotion and prove the obsolete result cannot become current or recreate
    deleted data.
11. A failed/unavailable refresh preserves the previous validated brief as stale.
    A later valid current result atomically replaces it and clears failure/retry
    metadata.
12. Restart converts orphaned analyzing work to recoverable queued/stale state,
    retains its last good result and retry budget, waits for a usable observer
    snapshot, and never leaves a permanent analyzing row.
13. Shutdown, delete-day, and delete-all stop accepting work, clear all timers,
    cancel/detach exact pending App Server work, drain worker promises before
    SQLite closes or deletes, and resume from clean post-delete state without a
    late write.
14. Ephemeral analysis threads are excluded before buffered creation events are
    projected and never appear in observer inventory, attention, reports,
    recent-10 selection, exports, or ordinary session cards.
15. Slice 01's read/refresh/SSE contract now exposes real background lifecycle
    changes without a page reload and without a second DTO or placeholder
    fallback.
16. Existing observer, morning planning, Needs You, report generation,
    reporting-thread behavior, privacy operations, diagnostics, production
    build, browser tests, and ROS repository boundaries continue to pass.

## Ordered Implementation Tasks

1. Confirm Slice 01 is implemented and its status block is verified. Map its
   exact shared DTO, repository, selection, coordinator seam, API/SSE, refresh
   intent, retention, export, deletion, and placeholder analyzer. Stop on a
   conflicting lifecycle or missing generation/conditional-promotion contract.
2. Add failing pure tests for first-intent discovery, final-six selection,
   overlap deduplication, ordering, supported text variants, every dropped item
   family, credential-shaped structured fields, empty input, Unicode/code-point
   boundaries, deterministic truncation markers, evidence labels, and the exact
   32,000-character cap.
3. Implement the pure transient extractor/renderer with no repository or logger
   dependency. Inspect fixtures and thrown errors to prove raw content cannot
   escape its return-to-gateway call chain.
4. Add failing output-schema and validator tests for all required fields,
   additional properties, enum/list/string limits, unique evidence labels,
   input-specific evidence allowlists, control characters, HTML,
   credential-bearing URLs, raw JSON only, and safe error messages.
5. Extend/generalize the App Server client and observer internal-generation seam:
   optional abortable correlation if required, buffered exclusion of an internal
   ephemeral thread, exact thread/turn completion demultiplexing, and safe error
   categorization. Preserve the persistent report-thread path and rename
   superseded reporting-only transport helpers.
6. Extend the deterministic fake App Server with synthetic ordinary turn
   histories and controllable analysis success, slow completion, timeout,
   disconnect, refusal/no-final-message, unavailable model, malformed result,
   wrong thread/turn completion, and late completion. Capture method/parameter
   metadata only in the test harness needed to assert the model contract; never
   copy real chats into fixtures.
7. Implement the GPT-5.6 gateway with the exact ephemeral thread parameters,
   lean untrusted-source prompt, explicit medium turn, strict `outputSchema`,
   two-minute abortable completion wait, final-message-only parser, independent
   validation, and request-local disposal of input/raw output.
8. Add fake-clock coordinator tests for initial usable-snapshot gating,
   30-second debounce/coalescing, deterministic priority, two-worker saturation,
   manual front-of-queue refresh/idempotence, transient retry at 30/120 seconds,
   terminal failure isolation, disconnect/reconnect, and timer cleanup.
9. Implement the coordinator using Slice 01's repository/service contract.
   Claim attempts transactionally, preserve last good data, fill free worker
   slots, and use one conditional promote/fail/retry operation keyed by source
   revision, desired generation, recent membership, lease, and coordinator epoch.
10. Add controlled-race repository/integration tests for source revision changes,
    manual generations, recent-window exit, retry supersession, late completion,
    last-good preservation, and exactly-once current promotion.
11. Wire startup recovery and application lifecycle. Add temporary-file SQLite
    restart tests for orphaned analyzing rows and post-inventory reconciliation.
    Add shutdown and privacy delete-day/delete-all race tests proving all workers
    drain/cancel and no deleted state is recreated.
12. Replace the Slice 01 placeholder analyzer and its assertions. Route existing
    manual refresh and SSE publication through the real coordinator; remove
    obsolete fallback names, fixtures, response shapes, and duplicate transport
    helpers.
13. Add privacy assertions across success, invalid output, retry, supersession,
    restart, and deletion: scan the database/export/API/SSE/diagnostics and
    captured logs for synthetic transcript, prompt, reasoning, raw-output, tool,
    path, and credential markers.
14. Run focused and full verification, inspect the exact diff for protected and
    unrelated paths, update only this plan's implementation status after success,
    and report any deviation without expanding scope.

## Verification And Expected Outcomes

From `apps/codex-daily/`:

```bash
npm run lint
npm run typecheck
npm test -- --run test/server/briefs
npm test -- --run test/server/codex/app-server-client.test.ts test/server/codex/observer-service.test.ts test/server/reports
npm test -- --run test/server/privacy test/server/runtime
npm test
npm run build
npm run test:e2e
npm run check
```

Expected:

- lint and both TypeScript projects pass;
- extractor/output/coordinator tests prove the exact content cap, strict schema,
  scheduling, retries, supersession, and last-good behavior with injected time;
- deterministic fake App Server tests prove explicit Sol/medium/ephemeral/no
  fallback/no tools/no environment and exact completion correlation;
- restart/deletion tests prove no orphaned analyzing state or late writes;
- observer/reporting regressions prove the shared App Server seam did not alter
  ordinary observation or daily narratives;
- privacy scans find none of the synthetic secret/source/raw-output markers in
  retained or published surfaces;
- all unit/component/integration tests, production build, and the existing
  browser suite pass; and
- the aggregate `check` exits zero.

From the repository root:

```bash
git diff --check
git diff --name-only -- 'buddy_*' docs/contracts
python3 -m pytest buddy_bringup/test/test_repository_contracts.py
git status --short
```

Expected: no whitespace errors; no ROS or frozen-contract diff; repository
contract tests pass; status contains only intended Codex Daily/session-brief
files, this plan's implementation-status update, and untouched pre-existing user
changes.

Do not use a real ordinary session to prove transcript handling in this slice.
The fixture must provide synthetic marker content and record enough protocol
metadata to assert exact parameters and maximum concurrency deterministically.

## Risks And Dependencies

- Slice 01 may choose different names or schema columns. Extend its canonical
  contract and update this plan's final summary with the actual paths; do not
  create an alternate lifecycle or queue.
- App Server notifications can precede `thread/start` resolution. Reuse/generalize
  the established creation buffer and inventory lock so an ephemeral analysis
  thread is never briefly projected.
- Two simultaneous turns share one JSONL client. Correlate both thread and turn,
  attach/remove listeners deterministically, and test crossed and late events.
- JavaScript string length is UTF-16 code units, not Unicode characters. Use one
  explicit code-point counter/slicer and include labels/markers in the cap.
- Prompt injection remains possible inside source chat text. Treat it as
  delimited untrusted data, give the analysis thread no tools/environment, use a
  strict output schema, and independently validate; do not claim perfect semantic
  resistance.
- App Server structured output constrains the final message but does not replace
  server validation. Never promote the raw value directly.
- In-memory debounce/retry timers can disappear on restart. Durable lifecycle,
  attempt, desired-generation, and retry-due state must be sufficient to
  reconcile after a fresh usable observer snapshot.
- SQLite is synchronous while model work is asynchronous. Keep transactions
  short and perform no App Server call inside a transaction.
- Deletion can race after model completion but before promotion. The final
  transaction must check a durable generation/epoch guard, and lifecycle drain
  must finish before the database is closed.
- The requested model may not be available in a future local catalog. That is a
  visible `analysis_unavailable` failure, not authority to use another model.
- Ten Sol analyses can be slow or capacity-limited. The fixed input cap,
  two-worker limit, debounce, timeout, and retry ceiling are product constraints,
  not tuning suggestions to bypass.

## Stop Conditions And Blocked Behavior

Stop and report rather than improvise when:

- Slice 01 is not implemented/verified or lacks a viable conditional-promotion,
  refresh-intent, retention, deletion, or SSE ownership seam.
- The installed stable App Server schema no longer supports explicit
  `gpt-5.6-sol`, `effort`, `ephemeral`, fallback control, empty environments, or
  `outputSchema`.
- Enforcing no environment/tools would require granting workspace, sandbox,
  shell, MCP, dynamic-tool, or ordinary-thread mutation authority.
- Safe internal-thread exclusion cannot be guaranteed before observer
  projection.
- A two-worker gateway cannot correlate exact turns on the existing client
  without a broad protocol rewrite.
- Restart/deletion safety would require storing source content, retaining raw
  output, or allowing a late write after coordinator cancellation.
- Implementation requires a second provider/API key, a new queue/database
  dependency, changes outside `apps/codex-daily/` and this pipeline status, or
  protected ROS changes.
- Required tests or verification commands cannot run, the selected slice becomes
  larger than the backend analysis lifecycle above, or existing behavior fails
  for reasons that cannot be isolated.

When blocked, preserve the worktree and report the exact command/evidence, the
smallest conflicting contract, whether any transient content reached a durable
surface, and the minimum design/alignment decision required. Do not add a
fallback model, placeholder result, compatibility DTO, or weakened assertion.

## Preserve Unrelated Changes

Inspect `git status` before editing, before verification, and before committing.
The existing UX catalogue and other slice-plan drafts may be concurrent planning
work. Do not revert, reformat, stage, or include another agent's or the user's
changes.

Limit implementation to the existing Codex Daily application, tests/fixture
needed for this slice, and this plan's status update. Never use destructive
cleanup on untracked files, the user's Codex storage, real session history, or
temporary databases not created by the slice. Do not modify `buddy_*`,
`docs/contracts`, unrelated pipeline folders, or root ROS behavior.

## Expected Final Summary

The implementing agent must report:

- **Implemented:** transient extractor, strict output validator, exact GPT-5.6
  gateway, two-worker coordinator, retry/supersession/restart behavior,
  lifecycle wiring, and required canonical cleanup with exact major paths.
- **Model contract proof:** evidence for `gpt-5.6-sol`, medium effort,
  ephemeral thread, strict `outputSchema`, no fallback, no tools/environment,
  exact thread/turn correlation, and zero ordinary-thread mutations.
- **Privacy proof:** the synthetic markers checked and every SQLite, log,
  API/SSE, export, diagnostics, restart, supersession, and deletion surface
  shown not to retain raw source/prompt/output.
- **Verification:** every focused and full command with pass/fail counts,
  fake-clock timing/concurrency evidence, temporary-store restart/deletion
  evidence, browser regression result, and ROS boundary result.
- **Deviations:** differences from this contract, or `None`.
- **Follow-ups:** stable IDs only, or `None`; `FUP-001` through `FUP-005` remain
  deferred.
- **Unrelated changes preserved:** pre-existing/concurrent paths left untouched.
- **Implementation status:** commit hash and confirmation that the status block
  above was updated to `implemented`, or the exact blocker and retained
  evidence.
