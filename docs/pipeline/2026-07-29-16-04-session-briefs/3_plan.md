# Codex Daily — Recent Session Briefs Slice Roadmap

## Context

- Repository: `/home/syncrobot/buddy`
- Planning branch target: `dev`
- Recommended implementation branch:
  `feature/2026-07-29-16-04-session-briefs`
- Feature folder:
  `docs/pipeline/2026-07-29-16-04-session-briefs/`
- Source design: `1_design.md`
- Source alignment: `2_alignment.md`
- Baseline feature: reviewed and archived Codex Daily implementation ending at
  `f255d46`

## Vertical Slices

### 01 — Brief Contract And Storage

Add one durable, privacy-bounded session-brief lifecycle through SQLite, service
ownership, API/SSE shapes, manual refresh intent, export, deletion, retention, and
restart recovery. Use a deterministic placeholder analyzer so the complete
server-to-browser state contract is visible before live GPT work.

Deferred scope pulled in: none.

### 02 — GPT-5.6 Background Analysis

Replace the placeholder with bounded recent-turn extraction and an ephemeral,
schema-constrained GPT-5.6 Sol gateway. Add debounced two-worker scheduling,
supersession, retry, timeout, failure isolation, and last-good preservation.

Depends on: Slice 01.

Deferred scope pulled in: none.

### 03 — Recent Sessions Frontend

Replace the metadata-only active/recent section with the canonical 10-session
brief cards, derived-state labels, structured actions, live progress, stale and
failure states, manual refresh, per-session retry, and responsive accessibility.

Depends on: Slices 01–02.

Deferred scope pulled in: none.

### 04 — Operational Proof

Prove the overnight lifecycle, restart recovery, host GPT-5.6 contract, privacy
boundaries, deletion races, bounded retention, responsive browser workflows, and
non-regression of planning, Needs You, reporting, diagnostics, and ROS scope.

Depends on: Slices 01–03.

Deferred scope pulled in: none.

## Recommended Order

Implement Slices 01–04 in numeric order. Each slice produces one testable vertical
increment and leaves the application runnable.

The next slice to implement is Slice 01 — Brief Contract And Storage.

## Deferred Feature Scope

`FUP-001` through `FUP-005` remain deferred. No roadmap slice pulls configurable
session count, configurable analysis depth, weekly synthesis, external
notifications, or ordinary-chat control into this feature.

## Implementation Source Warning

This roadmap is not an implementation source for `4_Implement`. Implementation
requires the corresponding approved `3_plan_slice_*.md` contract.

## Repository Rules

- Consulted: `1_design.md`, `2_alignment.md`, UX catalogue, archived Codex Daily
  plan/review, and current app boundaries. No `docs/rules/README.md` exists.
- Constraints applied: preserve one recent-session concept, privacy-bounded
  transcript access, explicit GPT-5.6 Sol, read-only ordinary chats, and protected
  ROS paths.
- Rule updates: None.
