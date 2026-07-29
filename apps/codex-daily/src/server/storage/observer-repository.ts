import type { DatabaseSync } from "node:sqlite";
import type {
  ObservedActivity,
  ObservedThread,
  ObservedThreadRuntime,
  TaskThreadLink,
} from "../../shared/observer-types.js";

interface ThreadRow {
  id: string;
  session_id: string;
  title: string | null;
  cwd: string;
  source: string;
  cli_version: string;
  created_at: string;
  updated_at: string;
  recency_at: string | null;
  archived: number;
  last_observed_at: string;
  runtime: ObservedThreadRuntime;
  waiting_on_approval: number;
  waiting_on_user_input: number;
  last_activity_at: string | null;
}

interface ActivityRow {
  source_key: string;
  thread_id: string;
  turn_id: string | null;
  item_id: string | null;
  occurred_at: string;
  category: ObservedActivity["category"];
  lifecycle: string;
  label: string;
}

function mapThread(row: ThreadRow): ObservedThread {
  return {
    id: row.id,
    sessionId: row.session_id,
    title: row.title,
    cwd: row.cwd,
    source: row.source,
    cliVersion: row.cli_version,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    recencyAt: row.recency_at,
    archived: Boolean(row.archived),
    lastObservedAt: row.last_observed_at,
    runtime: row.runtime,
    waitingOnApproval: Boolean(row.waiting_on_approval),
    waitingOnUserInput: Boolean(row.waiting_on_user_input),
    lastActivityAt: row.last_activity_at,
  };
}

function mapActivity(row: ActivityRow): ObservedActivity {
  return {
    sourceKey: row.source_key,
    threadId: row.thread_id,
    turnId: row.turn_id,
    itemId: row.item_id,
    occurredAt: row.occurred_at,
    category: row.category,
    lifecycle: row.lifecycle,
    label: row.label,
  };
}

export class ObserverRepository {
  constructor(private readonly db: DatabaseSync) {}

  isExcluded(threadId: string): boolean {
    return Boolean(
      this.db
        .prepare("SELECT 1 FROM observer_thread_exclusions WHERE thread_id = ?")
        .get(threadId),
    );
  }

  exclude(threadId: string, now: string): void {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(`
          INSERT INTO observer_thread_exclusions(thread_id, reason, created_at)
          VALUES (?, 'reporting', ?)
          ON CONFLICT(thread_id) DO NOTHING
        `)
        .run(threadId, now);
      this.db.prepare("DELETE FROM observed_threads WHERE id = ?").run(threadId);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  upsertThread(thread: ObservedThread): boolean {
    if (this.isExcluded(thread.id)) return false;
    this.db
      .prepare(`
        INSERT INTO observed_threads(
          id, session_id, title, cwd, source, cli_version, created_at, updated_at,
          recency_at, archived, last_observed_at, runtime, waiting_on_approval,
          waiting_on_user_input, last_activity_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          session_id = excluded.session_id,
          title = excluded.title,
          cwd = excluded.cwd,
          source = excluded.source,
          cli_version = excluded.cli_version,
          created_at = excluded.created_at,
          updated_at = excluded.updated_at,
          recency_at = excluded.recency_at,
          archived = excluded.archived,
          last_observed_at = excluded.last_observed_at,
          runtime = excluded.runtime,
          waiting_on_approval = excluded.waiting_on_approval,
          waiting_on_user_input = excluded.waiting_on_user_input,
          last_activity_at = COALESCE(excluded.last_activity_at, observed_threads.last_activity_at)
      `)
      .run(
        thread.id,
        thread.sessionId,
        thread.title,
        thread.cwd,
        thread.source,
        thread.cliVersion,
        thread.createdAt,
        thread.updatedAt,
        thread.recencyAt,
        Number(thread.archived),
        thread.lastObservedAt,
        thread.runtime,
        Number(thread.waitingOnApproval),
        Number(thread.waitingOnUserInput),
        thread.lastActivityAt,
      );
    return true;
  }

  updateRuntime(
    threadId: string,
    runtime: ObservedThreadRuntime,
    waitingOnApproval: boolean,
    waitingOnUserInput: boolean,
    now: string,
  ): void {
    if (this.isExcluded(threadId)) return;
    this.db
      .prepare(`
        UPDATE observed_threads
        SET runtime = ?, waiting_on_approval = ?, waiting_on_user_input = ?,
            last_observed_at = ?
        WHERE id = ?
      `)
      .run(
        runtime,
        Number(waitingOnApproval),
        Number(waitingOnUserInput),
        now,
        threadId,
      );
  }

  setArchived(threadId: string, archived: boolean, now: string): void {
    if (this.isExcluded(threadId)) return;
    this.db
      .prepare("UPDATE observed_threads SET archived = ?, last_observed_at = ? WHERE id = ?")
      .run(Number(archived), now, threadId);
  }

  addActivity(activity: ObservedActivity): boolean {
    if (this.isExcluded(activity.threadId) || !this.findThread(activity.threadId)) return false;
    const result = this.db
      .prepare(`
        INSERT INTO observed_activities(
          source_key, thread_id, turn_id, item_id, occurred_at, category, lifecycle, label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_key) DO NOTHING
      `)
      .run(
        activity.sourceKey,
        activity.threadId,
        activity.turnId,
        activity.itemId,
        activity.occurredAt,
        activity.category,
        activity.lifecycle,
        activity.label,
      );
    if (result.changes) {
      this.db
        .prepare(`
          UPDATE observed_threads
          SET last_activity_at = CASE
            WHEN last_activity_at IS NULL OR last_activity_at < ? THEN ?
            ELSE last_activity_at
          END
          WHERE id = ?
        `)
        .run(activity.occurredAt, activity.occurredAt, activity.threadId);
    }
    return result.changes > 0;
  }

  findThread(id: string): ObservedThread | null {
    if (this.isExcluded(id)) return null;
    const row = this.db
      .prepare("SELECT * FROM observed_threads WHERE id = ?")
      .get(id) as unknown as ThreadRow | undefined;
    return row ? mapThread(row) : null;
  }

  listThreads(): ObservedThread[] {
    const rows = this.db
      .prepare(`
        SELECT threads.*
        FROM observed_threads threads
        LEFT JOIN observer_thread_exclusions exclusions ON exclusions.thread_id = threads.id
        WHERE exclusions.thread_id IS NULL
        ORDER BY COALESCE(threads.recency_at, threads.updated_at) DESC, threads.id
      `)
      .all() as unknown as ThreadRow[];
    return rows.map(mapThread);
  }

  listActivities(limit = 200): ObservedActivity[] {
    const rows = this.db
      .prepare(`
        SELECT activities.*
        FROM observed_activities activities
        LEFT JOIN observer_thread_exclusions exclusions
          ON exclusions.thread_id = activities.thread_id
        WHERE exclusions.thread_id IS NULL
        ORDER BY activities.occurred_at DESC, activities.source_key
        LIMIT ?
      `)
      .all(limit) as unknown as ActivityRow[];
    return rows.map(mapActivity);
  }

  listLinks(): TaskThreadLink[] {
    return this.db
      .prepare(`
        SELECT links.task_id AS taskId, links.thread_id AS threadId, links.created_at AS createdAt
        FROM task_thread_links links
        JOIN tasks ON tasks.id = links.task_id
        JOIN observed_threads threads ON threads.id = links.thread_id
        LEFT JOIN observer_thread_exclusions exclusions ON exclusions.thread_id = links.thread_id
        WHERE exclusions.thread_id IS NULL
        ORDER BY links.created_at, links.task_id, links.thread_id
      `)
      .all() as unknown as TaskThreadLink[];
  }

  link(taskId: string, threadId: string, now: string): "linked" | "missing_task" | "missing_thread" {
    if (!this.db.prepare("SELECT 1 FROM tasks WHERE id = ?").get(taskId)) return "missing_task";
    if (!this.findThread(threadId)) return "missing_thread";
    this.db
      .prepare(`
        INSERT INTO task_thread_links(task_id, thread_id, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(task_id, thread_id) DO NOTHING
      `)
      .run(taskId, threadId, now);
    return "linked";
  }

  unlink(taskId: string, threadId: string): "unlinked" | "missing_task" | "missing_thread" {
    if (!this.db.prepare("SELECT 1 FROM tasks WHERE id = ?").get(taskId)) return "missing_task";
    if (!this.findThread(threadId)) return "missing_thread";
    this.db
      .prepare("DELETE FROM task_thread_links WHERE task_id = ? AND thread_id = ?")
      .run(taskId, threadId);
    return "unlinked";
  }
}
