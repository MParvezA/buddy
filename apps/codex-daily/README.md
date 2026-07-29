# Codex Daily

Codex Daily is a loopback-only daily operations dashboard for organizing work
across Codex chats. Morning outcomes and deliberate prior-day review decisions
are stored in local SQLite. The read-only Codex observer stores thread metadata
and content-free activity facts, never copied chat transcripts.
At the end of the day it freezes deterministic factual report snapshots from
the plan, normalized activity, and Needs You state. The default automatic run
is 18:00 Europe/Berlin; both time and IANA timezone are configurable in Settings.

## Requirements

- Node.js 24
- npm 11

## Run

```bash
npm ci
npm run dev
```

The client is available at `http://127.0.0.1:5173` and proxies API requests to
the local service at `http://127.0.0.1:4317`.

For a production-style local run:

```bash
npm run build
npm run start
```

The built dashboard and API are served at `http://127.0.0.1:4317`.

The service binds only to `127.0.0.1`. It handles `SIGINT` and `SIGTERM` by
stopping the report scheduler and observer before closing SQLite and the HTTP
listener.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_DAILY_PORT` | `4317` | Loopback HTTP port |
| `CODEX_DAILY_DB_PATH` | `.codex-daily-data/codex-daily.sqlite` | Inspectable local SQLite path |
| `CODEX_DAILY_TIMEZONE` | retained preference or `Europe/Berlin` | IANA timezone used at startup |
| `CODEX_DAILY_REPORT_TIME` | retained preference or `18:00` | Automatic report time in `HH:MM` |
| `CODEX_DAILY_OBSERVER_MODE` | `standalone_history` | `standalone_history` or `shared_live` |
| `CODEX_DAILY_CODEX_PATH` | `codex` | Codex executable path |
| `CODEX_DAILY_REPORTING_TURN_TIMEOUT_MS` | `120000` | Reporting-turn timeout, capped at 10 minutes |

Environment timezone/time values intentionally update the retained preference at
startup. Later changes can be made in Settings without editing source.

The observer defaults to `standalone_history`, spawning the fixed command
`codex app-server --stdio`. This mode polls all stored top-level CLI, VS Code,
and App Server chats, but cannot promise live approval/question events owned by
another Codex process.

Set `CODEX_DAILY_OBSERVER_MODE=shared_live` to use the fixed
`codex app-server proxy` bridge to an operator-managed App Server daemon. Codex
Daily does not start, stop, or reconfigure that daemon. `CODEX_DAILY_CODEX_PATH`
may select a Codex executable path for local testing or an installation outside
`PATH`; observer arguments and the narrow protocol boundary remain fixed.

Ordinary chats remain read-only. When generated interpretation is explicitly
enabled, Codex Daily creates one dedicated reporting thread, excludes it from
monitoring, transiently reads only the final assistant message from linked work
threads, and starts turns only in that reporting thread. Factual snapshots are
saved first and remain usable if this optional step fails.

## Recent session briefs

Priority 03 keeps an operational brief for the newest 10 eligible ordinary
sessions. Eligibility is limited to top-level, non-archived sessions; reporting
threads, ephemeral analysis threads, subagents/children, and locally excluded
threads are omitted. Ordering is literal `recencyAt`, falling back to
`updatedAt`; runtime activity does not move an older session ahead of a newer
one. A brief is current only for the exact observed `{threadId, updatedAt}`
revision.

For each selected revision, the server transiently reads the first user intent
and the six most recent turns. It accepts only user/assistant text, strips
reasoning, tools, raw protocol fields, unsupported content, and
credential-shaped fields, preserves chronological role labels, and caps the
complete rendered request at 32,000 Unicode characters. That bounded input
exists only in process/request memory.

Analysis uses one ephemeral Codex App Server thread per job with exactly
`gpt-5.6-sol`, medium reasoning, provider fallback disabled, no dynamic tools,
no environment or workspace roots, and a strict structured-output schema.
Codex Daily persists only the validated current-state, chat-reported-done,
operator-action, blocker, confidence, evidence-label, model, revision, and safe
lifecycle fields. It never stores the prompt, transcript text, raw model output,
reasoning, tool payloads, protocol envelopes, or raw exceptions.

Automatic work begins only after a usable observer snapshot and a 30-second
debounce. At most two analyses run together. A turn times out after two minutes;
transient failures retry after 30 seconds and then two minutes, with no model or
provider fallback. A newer source revision supersedes queued, retrying, or
in-flight older work. Manual refresh moves eligible work ahead of automatic
queued work without bypassing concurrency or creating duplicate revision jobs.

The last validated result remains visible as stale through refresh failures,
disconnects, restarts, and overnight use. Startup recovers an interrupted
analysis only after the observer is ready. A brief leaving the newest-10 window
is hidden immediately, retained for a 24-hour grace period, restored on re-entry,
and pruned at or after the exact boundary by an hourly sweep. Settings diagnostics
show content-free durable queued/retry/analyzing job counts separately from
active in-memory workers and their peak. They also show model, failure, pruning,
orphan-recovery, and drain state; a stopped service can retain an interrupted
durable job while reporting zero active workers.

## Local data, export, backup, and deletion

The database stores daily plans, review decisions, normalized content-free
activity, task/thread links, local attention state, report snapshots, reporting
thread exclusions, validated session briefs, safe brief-job metadata, and
preferences. It does not retain fetched transcript bodies, prompts, raw model
output, credentials, or raw App Server payloads.

Settings shows the exact data location, SQLite health, record counts, retained
date range, observer reconnect state, report scheduling state, and redacted
error categories. Use **Export JSON** there for a deterministic product-level
backup. For a byte-for-byte backup while the app is stopped, copy the configured
SQLite file and any adjacent `-wal`/`-shm` files together.

Settings also provides typed-confirmation deletion for one local day or all
Codex Daily data. These operations pause local writers and are transactional.
They cancel/drain brief generation before deleting its local rows, and obsolete
late model results cannot recreate deleted data.
They never delete, archive, prompt, approve, or otherwise change Codex chats.
After monitoring resumes, current thread metadata can be rediscovered.

The JSON export contains validated structured briefs and safe lifecycle metadata
but no analysis input or raw output. Diagnostics are similarly bounded to counts,
timestamps, model ID, and safe failure categories.

## Synthetic GPT-5.6 host proof

After `npm run build`, an opt-in proof can verify the installed Codex App Server
and exact production model contract:

```bash
CODEX_DAILY_RUN_HOST_MODEL_PROOF=1 \
  node scripts/prove-session-brief-host.mjs
```

The proof creates one ephemeral analysis thread from invented Northstar-demo
content. It never calls `thread/list` or `thread/read`, so it does not enumerate
or inspect local chat history. It validates the production strict schema and
prints only a fixed redacted summary: CLI/model/effort identifiers, booleans,
elapsed time, and a safe pass/blocker category. It never prints IDs, working
directories, prompts, model output, protocol envelopes, reasoning, environment,
or credentials.

Safe blocker categories distinguish host startup/transport unavailability,
App Server request rejection, and an explicit model/ephemeral/structured-output
contract mismatch. They intentionally do not include raw exception or stderr
text.

This proof is intentionally excluded from normal tests, builds, startup, and
Playwright. It may consume account/model capacity and requires local Codex
authentication, network access, and GPT-5.6 Sol availability. It fails without
fallback if any requirement is unavailable. Run it from a normal host context
when a restricted filesystem sandbox prevents Codex from initializing; never
substitute a real transcript.

## Troubleshooting

- **Observer disconnected:** the plan, reports, and retained normalized thread
  facts and last-good session briefs remain usable; only new analysis and
  transient full chat history are unavailable. Confirm
  that `codex` is on `PATH`, or set `CODEX_DAILY_CODEX_PATH`. For shared live
  events, confirm the operator-managed proxy is available.
- **A brief is stale or failed:** the prior validated brief remains visible.
  Reconnect Codex if needed, then use the title-specific retry or **Refresh 10
  briefs**. Timeout, refusal, invalid output, unavailable model, and source-read
  failures stay isolated to the affected session.
- **GPT-5.6 Sol is unavailable:** Codex Daily reports analysis unavailable and
  does not switch model/provider. Verify local Codex authentication and model
  access, then retry.
- **Approvals/questions are absent:** `standalone_history` cannot observe live
  requests owned by another Codex process.
- **Automatic report did not run:** inspect scheduler diagnostics in Settings.
  Startup recovers at most the current local day's missed slot; it never
  backfills older dates.
- **Narrative failed:** the factual report is already retained. Reconnect Codex
  and retry interpretation from the report detail view.
- **Database health is not OK:** stop the app, preserve the database files, and
  use the JSON export if available before making filesystem-level changes.
- **Shutdown appears delayed:** active analysis is canceled/drained before the
  App Server, HTTP listener, and SQLite close. Allow the bounded shutdown to
  finish before restarting or copying the database.

## Fresh temporary-data smoke

```bash
CODEX_DAILY_DB_PATH=/tmp/codex-daily-hardening.sqlite \
CODEX_DAILY_TIMEZONE=Europe/Berlin \
CODEX_DAILY_REPORT_TIME=18:00 \
npm run start
```

Stop with `Ctrl+C`. Remove only the explicitly named temporary SQLite file and
its `-wal`/`-shm` companions after the smoke run.

## Verify

```bash
npm run check
npm run test:e2e
```
