# Codex Daily — Feature Design

## Goal

Create a private, local daily operations dashboard that helps one operator organize
work delegated across Codex chats. The product turns a collection of independent
threads into one daily loop:

`Morning plan → Codex work → Attention queue → Evening report`

The target operator uses multiple Codex chats during the day and needs a reliable
answer to three questions:

1. What is Codex doing or what has it finished?
2. Where does Codex need human input?
3. What remains from today's intended work?

## Success Criteria

- The operator can define today's intended outcomes in a short morning check-in.
- The dashboard automatically discovers local Codex threads and reflects their
  current or most recently observed state.
- Work requiring human attention is separated from passive activity.
- Planned tasks can be linked to one or more Codex threads.
- An evening report reconciles the morning plan with observed work, including
  completed, pending, blocked, and newly discovered work.
- The monitor is local-only and read-only by default.
- The report can be generated on demand as well as at a configurable local time.

## Non-Goals

- Acting on approval requests without explicit operator confirmation.
- Sending prompts or changing Codex threads automatically in the first release.
- Supporting teams, shared workspaces, or multiple user accounts.
- Monitoring non-Codex assistants.
- Treating activity as proof of completion when no supporting completion signal is
  available.

## Deferred Scope And Follow-Up Candidates

| ID | Item | Why Deferred | Follow-Up Trigger |
| --- | --- | --- | --- |
| FUP-001 | Evidence-backed completion | Git commits, diffs, and test results need repository-aware evidence collection beyond the core monitor | Core daily reconciliation is reliable and users need stronger completion confidence |
| FUP-002 | Weekly review | Daily reports should prove useful before introducing a second reporting cadence | At least one week of retained daily reports exists |
| FUP-003 | Third-party integrations | Calendar, Slack, Notion, and similar systems add authentication and data-ownership complexity | A specific external system is chosen after local use |
| FUP-004 | Multi-device sync | Secure sync requires an account, encryption, and conflict model | Local-only use becomes a demonstrated limitation |
| FUP-005 | Cost and limit insights | Rate-limit data is available, but useful cost/usage framing needs separate product decisions | Operators ask for capacity planning after the activity monitor is established |
| FUP-006 | Proactive chat control | Sending suggested prompts or resolving approvals changes the product from monitor to controller | Read-only trust is established and explicit action semantics are designed |

## Constraints And Assumptions

- The first release is a personal application running on the same machine as
  Codex.
- Europe/Berlin is the initial local timezone; the timezone and evening report time
  are configurable.
- Codex App Server is the supported integration boundary for conversation history,
  runtime status, approvals, and streamed events.
- Direct parsing of Codex's internal session files or database is not a supported
  integration strategy.
- Local persisted data belongs to the operator and must remain inspectable and
  deletable.
- Intelligent report generation may use a dedicated Codex reporting thread and
  therefore consumes Codex capacity. The underlying factual activity timeline must
  remain useful when intelligent summarization is unavailable.
- The existing repository is a ROS 2 robot project and has no established web
  application stack, design system, product rules, or feature pipeline rules.

## Canonical Mental Model

The canonical unit is a **day**, not a chat.

Each day contains:

- **Intent:** operator-authored outcomes established in the morning.
- **Observed work:** Codex threads and events discovered during the day.
- **Attention:** questions, approvals, failures, or stale work requiring the
  operator.
- **Reconciliation:** an evening account of intent versus observed outcomes.

A chat is evidence and context attached to a daily task; it is not itself the task.
The monitor must not equate a completed Codex turn with completion of the
operator's outcome.

Superseded concepts to avoid:

- A generic chat-history viewer.
- A notification feed without a daily plan.
- A kanban board that requires manually duplicating every Codex action.
- Automatic agent control hidden inside a monitoring product.

## Selected Approach

Build a local web dashboard with a small local service.

The service connects to Codex App Server, reads thread history and runtime state,
subscribes to live events, persists the operator's daily plan and mappings, and
runs the report schedule. The browser interface presents the daily loop and can
remain useful when Codex is temporarily unavailable.

This approach is selected because Codex App Server is designed for rich clients
and exposes conversation history, thread status, approvals, and streamed events.
It avoids coupling the product to Codex's private on-disk representation.

## Rejected Alternatives

### Notification hook only

Codex's external notification hook is useful for turn-complete signals but does
not provide the history and state needed for a complete dashboard.

### Direct local state parsing

Reading session logs or SQLite state directly would be fragile and could silently
break when Codex changes its storage format.

### Hosted service first

A hosted system would add authentication, sync, and privacy work before validating
the daily operating model.

## Architecture

### Local dashboard

The primary interface has four product surfaces:

- **Today:** morning goals and overall progress.
- **Live work:** active and recent Codex threads.
- **Needs you:** an attention-first queue.
- **Report:** the current or historical daily reconciliation.

The visual direction is a calm, dense operations console rather than an animated
chat client: dark by default, status color used sparingly, readable timestamps,
and clear separation between observed facts and generated interpretation.

### Codex adapter

The adapter owns the App Server connection and protocol lifecycle. It:

- initializes the connection;
- lists and reads relevant local threads;
- subscribes to runtime, turn, and item events;
- normalizes Codex-specific events into the application's small activity model;
- reconnects with bounded backoff; and
- exposes connection health without discarding locally persisted planning data.

### Daily planning store

Local persistence owns days, tasks, task-to-thread links, attention state, report
snapshots, and user preferences. Raw credentials are not stored by the
application.

### Reconciliation engine

The engine first builds a deterministic factual digest from the daily plan and
normalized activity. When configured and available, a dedicated Codex reporting
thread turns that digest into a concise narrative and suggested next-day
priorities. Generated statements remain distinguishable from recorded facts.

### Scheduler

The local scheduler creates the evening report at the configured time. Missed
scheduled runs are recovered the next time the application starts, without
creating duplicate reports for the same day.

## Data Flow

1. The operator creates or confirms today's plan.
2. The service requests current thread inventory from Codex App Server.
3. Stored thread data and streamed events are normalized into daily activity.
4. The operator links relevant threads to planned tasks; high-confidence suggested
   links may be offered but are never silently committed.
5. Attention signals are projected into the Needs You queue.
6. At report time, the reconciliation engine compares the plan with observed work.
7. The factual digest is saved, optionally summarized, and presented for review.
8. Pending work can be carried forward only through an explicit operator action.

## Error Handling

- When Codex is offline, show a clear disconnected state and retain planning and
  report access.
- Reconnect without producing duplicate activity.
- Preserve the last factual report if intelligent summarization fails.
- Label unknown thread state as unknown instead of inferring completion.
- Never mark a task complete solely because a thread or turn finished.
- Surface scheduling failures and allow manual report generation.
- Require explicit confirmation before deleting local history or carrying work
  into another day.

## Testing Strategy

Testing should cover the daily lifecycle at the product boundary, protocol event
normalization, reconnection and deduplication, time-zone report scheduling,
missed-run recovery, factual report generation, and the absence of autonomous
actions. A fake App Server event source should make critical flows deterministic.

## Rough Vertical-Slice Roadmap

1. **Daily shell:** establish the visual daily dashboard with representative data.
2. **Morning intent:** persist daily tasks and planning state.
3. **Codex observer:** connect thread inventory and live normalized activity.
4. **Attention queue:** derive and manage human-action items.
5. **Daily reconciliation:** generate, schedule, and retain evening reports.
6. **Operational hardening:** cover recovery, privacy controls, and end-to-end
   lifecycle verification.

## Open Questions For Alignment

- Which events deserve immediate attention versus passive visibility?
- How should the operator express task completion: manual only, suggested, or
  automatically inferred with confirmation?
- How much thread content may the monitor retain locally?
- What should happen to unfinished work the next morning?
- Which information belongs in the primary dashboard versus a detail view?

## Source Notes

- Current OpenAI Codex manual, **Codex App Server**: App Server supports
  authentication, conversation history, approvals, thread APIs, runtime status,
  and streamed agent events.
- Current OpenAI Codex manual, **Notifications**: the external `notify` command is
  currently limited to supported events including `agent-turn-complete`, making it
  insufficient as the sole monitor integration.

## Issue-Log Overlap

No targeted issue-log overlap found. This repository does not currently contain
`docs/issues/README.md` or a central issue register.

## Repository Rules

- Consulted: root README; no root `AGENTS.md`, `docs/rules/README.md`, project goals, or UX decision catalogue exists.
- Constraints applied: preserve the existing ROS project; introduce the monitor as a bounded local application; use Codex App Server rather than internal state parsing.
- Rule updates: None
