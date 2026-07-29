import type { DatabaseSync } from "node:sqlite";
import type {
  CodexDailyExport,
  DeleteResult,
  ExportReviewDecision,
  RetainedCategoryCount,
  RetainedDateRange,
} from "../../shared/operations.js";
import { DELETE_ALL_CONFIRMATION } from "../../shared/operations.js";
import type { AttentionItem } from "../../shared/attention.js";
import type {
  ObservedActivity,
  ObservedThread,
  TaskThreadLink,
} from "../../shared/observer-types.js";
import type { PlanningTask } from "../../shared/planning.js";
import { assertLocalDate } from "../planning/local-date.js";
import { reportDayBounds } from "../reports/report-time.js";
import { ReportRepository } from "../reports/report-repository.js";
import { WriteCoordinator } from "../runtime/write-coordinator.js";

const REDISCOVERY_NOTICE =
  "Only Codex Daily local monitor data changed. Resuming monitoring can rediscover current Codex thread metadata; Codex history is untouched.";

export class PrivacyConfirmationError extends Error {}

export interface PrivacyServiceOptions {
  database: DatabaseSync;
  reports: ReportRepository;
  coordinator: WriteCoordinator;
  clock?: () => Date;
  pauseWriters: () => Promise<void>;
  resumeWriters: () => Promise<void>;
}

export class PrivacyService {
  private readonly db: DatabaseSync;
  private readonly reports: ReportRepository;
  private readonly coordinator: WriteCoordinator;
  private readonly clock: () => Date;
  private readonly pauseWriters: () => Promise<void>;
  private readonly resumeWriters: () => Promise<void>;

  constructor(options: PrivacyServiceOptions) {
    this.db = options.database;
    this.reports = options.reports;
    this.coordinator = options.coordinator;
    this.clock = options.clock ?? (() => new Date());
    this.pauseWriters = options.pauseWriters;
    this.resumeWriters = options.resumeWriters;
  }

  retainedCounts(): RetainedCategoryCount[] {
    const definitions: Array<[RetainedCategoryCount["category"], string]> = [
      ["days", "days"],
      ["tasks", "tasks"],
      ["reviewDecisions", "task_review_decisions"],
      ["taskLinks", "task_thread_links"],
      ["threads", "observed_threads"],
      ["activities", "observed_activities"],
      ["attention", "attention_items"],
      ["reports", "report_snapshots"],
      ["narratives", "report_narratives"],
      ["suggestions", "report_completion_suggestions"],
      ["observerExclusions", "observer_thread_exclusions"],
      ["reportingRoles", "reporting_thread_roles"],
      ["preferences", "report_schedule_preferences"],
    ];
    return definitions.map(([category, table]) => ({
      category,
      count: Number(
        (this.db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get() as {
          count: number;
        }).count,
      ),
    }));
  }

  retainedDates(): RetainedDateRange {
    const row = this.db
      .prepare(`
        SELECT MIN(local_date) AS oldest, MAX(local_date) AS newest
        FROM (
          SELECT local_date FROM days
          UNION ALL
          SELECT local_date FROM report_snapshots
        )
      `)
      .get() as { oldest: string | null; newest: string | null };
    return { oldest: row.oldest, newest: row.newest };
  }

  databaseHealth(): {
    status: "ok" | "error";
    schemaVersion: string | null;
    foreignKeyViolations: number;
  } {
    try {
      const quick = this.db.prepare("PRAGMA quick_check").get() as Record<
        string,
        unknown
      >;
      const schema = this.db
        .prepare("SELECT MAX(version) AS version FROM schema_migrations")
        .get() as { version: string | null };
      const foreignKeyViolations = this.db
        .prepare("PRAGMA foreign_key_check")
        .all().length;
      return {
        status:
          Object.values(quick)[0] === "ok" && foreignKeyViolations === 0
            ? "ok"
            : "error",
        schemaVersion: schema.version,
        foreignKeyViolations,
      };
    } catch {
      return {
        status: "error",
        schemaVersion: null,
        foreignKeyViolations: 0,
      };
    }
  }

  export(): CodexDailyExport {
    const days = this.db
      .prepare(`
        SELECT id, local_date AS localDate, created_at AS createdAt,
               updated_at AS updatedAt, timezone
        FROM days ORDER BY local_date, id
      `)
      .all() as unknown as CodexDailyExport["days"];
    const tasks = this.db
      .prepare(`
        SELECT tasks.id, days.local_date AS localDate, tasks.title,
               tasks.clarification, tasks.sort_position AS position,
               tasks.lifecycle, tasks.origin_task_id AS originTaskId,
               tasks.created_at AS createdAt, tasks.updated_at AS updatedAt,
               tasks.completed_at AS completedAt, tasks.closed_at AS closedAt
        FROM tasks JOIN days ON days.id = tasks.day_id
        ORDER BY days.local_date, tasks.sort_position, tasks.created_at, tasks.id
      `)
      .all() as unknown as PlanningTask[];
    const reviewDecisions = this.db
      .prepare(`
        SELECT source_task_id AS sourceTaskId, action,
               target_local_date AS targetLocalDate,
               successor_task_id AS successorTaskId, decided_at AS decidedAt
        FROM task_review_decisions ORDER BY decided_at, source_task_id
      `)
      .all() as unknown as ExportReviewDecision[];
    const threads = this.db
      .prepare(`
        SELECT id, session_id AS sessionId, title, cwd, source,
               cli_version AS cliVersion, created_at AS createdAt,
               updated_at AS updatedAt, recency_at AS recencyAt,
               archived, last_observed_at AS lastObservedAt, runtime,
               waiting_on_approval AS waitingOnApproval,
               waiting_on_user_input AS waitingOnUserInput,
               last_activity_at AS lastActivityAt
        FROM observed_threads ORDER BY id
      `)
      .all()
      .map((row) => {
        const value = row as Record<string, unknown>;
        return {
          ...value,
          archived: Boolean(value.archived),
          waitingOnApproval: Boolean(value.waitingOnApproval),
          waitingOnUserInput: Boolean(value.waitingOnUserInput),
        } as unknown as ObservedThread;
      });
    const activities = this.db
      .prepare(`
        SELECT source_key AS sourceKey, thread_id AS threadId,
               turn_id AS turnId, item_id AS itemId, occurred_at AS occurredAt,
               category, lifecycle, label
        FROM observed_activities ORDER BY occurred_at, source_key
      `)
      .all() as unknown as ObservedActivity[];
    const taskLinks = this.db
      .prepare(`
        SELECT task_id AS taskId, thread_id AS threadId, created_at AS createdAt
        FROM task_thread_links ORDER BY task_id, thread_id
      `)
      .all() as unknown as TaskThreadLink[];
    const attention = this.db
      .prepare(`
        SELECT id, source_key AS sourceKey, thread_id AS threadId,
               turn_id AS turnId, item_id AS itemId, kind, certainty,
               source_occurred_at AS sourceOccurredAt,
               last_derived_at AS lastDerivedAt, source_label AS sourceLabel,
               lifecycle, local_action_at AS localActionAt
        FROM attention_items ORDER BY source_occurred_at, id
      `)
      .all() as unknown as AttentionItem[];
    const observerExclusions = this.db
      .prepare(`
        SELECT thread_id AS threadId, reason, created_at AS createdAt
        FROM observer_thread_exclusions ORDER BY thread_id
      `)
      .all() as unknown as CodexDailyExport["observerExclusions"];
    const reportingRoles = this.db
      .prepare(`
        SELECT thread_id AS threadId, role, created_at AS createdAt
        FROM reporting_thread_roles ORDER BY thread_id
      `)
      .all() as unknown as CodexDailyExport["reportingRoles"];
    return {
      product: "codex-daily",
      schemaVersion: 1,
      exportedAt: this.clock().toISOString(),
      schedule: this.reports.getSchedule(),
      days,
      tasks,
      reviewDecisions,
      threads,
      activities,
      taskLinks,
      attention,
      reports: [...this.reports.listSnapshots()].reverse(),
      observerExclusions,
      reportingRoles,
    };
  }

  async deleteDay(localDateInput: string, confirmation: string): Promise<DeleteResult> {
    const localDate = assertLocalDate(localDateInput);
    if (confirmation !== `DELETE ${localDate}`) {
      throw new PrivacyConfirmationError(`Type DELETE ${localDate} to confirm.`);
    }
    return this.coordinator.exclusive(
      this.pauseWriters,
      () => this.deleteDayTransaction(localDate),
      this.resumeWriters,
    );
  }

  async deleteAll(confirmation: string): Promise<DeleteResult> {
    if (confirmation !== DELETE_ALL_CONFIRMATION) {
      throw new PrivacyConfirmationError(
        `Type ${DELETE_ALL_CONFIRMATION} to confirm.`,
      );
    }
    return this.coordinator.exclusive(
      this.pauseWriters,
      () => this.deleteAllTransaction(),
      this.resumeWriters,
    );
  }

  private deleteDayTransaction(localDate: string): DeleteResult {
    const before = this.retainedCounts();
    const timezone = this.reports.timezoneForLocalDate(
      localDate,
      this.reports.getSchedule().timezone,
    );
    const bounds = reportDayBounds(localDate, timezone);
    this.transaction(() => {
      this.db
        .prepare(`
          DELETE FROM task_review_decisions
          WHERE source_task_id IN (
            SELECT tasks.id FROM tasks
            JOIN days ON days.id = tasks.day_id
            WHERE days.local_date = ?
          )
          OR successor_task_id IN (
            SELECT tasks.id FROM tasks
            JOIN days ON days.id = tasks.day_id
            WHERE days.local_date = ?
          )
        `)
        .run(localDate, localDate);
      this.db
        .prepare(`
          UPDATE tasks SET origin_task_id = NULL
          WHERE origin_task_id IN (
            SELECT tasks.id FROM tasks
            JOIN days ON days.id = tasks.day_id
            WHERE days.local_date = ?
          )
        `)
        .run(localDate);
      this.db
        .prepare("DELETE FROM report_snapshots WHERE local_date = ?")
        .run(localDate);
      this.db
        .prepare(`
          DELETE FROM attention_items
          WHERE source_occurred_at >= ? AND source_occurred_at < ?
        `)
        .run(bounds.start, bounds.end);
      this.db
        .prepare(`
          DELETE FROM observed_activities
          WHERE occurred_at >= ? AND occurred_at < ?
        `)
        .run(bounds.start, bounds.end);
      this.db.exec(`
        UPDATE observed_threads
        SET last_activity_at = (
          SELECT MAX(activities.occurred_at)
          FROM observed_activities activities
          WHERE activities.thread_id = observed_threads.id
        )
      `);
      this.db.prepare("DELETE FROM days WHERE local_date = ?").run(localDate);
    });
    return {
      scope: "day",
      localDate,
      deleted: countDifference(before, this.retainedCounts()),
      preferencesReset: false,
      codexHistoryChanged: false,
      rediscoveryNotice: REDISCOVERY_NOTICE,
    };
  }

  private deleteAllTransaction(): DeleteResult {
    const before = this.retainedCounts();
    const now = this.clock().toISOString();
    this.transaction(() => {
      this.db.exec(`
        DELETE FROM report_snapshots;
        DELETE FROM reporting_thread_roles;
        DELETE FROM attention_items;
        DELETE FROM task_thread_links;
        DELETE FROM observed_activities;
        DELETE FROM observed_threads;
        DELETE FROM observer_thread_exclusions;
        DELETE FROM task_review_decisions;
        DELETE FROM tasks;
        DELETE FROM days;
        DELETE FROM report_schedule_preferences;
      `);
      this.db
        .prepare(`
          INSERT INTO report_schedule_preferences(
            singleton, local_time, timezone, narrative_enabled, updated_at
          ) VALUES (1, '18:00', 'Europe/Berlin', 0, ?)
        `)
        .run(now);
    });
    return {
      scope: "all",
      localDate: null,
      deleted: countDifference(before, this.retainedCounts()),
      preferencesReset: true,
      codexHistoryChanged: false,
      rediscoveryNotice: REDISCOVERY_NOTICE,
    };
  }

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
}

function countDifference(
  before: RetainedCategoryCount[],
  after: RetainedCategoryCount[],
): RetainedCategoryCount[] {
  const current = new Map(after.map((item) => [item.category, item.count]));
  return before.map((item) => ({
    category: item.category,
    count: Math.max(0, item.count - (current.get(item.category) ?? 0)),
  }));
}
