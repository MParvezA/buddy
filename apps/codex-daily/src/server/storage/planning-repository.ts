import { randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import type { PlanningTask, ReviewAction } from "../../shared/planning.js";

interface TaskRow {
  id: string;
  local_date: string;
  title: string;
  clarification: string | null;
  sort_position: number;
  lifecycle: PlanningTask["lifecycle"];
  origin_task_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  closed_at: string | null;
}

interface DecisionRow {
  action: ReviewAction;
  target_local_date: string | null;
  successor_task_id: string | null;
}

function task(row: TaskRow): PlanningTask {
  return {
    id: row.id,
    localDate: row.local_date,
    title: row.title,
    clarification: row.clarification,
    position: row.sort_position,
    lifecycle: row.lifecycle,
    originTaskId: row.origin_task_id,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    completedAt: row.completed_at,
    closedAt: row.closed_at,
  };
}

export class PlanningRepository {
  constructor(private readonly db: DatabaseSync) {}

  transaction<T>(work: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const value = work();
      this.db.exec("COMMIT");
      return value;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  ensureDay(localDate: string, now: string): string {
    const existing = this.db
      .prepare("SELECT id FROM days WHERE local_date = ?")
      .get(localDate) as { id: string } | undefined;
    if (existing) return existing.id;
    const id = randomUUID();
    this.db
      .prepare("INSERT INTO days(id, local_date, created_at, updated_at) VALUES (?, ?, ?, ?)")
      .run(id, localDate, now, now);
    return id;
  }

  listTasks(localDate: string): PlanningTask[] {
    const rows = this.db
      .prepare(`
        SELECT tasks.*, days.local_date
        FROM tasks JOIN days ON days.id = tasks.day_id
        WHERE days.local_date = ? AND tasks.lifecycle != 'closed'
        ORDER BY tasks.sort_position, tasks.created_at, tasks.id
      `)
      .all(localDate) as unknown as TaskRow[];
    return rows.map(task);
  }

  listUnresolved(localDate: string): PlanningTask[] {
    const rows = this.db
      .prepare(`
        SELECT tasks.*, days.local_date
        FROM tasks JOIN days ON days.id = tasks.day_id
        LEFT JOIN task_review_decisions decisions ON decisions.source_task_id = tasks.id
        WHERE days.local_date = ? AND tasks.lifecycle = 'open' AND decisions.id IS NULL
        ORDER BY tasks.sort_position, tasks.created_at, tasks.id
      `)
      .all(localDate) as unknown as TaskRow[];
    return rows.map(task);
  }

  findTask(id: string): PlanningTask | null {
    const row = this.db
      .prepare(`
        SELECT tasks.*, days.local_date
        FROM tasks JOIN days ON days.id = tasks.day_id
        WHERE tasks.id = ?
      `)
      .get(id) as unknown as TaskRow | undefined;
    return row ? task(row) : null;
  }

  nextPosition(localDate: string): number {
    const row = this.db
      .prepare(`
        SELECT COALESCE(MAX(tasks.sort_position), -1) + 1 AS position
        FROM tasks JOIN days ON days.id = tasks.day_id
        WHERE days.local_date = ? AND tasks.lifecycle != 'closed'
      `)
      .get(localDate) as { position: number };
    return row.position;
  }

  createTask(input: {
    localDate: string;
    title: string;
    clarification: string | null;
    position: number;
    originTaskId?: string | null;
    now: string;
  }): PlanningTask {
    const dayId = this.ensureDay(input.localDate, input.now);
    const id = randomUUID();
    this.db
      .prepare(`
        INSERT INTO tasks(
          id, day_id, title, clarification, sort_position, lifecycle,
          origin_task_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)
      `)
      .run(
        id,
        dayId,
        input.title,
        input.clarification,
        input.position,
        input.originTaskId ?? null,
        input.now,
        input.now,
      );
    return this.findTask(id)!;
  }

  updateTask(id: string, title: string, clarification: string | null, now: string): void {
    this.db
      .prepare("UPDATE tasks SET title = ?, clarification = ?, updated_at = ? WHERE id = ?")
      .run(title, clarification, now, id);
  }

  updateLifecycle(
    id: string,
    lifecycle: PlanningTask["lifecycle"],
    now: string,
  ): void {
    this.db
      .prepare(`
        UPDATE tasks
        SET lifecycle = ?, updated_at = ?,
            completed_at = CASE WHEN ? = 'confirmed_complete' THEN ? ELSE NULL END,
            closed_at = CASE WHEN ? = 'closed' THEN ? ELSE NULL END
        WHERE id = ?
      `)
      .run(lifecycle, now, lifecycle, now, lifecycle, now, id);
  }

  reorder(ids: string[], now: string): void {
    const statement = this.db.prepare(
      "UPDATE tasks SET sort_position = ?, updated_at = ? WHERE id = ?",
    );
    ids.forEach((id, position) => statement.run(position, now, id));
  }

  findDecision(sourceTaskId: string): DecisionRow | null {
    return (
      (this.db
        .prepare(`
          SELECT action, target_local_date, successor_task_id
          FROM task_review_decisions WHERE source_task_id = ?
        `)
        .get(sourceTaskId) as unknown as DecisionRow | undefined) ?? null
    );
  }

  recordDecision(input: {
    sourceTaskId: string;
    action: ReviewAction;
    targetLocalDate: string | null;
    successorTaskId: string | null;
    now: string;
  }): void {
    this.db
      .prepare(`
        INSERT INTO task_review_decisions(
          id, source_task_id, action, target_local_date, successor_task_id, decided_at
        ) VALUES (?, ?, ?, ?, ?, ?)
      `)
      .run(
        randomUUID(),
        input.sourceTaskId,
        input.action,
        input.targetLocalDate,
        input.successorTaskId,
        input.now,
      );
  }
}
