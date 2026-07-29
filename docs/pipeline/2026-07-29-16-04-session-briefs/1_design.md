# Codex Daily — Recent Session Briefs Design

## Goal

Turn the 10 most recent ordinary Codex sessions into a continuously refreshed,
action-oriented briefing inside Codex Daily. Each session should explain:

- what is going on now;
- what has been done;
- what the operator is supposed to do next.

The target operator is the local Codex user returning to active work after hours
or overnight and needing a fast, trustworthy orientation without rereading chats.

## Success Criteria

- The Today view shows exactly the 10 most recent eligible sessions, newest first.
- Each session has concise structured fields for current state, completed work,
  operator actions, blockers, confidence, and freshness.
- GPT-5.6 Sol performs analysis in the background without blocking planning,
  attention, reporting, or cached observer data.
- Session updates invalidate stale briefs and trigger bounded, debounced refresh.
- The operator can manually refresh all briefs and see queued, analyzing, ready,
  stale, unavailable, and failed states truthfully.
- Raw transcript content is never written to Codex Daily storage, logs, SSE,
  exports, diagnostics, or browser caches.
- Restarting Codex Daily preserves the last structured briefs and resumes stale
  work safely.

## Non-Goals

- Automatically sending prompts, approving actions, or changing ordinary chats.
- Claiming that model-inferred completion is operator-confirmed task completion.
- Analyzing more than the 10 most recent eligible top-level sessions.
- Persisting raw turns, assistant reasoning, or model prompts.
- Cross-device sync, external notifications, or third-party task integrations.
- Replacing the factual daily report or the existing Needs You engine.

## Deferred Scope And Follow-Up Candidates

| ID | Item | Why Deferred | Follow-Up Trigger |
| --- | --- | --- | --- |
| FUP-001 | User-tunable session count | Ten is the explicit product request and keeps cost bounded | Repeated use shows a need for a different window |
| FUP-002 | Per-session analysis depth | One bounded recent-content policy is safer for the first version | Operators need full-history or repository-aware reconstruction |
| FUP-003 | Weekly cross-session synthesis | Daily session orientation should prove useful first | At least one week of reliable briefs exists |
| FUP-004 | External notifications | Delivery channels add authentication and interruption policy | The in-app briefing is reliable and a channel is explicitly chosen |
| FUP-005 | Automatic ordinary-chat actions | This would change the app from monitor to controller | Read-only trust is established and action approvals are designed |

## Constraints And Assumptions

- The existing loopback-only, local SQLite, read-only architecture remains.
- The installed Codex App Server is the model and transcript-access boundary; no
  separate OpenAI API key is required.
- The analysis target is explicitly `gpt-5.6-sol` with medium reasoning.
- Official GPT-5.6 guidance favors explicit model/effort selection and lean,
  outcome-oriented prompts with structured success criteria.
- Installed App Server schemas support `model`, `effort`, ephemeral threads, and
  an output schema for `turn/start`.
- Ordinary session content may be fetched transiently only for the selected 10
  sessions and only while analysis is running.
- The last good structured brief remains visible when Codex or the model is
  unavailable.
- Existing standalone-history capability limits still apply: background briefs
  summarize observable stored sessions, while another process's live approval
  events remain the responsibility of Needs You/shared-live mode.

## Canonical Mental Model

A **session brief** is a model-derived, structured interpretation of one observed
Codex session at a known source revision. It is not the chat, not a task record,
not an attention item, and not proof of completion.

Each brief carries:

- source thread identity and revision;
- generated and stale timestamps;
- analysis lifecycle;
- current-work summary;
- completed-work summary;
- operator-action list;
- blocker list;
- confidence and bounded evidence labels.

The frontend presents model-derived language distinctly from factual observer and
operator-owned task state. “Done” means the chat indicates work was done; it does
not mark a morning outcome complete.

The superseded concept is the current metadata-only recent-session card. The new
card keeps factual metadata but adds one canonical brief state rather than a
separate AI panel or duplicate chat list.

## Selected Approach

Use a background session-brief service behind the existing observer:

1. Select the newest 10 eligible, non-reporting, top-level sessions.
2. Detect which source revisions lack a current brief.
3. Fetch bounded recent turns transiently through `thread/read`.
4. Create an ephemeral analysis thread pinned to `gpt-5.6-sol` and medium effort.
5. Request a strict JSON result for the session brief.
6. Validate and persist only the structured result and source revision.
7. Publish brief-state updates to the frontend and retain the last good result on
   refresh failure.

Analysis runs with a small concurrency limit, debounce, timeout, and retry bound.
Only one refresh per thread revision may be active. Newer revisions supersede
queued stale work.

## Rejected Alternatives

### Separate OpenAI Responses API integration

Rejected for this feature because it adds API-key management, a second auth and
model lifecycle, and a second transcript boundary when the local Codex App Server
already supports explicit model, effort, ephemeral threads, and structured output.

### One persistent analysis chat containing all 10 sessions

Rejected because it accumulates ordinary-chat content in another durable thread,
increases cross-session leakage risk, and makes per-session freshness and retry
ownership ambiguous.

### One giant batch prompt for all 10 sessions

Rejected as the canonical path because any single update would reprocess every
session, one malformed item could fail the whole briefing, and slow work would
delay all cards. Per-session jobs permit bounded concurrency and incremental
refresh while still allowing frontend ranking across the 10 results.

### Browser-side GPT calls

Rejected because secrets, transcript content, retries, concurrency, validation,
and persistence belong at the local service boundary.

## Architecture

The observer remains responsible for discovering eligible sessions and transient
thread reads. A new server-owned brief coordinator subscribes to observer
snapshots, selects the recent window, compares source revisions, and schedules
analysis jobs.

An analysis gateway owns the App Server lifecycle for ephemeral GPT-5.6 work. It
receives bounded transient source content and returns a schema-constrained result.
It cannot mutate ordinary threads and cannot expose raw input or output envelopes.

A brief repository stores only validated structured fields, lifecycle metadata,
source revision, model identifier, and safe failure categories. API/SSE DTOs
contain the same bounded data. The client merges factual observed-session metadata
with the corresponding brief.

## Data Flow

1. Observer inventory or live events update a session revision.
2. Brief coordinator recalculates the newest 10 eligible sessions.
3. Missing/stale revisions enter a bounded queue after debounce.
4. Worker fetches recent turns into request memory.
5. Ephemeral GPT-5.6 Sol analysis returns schema-constrained JSON.
6. Validator rejects extra, oversized, contradictory, or malformed fields.
7. Repository atomically promotes the validated result to the last good brief.
8. Brief updates reach the Today view without reloading.
9. A later revision marks the current brief stale while leaving it readable until
   replacement succeeds.

## Error Handling

- Disconnected Codex: keep last good briefs, mark affected work unavailable/stale,
  and resume automatically after reconnection.
- Transcript read failure: retain prior brief and expose a safe per-session failure
  category with manual retry.
- Model timeout or refusal: fail only that session revision; continue other jobs.
- Invalid structured output: reject it without overwriting the last good brief.
- Restart during analysis: convert orphaned running jobs to queued/stale and resume
  after observer readiness.
- Session leaves the newest-10 window: cancel queued work and keep or prune its
  brief according to bounded retention without surfacing it on Today.
- New revision during analysis: discard the obsolete result and queue the newest
  revision.

## Testing Strategy

- Pure selection, freshness, deduplication, supersession, prompt-bounding, and
  output-validation tests.
- Repository tests for restart recovery, last-good preservation, retention, and
  deletion/export privacy.
- Deterministic fake App Server tests proving explicit GPT-5.6 Sol, medium effort,
  ephemeral analysis, structured output, and zero ordinary-thread mutations.
- Integration tests for observer-to-queue-to-brief state transitions and failure
  isolation.
- Browser workflows for initial background progress, live updates, manual refresh,
  stale/offline visibility, action lists, responsive layout, and accessibility.
- Regression checks for morning planning, Needs You, reports, deletion, and the
  existing transient-content boundary.

## Rough Vertical-Slice Roadmap

1. **Brief Contract And Storage** — structured session-brief lifecycle, source
   revisions, retention, privacy, and API shapes.
2. **GPT-5.6 Background Analysis** — ephemeral model gateway, bounded recent-turn
   input, validation, queueing, supersession, and restart behavior.
3. **Recent Sessions Frontend** — integrated 10-session cards, live progress,
   operator actions, freshness, failure, and manual refresh.
4. **Operational Proof** — lifecycle, privacy/export/deletion, responsive browser
   evidence, model-contract proof, and full regression verification.

## Open Questions For Alignment

- Exact recent-turn budget per session and truncation wording.
- Debounce, concurrency, timeout, and retry defaults.
- Whether a brief leaving the recent-10 window is immediately pruned or retained
  for a short bounded period.
- Exact frontend hierarchy between Needs You, today's outcomes, and recent briefs.
- Manual refresh semantics when a source revision has not changed.

## Source Notes

- Official GPT-5.6 guidance:
  `https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6`
- The official guidance identifies `gpt-5.6-sol` as the flagship model, recommends
  explicit reasoning-effort selection, and supports structured, outcome-focused
  prompts.
- Installed Codex CLI schema generated locally from
  `codex-cli 0.146.0-alpha.3.1` confirms App Server support for explicit model,
  effort, ephemeral threads, and turn output schemas.
- The Codex manual helper could not resolve its remote host in the sandbox; the
  installed generated schema is the verified source for this environment.

## Issue-Log Overlap

No `docs/issues/README.md` or central issue register exists in this repository.
No targeted issue-log overlap was found.

## Repository Rules

- Consulted: existing Codex Daily archived pipeline, app README, generated App
  Server schema, and repository structure. No `docs/rules/README.md` exists.
- Constraints applied: preserve loopback-only security, read-only ordinary chats,
  minimal retention, factual-versus-derived labeling, and ROS protected paths.
- Rule updates: None.
