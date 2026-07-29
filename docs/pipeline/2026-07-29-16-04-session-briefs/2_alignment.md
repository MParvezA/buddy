# Codex Daily — Recent Session Briefs Alignment

## Short Feature Name

Recent Session Briefs

Pipeline folder:
`docs/pipeline/2026-07-29-16-04-session-briefs/`

## Aligned Product Contract

Codex Daily will continuously maintain structured GPT-5.6 briefs for the 10 most
recent eligible ordinary Codex sessions. The brief is an orientation layer over
factual observer metadata, not a replacement for the chat, task plan, Needs You,
or daily report.

The operator has explicitly approved transient model access to recent chat
content under the design's retention boundary and requested that the feature be
implemented and left running for review the following day.

## Final Decisions

### Recent-session window

- Select exactly the newest 10 eligible top-level, non-archived sessions by
  `recencyAt`, falling back to `updatedAt`.
- Exclude the dedicated reporting thread, ephemeral analysis threads, subagents,
  and locally excluded sessions.
- Runtime state does not change ordering ahead of recency; “recent 10” has one
  literal meaning.
- When fewer than 10 eligible sessions exist, show all available sessions.

### Source revision and freshness

- A session revision is the observer's stable thread ID plus its current
  `updatedAt`.
- A ready brief is current only when its source revision matches.
- A newer revision immediately labels the previous brief stale but keeps it
  readable while refresh runs.
- A result generated for a superseded revision is discarded.
- Manual refresh may reanalyze an unchanged revision and records a new generation
  time; it never mutates the ordinary source thread.

### Transcript input boundary

- The worker transiently reads the first user intent plus the six most recent
  turns.
- Rendered input is capped at 32,000 Unicode characters per session.
- Preserve chronological order, visible role labels, and truncation markers.
- Strip unsupported content types, tool payloads, raw protocol fields, secrets
  from known credential-shaped fields, and assistant reasoning.
- If bounded usable text is empty, fail that session safely without inventing a
  brief.
- Input exists only in request/process memory and the ephemeral model request.

### GPT-5.6 execution contract

- Use explicit model `gpt-5.6-sol`.
- Use explicit medium reasoning effort.
- Create an ephemeral App Server analysis thread per job.
- Disable provider-model fallback; a missing requested model is a visible failure.
- Provide no dynamic tools, no workspace environment, and no authority to mutate
  source sessions.
- Use a strict output schema on `turn/start`; parse only the final assistant JSON.
- Do not use Pro mode, multi-agent mode, tools, prompt caching controls, or another
  API/provider in this feature.

### Structured brief

Each current result contains:

- `currentState`: one short paragraph;
- `done`: zero to five concise items;
- `operatorActions`: zero to five concise, imperative items;
- `blockers`: zero to five concise items;
- `confidence`: `high`, `medium`, or `low`;
- `evidence`: zero to six bounded labels referencing source roles/turn positions,
  never copied transcript excerpts.

Each field has server-side item and character limits. Extra fields, HTML, URLs
with embedded credentials, or invalid enums reject the result.

“Done” always appears as **chat-reported done**, never as operator-confirmed task
completion. Operator actions remain suggestions and do not enter Needs You or the
morning plan automatically.

### Background scheduling

- Start selection only after the observer has a usable snapshot.
- Debounce source revisions for 30 seconds to avoid summarizing active churn.
- Analyze at most two sessions concurrently.
- Use a two-minute model timeout.
- Retry a transient failure at most twice: after 30 seconds and then two minutes.
- Never run more than one job per thread revision.
- Manual refresh moves eligible work to the front but respects concurrency.
- On startup, recover orphaned `analyzing` work to queued/stale and resume.
- On shutdown and destructive local-data operations, stop accepting new work and
  drain or cancel bounded in-flight analysis before closing SQLite.

### Retention

- Persist only the last good structured brief, lifecycle/failure metadata, source
  revision, generation timestamps, model ID, and safe counters.
- Never persist prompts, transcript text, final raw model output, reasoning, or App
  Server envelopes.
- Keep briefs for the current recent-10 window.
- A brief that leaves the window receives a 24-hour grace period, then is pruned.
- Thread exclusion, delete-all, and relevant day deletion remove associated brief
  state consistently.
- Export includes structured briefs and lifecycle metadata only.

### UI hierarchy and interaction

- Priority 01 remains Needs You.
- Priority 02 remains today's outcomes and progress.
- Priority 03 becomes **Recent session briefs** and replaces “Active and recent
  Codex chats” as the canonical session-card section.
- Priority 04 remains recently completed factual turn activity.
- The section contains at most 10 cards, newest first, at both desktop and 390px.
- Every card keeps factual title, source, working directory, runtime status,
  recency, links, and outcome-link controls.
- Derived content is grouped under:
  - **Going on**
  - **Chat-reported done**
  - **What you should do**
  - **Blockers**
- Each card visibly labels `GPT-5.6 derived`, confidence, generated time, and
  current/stale lifecycle.
- Pending cards use stable skeleton/status content without hiding factual metadata.
- Failed/unavailable cards retain the last good brief when present and offer a
  per-session retry.
- The section header offers **Refresh 10 briefs**, reports aggregate progress, and
  remains keyboard accessible.
- Live updates arrive without a full page reload.

### API and ownership

- Session briefs have their own read API, manual-refresh mutation, and SSE stream.
- They do not enter the factual observer snapshot or attention DTOs.
- The brief coordinator owns selection, queueing, retries, supersession, and model
  lifecycle.
- The observer owns ordinary-session discovery and request-scoped thread reads.
- The repository owns durable structured state and pruning.
- The browser never calls GPT or receives source transcript input.

## Rejected Alternatives

- A persistent all-session analysis chat is rejected for retention and
  cross-session isolation.
- A single 10-session batch is rejected for refresh cost and failure coupling.
- Browser-side generation and a separate OpenAI API integration are rejected.
- Automatically converting suggested actions into Needs You or morning tasks is
  rejected because it would confuse model inference with operator intent.
- Runtime-first ordering is removed from the replaced recent-session section;
  literal recency is the canonical selection rule.

## Explicit Non-Goals

- Ordinary-chat writes, approvals, prompts, archives, or task completion.
- More than 10 briefs, configurable model choice, or configurable analysis depth.
- Daily-report narrative integration or weekly synthesis.
- External notifications, accounts, synchronization, or third-party systems.
- Repository inspection, Git evidence, or test-result verification beyond what
  the source chat itself states.

## Deferred Scope And Follow-Up Candidates

| ID | Item | Why Deferred | Follow-Up Trigger |
| --- | --- | --- | --- |
| FUP-001 | User-tunable session count | Ten is the explicit request and bounds cost | Repeated use demonstrates another useful window |
| FUP-002 | Per-session analysis depth | One bounded input policy protects privacy and latency | Brief quality shows repeatable missing context |
| FUP-003 | Weekly cross-session synthesis | Daily orientation must prove useful first | At least one week of reliable briefs exists |
| FUP-004 | External notifications | Delivery adds auth and interruption policy | A reliable in-app briefing exists and a channel is chosen |
| FUP-005 | Automatic ordinary-chat actions | This changes monitor trust and permissions | Explicit action semantics and approvals are designed |

## Product Behavior And UX Expectations

- Facts remain useful before and without generated interpretation.
- The card never collapses into a generic AI paragraph; operator action is a
  first-class, scannable field.
- Empty lists say “No action inferred” or “No blocker inferred,” not an
  authoritative “none.”
- Confidence communicates model certainty, not completion certainty.
- Staleness is based on source revision, not elapsed wall time alone.
- A disconnected observer leaves prior briefs and factual cards readable.
- Manual refresh feedback includes queued/running counts and does not permit
  duplicate clicks to create duplicate jobs.
- Keyboard focus remains on the initiating control after a refresh action.
- Status meaning is communicated with text and icons, never color alone.

## Edge Cases And Failure Behavior

- One failed session never blocks the remaining nine.
- New sessions can enter the recent window while older queued work is canceled.
- A source can update repeatedly while a job runs; only the newest revision may
  become current.
- Missing or deleted threads yield pruned/missing state, never a ghost brief.
- Model refusal, invalid JSON, schema mismatch, timeout, or unavailable Sol remain
  distinct safe failure categories in diagnostics without raw content.
- A restart cannot leave an item permanently `analyzing`.
- Manual refresh while disconnected queues nothing and explains why.
- Delete/export operations coordinate with the worker so deleted data cannot be
  recreated from a finishing job.

## Canonical Mental Model And Required Removals

- Rename the user-facing “Active and recent Codex chats” concept to “Recent
  session briefs.”
- Remove the 20-card runtime-first selection policy from the Today view.
- Keep one session card implementation; do not leave a second metadata-only list.
- Keep one structured brief schema and lifecycle; no legacy free-text summary
  field or compatibility response.
- Do not overload report narratives or attention items to represent session briefs.

## Roadmap-Level Vertical Slices

1. **Brief Contract And Storage** — schema, lifecycle, privacy, retention, APIs,
   deletion, export, and restart-safe ownership.
2. **GPT-5.6 Background Analysis** — transient input extraction, ephemeral Sol
   gateway, queueing, retry, supersession, and failure isolation.
3. **Recent Sessions Frontend** — canonical 10-card UI, live states, action lists,
   manual refresh, responsive and accessible behavior.
4. **Operational Proof** — full lifecycle, privacy, host model contract, restart,
   deletion, regression, and browser evidence.

## Acceptance Criteria

- The 10 newest eligible sessions appear in literal recency order.
- Every card remains factually useful before analysis finishes.
- Ready cards answer what is happening, what the chat reports done, and what the
  operator should do.
- Generated claims are visibly derived and never confirm user-owned completion.
- A source update makes the old brief stale and eventually replaces it without
  duplicate work.
- Background analysis uses explicit GPT-5.6 Sol, medium effort, ephemeral threads,
  strict structured output, two-worker concurrency, and bounded retry/timeout.
- Only the approved bounded recent content enters request memory; no raw content
  reaches storage, SSE, export, diagnostics, browser state, or logs.
- The last good brief survives disconnects, generation failure, and restart.
- Manual refresh and per-session retry are truthful and idempotent.
- Delete-all and relevant local deletion cannot race with a finishing model job.
- Existing morning planning, Needs You, reporting, diagnostics, and read-only
  ordinary-chat boundaries do not regress.
- Desktop and 390px browser workflows prove loading, live success, failure/stale,
  manual refresh, keyboard use, and no horizontal overflow.

## Risks That Shape Planning And Testing

- App Server ephemeral/history behavior must be proven against the installed
  schema and a deterministic fixture.
- Turn-body extraction is a sensitive parser boundary and must default to dropping
  unsupported content.
- Background completion races with newer revisions and deletion require
  generation-token checks inside the final write transaction.
- Ten Sol jobs can consume time/capacity; concurrency, debounce, input caps, and
  explicit manual behavior must remain enforced.
- Dev launches inside a restricted filesystem sandbox cannot initialize Codex;
  host-context runtime verification is required.
- The existing deterministic fake App Server must be extended without copying real
  ordinary-chat content into tests.

## Remaining Open Questions

None blocking planning. Operational defaults above are approved assumptions made
under the user's instruction to implement and leave the app running for review
tomorrow.

## UX Catalogue Updates

Added **Generated Operational Briefs** to
`docs/about/05_ux_decision_catalogue.md`. Existing Human-Confirmed Completion,
Attention Before Activity, Minimal Local Retention, and Facts Before Generated
Interpretation decisions already cover the remaining reusable behavior. No
catalogue conflict was found.

## Repository Rules

- Consulted: `1_design.md`, the existing UX catalogue, archived Codex Daily
  design/alignment/review, app README, and current observer/client contracts. No
  `docs/rules/README.md` exists.
- Constraints applied: attention before activity, human-confirmed completion,
  minimal local retention, facts before generated interpretation, loopback-only
  security, and protected ROS paths.
- Rule updates: None.
