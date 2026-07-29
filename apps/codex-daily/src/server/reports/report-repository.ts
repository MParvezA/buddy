import { randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import type {
  CompletionSuggestion,
  FactualDigest,
  ReportNarrative,
  ReportSchedule,
  ReportSnapshot,
  ReportTrigger,
} from "../../shared/report.js";
import { buildFactualDigest, type DigestTaskInput, type DigestThreadInput } from "./factual-digest.js";

interface SnapshotRow {
  id: string;
  local_date: string;
  sequence: number;
  timezone: string;
  trigger: ReportTrigger;
  cutoff_at: string;
  factual_digest_json: string;
  created_at: string;
  narrative_status: ReportNarrative["status"];
  narrative_text: string | null;
  failure_code: string | null;
}

interface SuggestionRow {
  id: string;
  snapshot_id: string;
  task_id: string;
  reason: string;
  source_thread_ids_json: string;
  superseded_at: string | null;
}

interface ScheduleRow {
  local_time: string;
  timezone: string;
  narrative_enabled: number;
}

const SNAPSHOT_SELECT = `
  SELECT snapshots.*,
         narratives.status AS narrative_status,
         narratives.narrative_text,
         narratives.failure_code
  FROM report_snapshots snapshots
  JOIN report_narratives narratives ON narratives.snapshot_id = snapshots.id
`;

function suggestion(row: SuggestionRow): CompletionSuggestion {
  return {
    id: row.id,
    snapshotId: row.snapshot_id,
    taskId: row.task_id,
    reason: row.reason,
    sourceThreadIds: JSON.parse(row.source_thread_ids_json) as string[],
    supersededAt: row.superseded_at,
  };
}

export class AutomaticReportAlreadyExistsError extends Error {}

export class ReportRepository {
  constructor(private readonly db: DatabaseSync) {}

  private transaction<T>(work: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = work();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  createSnapshot(input: {
    localDate: string;
    dayStart: string;
    dayEnd: string;
    cutoff: string;
    trigger: ReportTrigger;
    narrativeRequested: boolean;
    timezone?: string;
    now: string;
  }): ReportSnapshot {
    return this.transaction(() => {
      const factualDigest = this.buildDigest(
        input.localDate,
        input.dayStart,
        input.dayEnd,
        input.cutoff,
      );
      const row = this.db
        .prepare(
          "SELECT COALESCE(MAX(sequence), 0) + 1 AS sequence FROM report_snapshots WHERE local_date = ?",
        )
        .get(input.localDate) as { sequence: number };
      const id = randomUUID();
      try {
        this.db
          .prepare(`
            INSERT INTO report_snapshots(
              id, local_date, sequence, trigger, automatic_run_key, timezone,
              cutoff_at, factual_digest_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          `)
          .run(
            id,
            input.localDate,
            row.sequence,
            input.trigger,
            input.trigger === "manual" ? null : input.localDate,
            input.timezone ?? this.getSchedule().timezone,
            input.cutoff,
            JSON.stringify(factualDigest),
            input.now,
          );
      } catch (error) {
        if (
          input.trigger !== "manual" &&
          error instanceof Error &&
          error.message.includes("UNIQUE constraint failed")
        ) {
          throw new AutomaticReportAlreadyExistsError(
            `The automatic report slot for ${input.localDate} is already filled.`,
          );
        }
        throw error;
      }
      this.db
        .prepare(`
          INSERT INTO report_narratives(
            snapshot_id, status, narrative_text, failure_code, updated_at
          ) VALUES (?, ?, NULL, NULL, ?)
        `)
        .run(id, input.narrativeRequested ? "pending" : "not_requested", input.now);
      this.db
        .prepare(`
          UPDATE report_completion_suggestions
          SET superseded_at = ?
          WHERE superseded_at IS NULL
            AND task_id IN (
              SELECT tasks.id
              FROM tasks JOIN days ON days.id = tasks.day_id
              WHERE days.local_date = ? AND tasks.lifecycle != 'closed'
            )
        `)
        .run(input.now, input.localDate);
      return this.findSnapshot(id)!;
    });
  }

  private buildDigest(
    localDate: string,
    dayStart: string,
    dayEnd: string,
    cutoff: string,
  ): FactualDigest {
    const taskRows = this.db
      .prepare(`
        SELECT tasks.id AS task_id, tasks.title, tasks.clarification,
               tasks.sort_position, tasks.lifecycle,
               EXISTS (
                 SELECT 1 FROM report_completion_suggestions suggestions
                 WHERE suggestions.task_id = tasks.id
                   AND suggestions.superseded_at IS NULL
                   AND suggestions.snapshot_id IN (
                     SELECT id FROM report_snapshots WHERE cutoff_at <= ?
                   )
               ) AS suggested_complete,
               EXISTS (
                 SELECT 1 FROM task_thread_links links
                 JOIN attention_items attention ON attention.thread_id = links.thread_id
                 WHERE links.task_id = tasks.id
                   AND attention.kind = 'explicit_blocker'
                   AND attention.lifecycle = 'open'
                   AND attention.source_occurred_at <= ?
               ) AS blocked
        FROM tasks JOIN days ON days.id = tasks.day_id
        WHERE days.local_date = ? AND tasks.lifecycle != 'closed'
        ORDER BY tasks.sort_position, tasks.created_at, tasks.id
      `)
      .all(cutoff, cutoff, localDate) as unknown as Array<{
        task_id: string;
        title: string;
        clarification: string | null;
        sort_position: number;
        lifecycle: "open" | "confirmed_complete";
        suggested_complete: number;
        blocked: number;
      }>;
    const linkRows = this.db
      .prepare(`
        SELECT links.task_id, links.thread_id
        FROM task_thread_links links
        LEFT JOIN observer_thread_exclusions exclusions ON exclusions.thread_id = links.thread_id
        WHERE exclusions.thread_id IS NULL
        ORDER BY links.task_id, links.thread_id
      `)
      .all() as unknown as Array<{ task_id: string; thread_id: string }>;
    const links = new Map<string, string[]>();
    for (const row of linkRows) {
      links.set(row.task_id, [...(links.get(row.task_id) ?? []), row.thread_id]);
    }
    const tasks: DigestTaskInput[] = taskRows.map((row) => ({
      taskId: row.task_id,
      title: row.title,
      clarification: row.clarification,
      position: row.sort_position,
      lifecycle: row.lifecycle,
      suggestedComplete: Boolean(row.suggested_complete),
      blocked: Boolean(row.blocked),
      threadIds: links.get(row.task_id) ?? [],
    }));
    const threadRows = this.db
      .prepare(`
        SELECT threads.id AS thread_id, threads.title,
               COUNT(activities.source_key) AS activity_count,
               MAX(activities.occurred_at) AS last_activity_at,
               EXISTS (
                 SELECT 1 FROM task_thread_links links
                 JOIN tasks ON tasks.id = links.task_id
                 JOIN days ON days.id = tasks.day_id
                 WHERE links.thread_id = threads.id AND days.local_date = ?
               ) AS linked
        FROM observed_threads threads
        JOIN observed_activities activities
          ON activities.thread_id = threads.id AND activities.occurred_at <= ?
        LEFT JOIN observer_thread_exclusions exclusions ON exclusions.thread_id = threads.id
        WHERE exclusions.thread_id IS NULL
          AND activities.occurred_at >= ?
          AND activities.occurred_at < ?
        GROUP BY threads.id, threads.title
      `)
      .all(localDate, cutoff, dayStart, dayEnd) as unknown as Array<{
        thread_id: string;
        title: string | null;
        activity_count: number;
        last_activity_at: string;
        linked: number;
      }>;
    const threads: DigestThreadInput[] = threadRows.map((row) => ({
      threadId: row.thread_id,
      title: row.title,
      activityCount: row.activity_count,
      lastActivityAt: row.last_activity_at,
      linked: Boolean(row.linked),
    }));
    const attention = this.db
      .prepare(`
        SELECT attention.id AS attentionId, attention.thread_id AS threadId,
               attention.kind, attention.certainty, attention.source_label AS label,
               attention.source_occurred_at AS occurredAt
        FROM attention_items attention
        LEFT JOIN observer_thread_exclusions exclusions ON exclusions.thread_id = attention.thread_id
        WHERE attention.lifecycle = 'open'
          AND attention.source_occurred_at <= ?
          AND exclusions.thread_id IS NULL
        ORDER BY attention.certainty, attention.source_occurred_at DESC, attention.id
      `)
      .all(cutoff) as unknown as FactualDigest["outstandingAttention"];
    return buildFactualDigest({ localDate, cutoff, tasks, threads, attention });
  }

  listSnapshots(): ReportSnapshot[] {
    return (
      this.db
        .prepare(`${SNAPSHOT_SELECT} ORDER BY snapshots.created_at DESC, snapshots.sequence DESC`)
        .all() as unknown as SnapshotRow[]
    ).map((row) => this.mapSnapshot(row));
  }

  findSnapshot(id: string): ReportSnapshot | null {
    const row = this.db
      .prepare(`${SNAPSHOT_SELECT} WHERE snapshots.id = ?`)
      .get(id) as unknown as SnapshotRow | undefined;
    return row ? this.mapSnapshot(row) : null;
  }

  latestSnapshot(localDate?: string): ReportSnapshot | null {
    const row = localDate
      ? (this.db
          .prepare(
            `${SNAPSHOT_SELECT} WHERE snapshots.local_date = ?
             ORDER BY snapshots.created_at DESC, snapshots.sequence DESC, snapshots.id DESC
             LIMIT 1`,
          )
          .get(localDate) as unknown as SnapshotRow | undefined)
      : (this.db
          .prepare(`
            ${SNAPSHOT_SELECT}
            ORDER BY snapshots.created_at DESC, snapshots.local_date DESC,
                     snapshots.sequence DESC, snapshots.id DESC
            LIMIT 1
          `)
          .get() as unknown as SnapshotRow | undefined);
    return row ? this.mapSnapshot(row) : null;
  }

  automaticExists(localDate: string): boolean {
    return Boolean(
      this.db
        .prepare("SELECT 1 FROM report_snapshots WHERE automatic_run_key = ?")
        .get(localDate),
    );
  }

  lastAutomaticRunAt(): string | null {
    const row = this.db
      .prepare(`
        SELECT created_at FROM report_snapshots
        WHERE automatic_run_key IS NOT NULL
        ORDER BY created_at DESC LIMIT 1
      `)
      .get() as { created_at: string } | undefined;
    return row?.created_at ?? null;
  }

  getSchedule(): ReportSchedule {
    const row = this.db
      .prepare("SELECT local_time, timezone, narrative_enabled FROM report_schedule_preferences WHERE singleton = 1")
      .get() as unknown as ScheduleRow;
    return {
      time: row.local_time,
      timezone: row.timezone,
      narrativeEnabled: Boolean(row.narrative_enabled),
    };
  }

  timezoneForLocalDate(localDate: string, fallback: string): string {
    const row = this.db
      .prepare(`
        SELECT timezone FROM days WHERE local_date = ?
        UNION ALL
        SELECT timezone FROM report_snapshots WHERE local_date = ?
        LIMIT 1
      `)
      .get(localDate, localDate) as { timezone: string | null } | undefined;
    return row?.timezone ?? fallback;
  }

  updateSchedule(schedule: ReportSchedule, now: string): ReportSchedule {
    this.db
      .prepare(`
        UPDATE report_schedule_preferences
        SET local_time = ?, timezone = ?, narrative_enabled = ?, updated_at = ?
        WHERE singleton = 1
      `)
      .run(schedule.time, schedule.timezone, Number(schedule.narrativeEnabled), now);
    return this.getSchedule();
  }

  markNarrativePending(snapshotId: string, now: string): void {
    this.db
      .prepare(`
        UPDATE report_narratives
        SET status = 'pending', narrative_text = NULL, failure_code = NULL, updated_at = ?
        WHERE snapshot_id = ?
      `)
      .run(now, snapshotId);
  }

  failPendingNarratives(failure: string, now: string): number {
    return Number(
      this.db
        .prepare(`
          UPDATE report_narratives
          SET status = 'failed', narrative_text = NULL, failure_code = ?, updated_at = ?
          WHERE status = 'pending'
        `)
        .run(failure.slice(0, 120), now).changes,
    );
  }

  saveNarrative(
    snapshotId: string,
    text: string,
    suggestions: Array<{ taskId: string; reason: string; sourceThreadIds: string[] }>,
    now: string,
  ): void {
    this.transaction(() => {
      this.db
        .prepare(`
          UPDATE report_narratives
          SET status = 'ready', narrative_text = ?, failure_code = NULL, updated_at = ?
          WHERE snapshot_id = ?
        `)
        .run(text, now, snapshotId);
      const insert = this.db.prepare(`
        INSERT INTO report_completion_suggestions(
          id, snapshot_id, task_id, reason, source_thread_ids_json, superseded_at
        ) VALUES (?, ?, ?, ?, ?, NULL)
      `);
      for (const item of suggestions) {
        insert.run(
          randomUUID(),
          snapshotId,
          item.taskId,
          item.reason,
          JSON.stringify([...new Set(item.sourceThreadIds)].sort()),
        );
      }
    });
  }

  failNarrative(snapshotId: string, failure: string, now: string): void {
    this.db
      .prepare(`
        UPDATE report_narratives
        SET status = 'failed', narrative_text = NULL, failure_code = ?, updated_at = ?
        WHERE snapshot_id = ?
      `)
      .run(failure.slice(0, 120), now, snapshotId);
  }

  registerReportingThread(threadId: string, now: string): void {
    this.transaction(() => {
      this.db
        .prepare(`
          INSERT INTO reporting_thread_roles(thread_id, role, created_at)
          VALUES (?, 'daily_reporter', ?)
          ON CONFLICT(thread_id) DO NOTHING
        `)
        .run(threadId, now);
      this.db
        .prepare(`
          INSERT INTO observer_thread_exclusions(thread_id, reason, created_at)
          VALUES (?, 'reporting', ?)
          ON CONFLICT(thread_id) DO NOTHING
        `)
        .run(threadId, now);
      this.db.prepare("DELETE FROM observed_threads WHERE id = ?").run(threadId);
    });
  }

  reportingThreadId(): string | null {
    const row = this.db
      .prepare("SELECT thread_id FROM reporting_thread_roles ORDER BY created_at LIMIT 1")
      .get() as { thread_id: string } | undefined;
    return row?.thread_id ?? null;
  }

  private mapSnapshot(row: SnapshotRow): ReportSnapshot {
    const suggestions = this.db
      .prepare(`
        SELECT * FROM report_completion_suggestions
        WHERE snapshot_id = ? ORDER BY task_id, id
      `)
      .all(row.id) as unknown as SuggestionRow[];
    return {
      id: row.id,
      localDate: row.local_date,
      sequence: row.sequence,
      timezone: row.timezone,
      trigger: row.trigger,
      cutoff: row.cutoff_at,
      factualDigest: JSON.parse(row.factual_digest_json) as FactualDigest,
      createdAt: row.created_at,
      narrative: {
        status: row.narrative_status,
        text: row.narrative_text,
        failure: row.failure_code,
        suggestions: suggestions.map(suggestion),
      },
    };
  }
}
