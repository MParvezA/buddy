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

## Local data, export, backup, and deletion

The database stores daily plans, review decisions, normalized content-free
activity, task/thread links, local attention state, report snapshots, reporting
thread exclusions, and preferences. It does not retain fetched transcript
bodies, credentials, or raw App Server payloads.

Settings shows the exact data location, SQLite health, record counts, retained
date range, observer reconnect state, report scheduling state, and redacted
error categories. Use **Export JSON** there for a deterministic product-level
backup. For a byte-for-byte backup while the app is stopped, copy the configured
SQLite file and any adjacent `-wal`/`-shm` files together.

Settings also provides typed-confirmation deletion for one local day or all
Codex Daily data. These operations pause local writers and are transactional.
They never delete, archive, prompt, approve, or otherwise change Codex chats.
After monitoring resumes, current thread metadata can be rediscovered.

## Troubleshooting

- **Observer disconnected:** the plan, reports, and retained normalized thread
  facts remain usable; only transient full chat history is unavailable. Confirm
  that `codex` is on `PATH`, or set `CODEX_DAILY_CODEX_PATH`. For shared live
  events, confirm the operator-managed proxy is available.
- **Approvals/questions are absent:** `standalone_history` cannot observe live
  requests owned by another Codex process.
- **Automatic report did not run:** inspect scheduler diagnostics in Settings.
  Startup recovers at most the current local day's missed slot; it never
  backfills older dates.
- **Narrative failed:** the factual report is already retained. Reconnect Codex
  and retry interpretation from the report detail view.
- **Database health is not OK:** stop the app, preserve the database files, and
  use the JSON export if available before making filesystem-level changes.

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
