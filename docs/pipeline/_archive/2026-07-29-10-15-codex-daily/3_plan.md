# Codex Daily — Slice Roadmap

## Context

- Repository: `/home/syncrobot/buddy`
- Current branch during planning: `main`
- Recommended implementation branch: `feature/codex-daily`
- Feature folder: `docs/pipeline/2026-07-29-10-15-codex-daily/`
- Source design: `1_design.md`
- Source alignment: `2_alignment.md`

The repository currently contains a ROS 2 application and no web application
stack. Codex Daily must remain a bounded local application and must not change
existing Buddy runtime behavior.

## Vertical Slices

### 01 — Daily Dashboard

Create a runnable local dashboard that demonstrates the complete attention-first
daily mental model with representative local data and responsive primary and
secondary views.

Deferred scope pulled in: none.

### 02 — Morning Planning

Replace representative planning data with durable local days and tasks, including
completion confirmation and explicit prior-day carry-forward choices.

Depends on: Slice 01.

Deferred scope pulled in: none.

### 03 — Codex Observer

Connect to the local Codex App Server, discover threads, normalize current and live
activity, expose connection health, and support explicit task-to-thread links
without retaining full transcripts.

Depends on: Slices 01–02.

Deferred scope pulled in: none.

### 04 — Needs You

Derive, display, acknowledge, and dismiss the aligned human-attention states while
keeping certainty and source activity visible.

Depends on: Slice 03.

Deferred scope pulled in: none.

### 05 — Evening Report

Create factual daily reconciliation, configurable and recoverable scheduling,
historical snapshots, manual generation, and optional Codex-authored narrative
with a factual fallback.

Depends on: Slices 02–04.

Deferred scope pulled in: none.

### 06 — Operational Hardening

Prove the full morning-to-evening lifecycle, reconnection and deduplication,
timezone behavior, privacy controls, diagnostics, and non-regression of the
existing ROS workspace.

Depends on: Slices 01–05.

Deferred scope pulled in: none.

## Recommended Order

Implement slices in numeric order. Each slice produces a user-visible vertical
increment and is the source for the next slice.

The next slice to plan is Slice 01 — Daily Dashboard.

## Deferred Feature Scope

FUP-001 through FUP-006 remain deferred. No roadmap slice pulls evidence-backed
completion, weekly reviews, third-party integrations, multi-device sync,
cost/limit insights, or proactive chat control into this feature.

## Implementation Source Warning

This roadmap is not an implementation source for `4_Implement`. Implementation
requires the corresponding approved `3_plan_slice_*.md` contract.

## Repository Rules

- Consulted: root README, `1_design.md`, `2_alignment.md`, and `docs/about/05_ux_decision_catalogue.md`; no `docs/rules/README.md` exists.
- Constraints applied: keep the new local web application isolated from ROS packages; retain the day-first, attention-first, read-only model.
- Rule updates: None
