# UX Decision Catalogue

Reusable product and interaction decisions approved through feature design and
alignment live here. Feature-specific behavior remains in its pipeline documents.

## Human-Confirmed Completion

- Automated evidence may suggest that a user-owned outcome is complete.
- Suggestions must remain visually and behaviorally distinct from confirmation.
- Only the user can confirm completion when the system observes activity rather
  than authoritative outcome evidence.
- Applied example: Codex Daily can suggest completion from chat activity but cannot
  complete a daily task automatically.

## Attention Before Activity

- Put items requiring user action ahead of passive progress and history.
- Define deterministic rules for what enters the attention surface.
- Preserve certainty levels: a possible stale state must not look equivalent to an
  explicit failure, question, or approval request.
- Applied example: Codex Daily separates Needs You from its ordinary activity feed.

## Deliberate Work Carry-Forward

- Unfinished work must not silently accumulate in a new planning period.
- Ask the user to carry forward, reschedule, or close each unresolved item.
- Keep historical intent intact rather than moving the original record.
- Applied example: Codex Daily resolves yesterday's unfinished outcomes during the
  next morning review.

## Minimal Local Retention

- Store only the durable metadata and derived state the product needs.
- Fetch sensitive source content on demand when a trusted source remains
  available.
- Make locally retained product data inspectable and deletable.
- Applied example: Codex Daily retains normalized activity and reports, not copied
  Codex transcripts.

## Facts Before Generated Interpretation

- Build generated summaries on a deterministic factual digest.
- Keep recorded facts distinguishable from generated interpretation.
- Preserve a useful factual result when intelligent generation is unavailable or
  fails.
- Applied example: every Codex Daily evening report exists as a factual
  reconciliation before an optional narrative is generated.

## Validated Source Families

- `docs/pipeline/2026-07-29-10-15-codex-daily/2_alignment.md`
