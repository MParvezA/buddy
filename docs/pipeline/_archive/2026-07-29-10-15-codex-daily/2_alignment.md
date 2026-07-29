# Codex Daily — Feature Alignment

## Short Feature Name

Codex Daily

Pipeline folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`

## Aligned Product Contract

Codex Daily is a private local daily operations dashboard for one person managing
work across multiple Codex chats. Its primary object is the operator's day:

`Morning intent → Observed Codex work → Human attention → Evening reconciliation`

The application is a monitor and organizer in the first release. It does not
silently become an autonomous controller.

## Final Decisions

### Completion remains operator-owned

- Codex Daily may suggest that a task is complete based on observed chat evidence.
- A suggestion is visually distinct from a confirmed completion.
- Only the operator can confirm completion.
- A completed Codex turn or thread is never sufficient by itself to mark the
  corresponding daily outcome complete.

Rejected alternative: automatically completing tasks when a Codex turn finishes.

### Local storage uses minimal retention

- Persist thread identity and metadata, normalized activity, task links, attention
  state, report digests, report narratives, and preferences.
- Do not persist full Codex chat transcripts.
- Fetch full thread content from Codex on demand when a detail or report operation
  needs it.
- Make local application data inspectable and deletable by the operator.

Rejected alternative: duplicating full chat history in the monitor database.

### Attention has explicit entry rules

The Needs You queue includes:

- approval requests and direct questions immediately;
- failed or interrupted turns immediately;
- explicit blockers immediately; and
- active threads with no observed activity for 30 minutes as `possibly stale`.

Completed turns and routine progress belong in the activity feed, not the
attention queue.

### Carry-forward is deliberate

Unfinished tasks appear in the next morning's review with exactly three operator
choices:

- carry forward to today;
- reschedule to another date; or
- close without carrying forward.

Nothing moves to a new day automatically.

### The dashboard is attention-first

The primary dashboard order is:

1. Needs your attention.
2. Today's outcomes and progress.
3. Active Codex chats.
4. Recently completed work.
5. Evening-report preview.

Thread details, settings, and historical reports are secondary views.

### Reports are factual before they are interpretive

- Every report has a deterministic factual digest.
- Intelligent narrative generation is an enhancement over that digest.
- A failed or unavailable Codex summarization step cannot prevent the factual
  report from being created.
- Reports distinguish confirmed completion, suggested completion, pending work,
  blockers, and newly observed unplanned work.
- The default automatic report time is 18:00 Europe/Berlin and is configurable.
- Manual report generation remains available.

## Product Behavior And UX Expectations

### Morning review

On first use each day, the operator sees unresolved work from the previous day
before creating today's outcomes. After carry-forward decisions are resolved, the
operator can add, prioritize, and clarify today's outcomes.

The morning flow should be quick enough to use daily. Empty-state guidance should
ask for desired outcomes, not a list of chats.

### Live monitoring

The interface continuously projects Codex thread inventory and streamed events
into understandable statuses. Codex-specific protocol language should remain in
diagnostic detail rather than the primary UI.

Connection health is always visible. A disconnected state must not block access to
today's plan or previously generated reports.

### Linking tasks and threads

One task may link to multiple chats, and one chat may contribute to multiple
tasks. Suggested links may be offered when confidence is high, but the application
does not silently create them.

Unlinked active chats remain visible as unplanned work and can appear in the
evening report as newly discovered activity.

### Attention management

The operator may acknowledge or dismiss derived attention items without mutating
the underlying Codex thread. The source event remains visible in thread detail.

`Possibly stale` is a low-certainty attention state and must not look equivalent
to an explicit failure or approval request.

### Evening reconciliation

The report answers:

- What was planned?
- What was confirmed complete?
- What appears complete but still needs confirmation?
- What remains pending or blocked?
- What unplanned work appeared?
- What still needs the operator?
- What should be considered tomorrow?

The report is a snapshot retained in history. Regeneration creates a newer
snapshot without destroying the earlier factual record.

## Edge Cases And Failure Behavior

- When Codex App Server is unavailable, planning remains editable and monitoring
  visibly pauses.
- Reconnection must not duplicate activity or attention items.
- Unknown state remains `unknown`; it is not coerced to idle, complete, or failed.
- Time-zone or daylight-saving changes use the configured local timezone for the
  day boundary and report schedule.
- If the application was not running at report time, it creates one missed report
  after startup when no report exists for that day.
- A thread can disappear from current inventory without being treated as deleted
  or complete.
- Archival in Codex is reflected as thread state and does not alter daily-task
  completion.
- Deleting local monitor history does not delete Codex threads.

## Data Ownership And Permissions

- The monitor reads Codex state through Codex App Server.
- Monitoring and reporting are read-only with respect to ordinary Codex chats.
- A dedicated reporting thread may be created only for requested or scheduled
  summarization and is excluded from the monitored work inventory.
- The application does not answer approvals, send prompts to work threads, archive
  threads, or change their state.
- Any future move from observation to action requires an explicit product design
  and remains tracked as deferred scope.

## Canonical Mental Model And Required Removals

Canonical model: the day owns intent, observed work, attention, and reconciliation.
Chats provide evidence and context.

Concepts that implementation must not introduce or must remove if discovered:

- chat completion as task completion;
- full-transcript mirroring;
- automatic task carry-forward;
- an undifferentiated notification/activity feed;
- hidden autonomous thread control; and
- a generic chat-history viewer as the primary navigation model.

## Non-Goals

- Autonomous approval decisions or prompt sending.
- Team accounts, shared plans, or role-based access.
- Cloud sync or remote hosting.
- Non-Codex assistant monitoring.
- Full transcript retention.
- Repository-aware verification of commits, diffs, or tests.
- Third-party integrations in the first release.

## Deferred Scope And Follow-Up Candidates

| ID | Item | Why Deferred | Follow-Up Trigger |
| --- | --- | --- | --- |
| FUP-001 | Evidence-backed completion | Git commits, diffs, and test results need repository-aware evidence collection beyond the core monitor | Core daily reconciliation is reliable and users need stronger completion confidence |
| FUP-002 | Weekly review | Daily reports should prove useful before introducing a second reporting cadence | At least one week of retained daily reports exists |
| FUP-003 | Third-party integrations | Calendar, Slack, Notion, and similar systems add authentication and data-ownership complexity | A specific external system is chosen after local use |
| FUP-004 | Multi-device sync | Secure sync requires an account, encryption, and conflict model | Local-only use becomes a demonstrated limitation |
| FUP-005 | Cost and limit insights | Rate-limit data is available, but useful cost/usage framing needs separate product decisions | Operators ask for capacity planning after the activity monitor is established |
| FUP-006 | Proactive chat control | Sending suggested prompts or resolving approvals changes the product from monitor to controller | Read-only trust is established and explicit action semantics are designed |

## Roadmap-Level Vertical Slices

1. **Daily shell** — an attention-first interface that demonstrates the complete
   daily mental model with representative states.
2. **Morning intent** — durable planning, prior-day review, and explicit
   carry-forward.
3. **Codex observer** — thread discovery, normalized activity, live state, and
   connection health.
4. **Attention queue** — deterministic attention derivation and acknowledgement.
5. **Daily reconciliation** — factual digest, optional intelligent narrative,
   scheduling, and history.
6. **Operational hardening** — recovery, privacy controls, diagnostics, and full
   lifecycle validation.

## Acceptance Criteria

- A new day can be planned without creating or selecting a Codex chat first.
- Previous unfinished work requires an explicit carry, reschedule, or close choice.
- Local Codex chats appear automatically with current or last-known state.
- Approval requests, direct questions, failures, interruptions, blockers, and
  stale-active threads appear in Needs You according to the aligned rules.
- Routine progress does not clutter Needs You.
- Tasks can be linked to chats without forcing a one-to-one relationship.
- Suggested completion never changes the task until the operator confirms it.
- The local database contains no complete copied chat transcripts.
- At 18:00 Europe/Berlin by default, or on demand, a factual report reconciles the
  day even when intelligent summarization fails.
- A missed scheduled report is recovered once without duplication.
- Disconnection from Codex is visible while planning and report history remain
  usable.
- No first-release flow approves, prompts, archives, or otherwise controls an
  ordinary Codex work thread.

## Risks That Shape Planning And Testing

- App Server is a rich but evolving protocol; the adapter needs a narrow
  normalization boundary and contract fixtures.
- Some attention concepts may not map to one explicit event and must retain their
  certainty level.
- Time and day-boundary behavior is easy to get subtly wrong around restarts and
  daylight-saving changes.
- Summarization can introduce unsupported claims, so the factual digest must remain
  the source of truth.
- The repository currently has no web stack, so the new application must remain
  bounded and not disturb the ROS workspace.

## Remaining Open Questions

None blocking implementation planning. Visual details and exact component
composition may be resolved within the approved attention-first hierarchy.

## UX Catalogue Updates

Added reusable decisions for human-confirmed completion, attention-first
information hierarchy, deliberate carry-forward, minimal local retention, and
facts-before-generated-interpretation to
`docs/about/05_ux_decision_catalogue.md`. No conflicts existed because this is the
repository's first UX decision catalogue.

## Repository Rules

- Consulted: `1_design.md`; root README; new `docs/about/05_ux_decision_catalogue.md`; no `docs/rules/README.md` was present.
- Constraints applied: preserve the ROS project boundary; use the approved local-only and read-only product model; avoid internal Codex state parsing.
- Rule updates: None
