# Codex Daily

Codex Daily is a loopback-only daily operations dashboard for organizing work
across Codex chats. This first slice uses deterministic representative data; it
does not connect to Codex or retain chat transcripts.

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

## Verify

```bash
npm run check
npm run test:e2e
```
