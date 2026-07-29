import type { DatabaseSync } from "node:sqlite";
import type {
  AttentionCertainty,
  AttentionItem,
  AttentionKind,
  AttentionLifecycle,
} from "../../shared/attention.js";

export interface AttentionCandidate {
  sourceKey: string;
  threadId: string;
  turnId: string | null;
  itemId: string | null;
  kind: AttentionKind;
  certainty: AttentionCertainty;
  sourceOccurredAt: string;
  sourceLabel: string;
}

interface AttentionRow {
  id: string;
  source_key: string;
  thread_id: string;
  turn_id: string | null;
  item_id: string | null;
  kind: AttentionKind;
  certainty: AttentionCertainty;
  source_occurred_at: string;
  last_derived_at: string;
  source_label: string;
  lifecycle: AttentionLifecycle;
  local_action_at: string | null;
}

function mapItem(row: AttentionRow): AttentionItem {
  return {
    id: row.id,
    sourceKey: row.source_key,
    threadId: row.thread_id,
    turnId: row.turn_id,
    itemId: row.item_id,
    kind: row.kind,
    certainty: row.certainty,
    sourceOccurredAt: row.source_occurred_at,
    lastDerivedAt: row.last_derived_at,
    sourceLabel: row.source_label,
    lifecycle: row.lifecycle,
    localActionAt: row.local_action_at,
  };
}

export class AttentionRepository {
  constructor(private readonly db: DatabaseSync) {}

  upsert(candidate: AttentionCandidate, now: string): boolean {
    const result = this.db
      .prepare(`
        INSERT INTO attention_items(
          id, source_key, thread_id, turn_id, item_id, kind, certainty,
          source_occurred_at, last_derived_at, source_label, lifecycle, local_action_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL)
        ON CONFLICT(source_key) DO UPDATE SET
          last_derived_at = excluded.last_derived_at
      `)
      .run(
        `attention:${candidate.sourceKey}`,
        candidate.sourceKey,
        candidate.threadId,
        candidate.turnId,
        candidate.itemId,
        candidate.kind,
        candidate.certainty,
        candidate.sourceOccurredAt,
        now,
        candidate.sourceLabel,
      );
    return result.changes > 0;
  }

  find(id: string): AttentionItem | null {
    const row = this.db
      .prepare("SELECT * FROM attention_items WHERE id = ?")
      .get(id) as unknown as AttentionRow | undefined;
    return row ? mapItem(row) : null;
  }

  listOpen(): AttentionItem[] {
    const rows = this.db
      .prepare(`
        SELECT *
        FROM attention_items
        WHERE lifecycle = 'open'
        ORDER BY certainty, source_occurred_at DESC, id
      `)
      .all() as unknown as AttentionRow[];
    return rows.map(mapItem);
  }

  listForThread(threadId: string): AttentionItem[] {
    const rows = this.db
      .prepare(`
        SELECT *
        FROM attention_items
        WHERE thread_id = ?
        ORDER BY source_occurred_at DESC, id
      `)
      .all(threadId) as unknown as AttentionRow[];
    return rows.map(mapItem);
  }

  markLocal(
    id: string,
    lifecycle: Extract<AttentionLifecycle, "acknowledged" | "dismissed">,
    now: string,
  ): "updated" | "not_found" | "not_actionable" {
    if (!this.find(id)) return "not_found";
    const result = this.db
      .prepare(`
        UPDATE attention_items
        SET lifecycle = ?, local_action_at = ?
        WHERE id = ? AND lifecycle = 'open'
      `)
      .run(lifecycle, now, id);
    return result.changes > 0 ? "updated" : "not_actionable";
  }

  sourceResolve(sourceKey: string, now: string): boolean {
    return (
      this.db
        .prepare(`
          UPDATE attention_items
          SET lifecycle = 'source_resolved', last_derived_at = ?
          WHERE source_key = ? AND lifecycle <> 'source_resolved'
        `)
        .run(now, sourceKey).changes > 0
    );
  }

  sourceResolveKindForThread(
    threadId: string,
    kind: AttentionKind,
    now: string,
    exceptSourceKey?: string,
  ): boolean {
    const statement = exceptSourceKey
      ? this.db.prepare(`
          UPDATE attention_items
          SET lifecycle = 'source_resolved', last_derived_at = ?
          WHERE thread_id = ? AND kind = ? AND source_key <> ?
            AND lifecycle <> 'source_resolved'
        `)
      : this.db.prepare(`
          UPDATE attention_items
          SET lifecycle = 'source_resolved', last_derived_at = ?
          WHERE thread_id = ? AND kind = ? AND lifecycle <> 'source_resolved'
        `);
    const result = exceptSourceKey
      ? statement.run(now, threadId, kind, exceptSourceKey)
      : statement.run(now, threadId, kind);
    return result.changes > 0;
  }
}
