# Codex Daily

Codex Daily is a loopback-only daily operations dashboard for organizing work
across Codex chats. Morning outcomes and deliberate prior-day review decisions
are stored in local SQLite; Codex monitoring surfaces still use representative
metadata and never retain chat transcripts.

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

## Verify

```bash
npm run check
npm run test:e2e
```
