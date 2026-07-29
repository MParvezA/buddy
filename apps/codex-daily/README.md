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

Planning data defaults to
`apps/codex-daily/.codex-daily-data/codex-daily.sqlite`. Set
`CODEX_DAILY_DB_PATH` to use another inspectable local path.

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

## Verify

```bash
npm run check
npm run test:e2e
```
