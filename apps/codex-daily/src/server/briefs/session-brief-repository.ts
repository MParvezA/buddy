import { randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import type {
  SessionBriefContent,
  SessionBriefFailureCategory,
  SessionBriefItem,
  SessionBriefJobReason,
  SessionBriefLastGood,
} from "../../shared/session-briefs.js";
import {
  assertSessionBriefContent,
  assertSessionBriefLastGood,
} from "./session-brief-validator.js";

type PersistedJobStatus = "queued" | "analyzing" | "unavailable" | "failed";

interface BriefRow {
  thread_id: string;
  source_updated_at: string;
  generated_at: string;
  generator: string;
  model_id: string | null;
  current_state: string;
  done_json: string;
  operator_actions_json: string;
  blockers_json: string;
  confidence: SessionBriefLastGood["confidence"];
  evidence_json: string;
  updated_at: string;
  out_of_window_at: string | null;
}

interface JobRow {
  thread_id: string;
  job_id: string;
  target_updated_at: string;
  reason: SessionBriefJobReason;
  status: PersistedJobStatus;
  attempt_count: number;
  queued_at: string;
  started_at: string | null;
  failure_category: SessionBriefFailureCategory | null;
  failure_at: string | null;
  updated_at: string;
}

export interface SessionBriefJob {
  threadId: string;
  jobId: string;
  targetUpdatedAt: string;
  reason: SessionBriefJobReason;
  status: PersistedJobStatus;
  attemptCount: number;
  queuedAt: string;
  startedAt: string | null;
  failureCategory: SessionBriefFailureCategory | null;
  failureAt: string | null;
  updatedAt: string;
}

function mapJob(row: JobRow): SessionBriefJob {
  return {
    threadId: row.thread_id,
    jobId: row.job_id,
    targetUpdatedAt: row.target_updated_at,
    reason: row.reason,
    status: row.status,
    attemptCount: row.attempt_count,
    queuedAt: row.queued_at,
    startedAt: row.started_at,
    failureCategory: row.failure_category,
    failureAt: row.failure_at,
    updatedAt: row.updated_at,
  };
}

function parseLastGood(row: BriefRow | undefined): SessionBriefLastGood | null {
  if (!row) return null;
  try {
    return assertSessionBriefLastGood({
      sourceUpdatedAt: row.source_updated_at,
      generatedAt: row.generated_at,
      generator: row.generator,
      modelId: row.model_id,
      currentState: row.current_state,
      done: JSON.parse(row.done_json) as unknown,
      operatorActions: JSON.parse(row.operator_actions_json) as unknown,
      blockers: JSON.parse(row.blockers_json) as unknown,
      confidence: row.confidence,
      evidence: JSON.parse(row.evidence_json) as unknown,
    });
  } catch {
    return null;
  }
}

export class SessionBriefRepository {
  constructor(
    private readonly db: DatabaseSync,
    private readonly createId: () => string = randomUUID,
  ) {}

  advanceCoordinatorEpoch(): number {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(`
          UPDATE session_brief_coordinator_state
          SET epoch = epoch + 1
          WHERE singleton_id = 1
        `)
        .run();
      const epoch = this.currentCoordinatorEpoch();
      this.db.exec("COMMIT");
      return epoch;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  currentCoordinatorEpoch(): number {
    const row = this.db
      .prepare(`
        SELECT epoch FROM session_brief_coordinator_state
        WHERE singleton_id = 1
      `)
      .get() as { epoch: number } | undefined;
    if (!row || !Number.isSafeInteger(row.epoch) || row.epoch < 0) {
      throw new Error("Session brief coordinator epoch is invalid.");
    }
    return row.epoch;
  }

  recoverAnalyzing(now: string): number {
    return Number(
      this.db
      .prepare(`
        UPDATE session_brief_jobs
        SET status = 'queued', started_at = NULL, updated_at = ?
        WHERE status = 'analyzing'
      `)
        .run(now).changes,
    );
  }

  enqueue(
    threadId: string,
    targetUpdatedAt: string,
    reason: SessionBriefJobReason,
    now: string,
    force = false,
  ): SessionBriefJob | null {
    const current = this.findJob(threadId);
    if (
      current &&
      current.targetUpdatedAt === targetUpdatedAt &&
      (current.status === "queued" || current.status === "analyzing") &&
      (!force || current.reason === "manual")
    ) {
      return current;
    }
    if (
      !force &&
      current &&
      current.targetUpdatedAt === targetUpdatedAt
    ) {
      return current;
    }
    const jobId = this.createId();
    this.db
      .prepare(`
        INSERT INTO session_brief_jobs(
          thread_id, job_id, target_updated_at, reason, status, attempt_count,
          queued_at, started_at, failure_category, failure_at, updated_at
        ) VALUES (?, ?, ?, ?, 'queued', 0, ?, NULL, NULL, NULL, ?)
        ON CONFLICT(thread_id) DO UPDATE SET
          job_id = excluded.job_id,
          target_updated_at = excluded.target_updated_at,
          reason = excluded.reason,
          status = 'queued',
          attempt_count = 0,
          queued_at = excluded.queued_at,
          started_at = NULL,
          failure_category = NULL,
          failure_at = NULL,
          updated_at = excluded.updated_at
      `)
      .run(threadId, jobId, targetUpdatedAt, reason, now, now);
    return this.findJob(threadId);
  }

  findJob(threadId: string): SessionBriefJob | null {
    const row = this.db
      .prepare("SELECT * FROM session_brief_jobs WHERE thread_id = ?")
      .get(threadId) as unknown as JobRow | undefined;
    return row ? mapJob(row) : null;
  }

  listDueQueued(now: string): SessionBriefJob[] {
    return (
      this.db
        .prepare(`
          SELECT * FROM session_brief_jobs
          WHERE status = 'queued' AND queued_at <= ?
        `)
        .all(now) as unknown as JobRow[]
    ).map(mapJob);
  }

  nextQueuedAt(): string | null {
    const row = this.db
      .prepare(`
        SELECT queued_at FROM session_brief_jobs
        WHERE status = 'queued'
        ORDER BY queued_at, thread_id
        LIMIT 1
      `)
      .get() as { queued_at: string } | undefined;
    return row?.queued_at ?? null;
  }

  markAnalyzing(jobId: string, now: string): SessionBriefJob | null {
    this.db
      .prepare(`
        UPDATE session_brief_jobs
        SET status = 'analyzing', attempt_count = attempt_count + 1,
            started_at = ?, failure_category = NULL, failure_at = NULL,
            updated_at = ?
        WHERE job_id = ? AND status = 'queued'
      `)
      .run(now, now, jobId);
    const row = this.db
      .prepare("SELECT * FROM session_brief_jobs WHERE job_id = ?")
      .get(jobId) as unknown as JobRow | undefined;
    return row?.status === "analyzing" ? mapJob(row) : null;
  }

  markFailure(
    jobId: string,
    category: SessionBriefFailureCategory,
    now: string,
    status: "unavailable" | "failed" = "failed",
  ): boolean {
    return (
      Number(
        this.db
      .prepare(`
        UPDATE session_brief_jobs
        SET status = ?, failure_category = ?, failure_at = ?, started_at = NULL,
            updated_at = ?
        WHERE job_id = ? AND status = 'analyzing'
      `)
          .run(status, category, now, now, jobId).changes,
      ) > 0
    );
  }

  scheduleRetry(
    jobId: string,
    category: SessionBriefFailureCategory,
    failureAt: string,
    dueAt: string,
  ): boolean {
    return Number(
      this.db
        .prepare(`
          UPDATE session_brief_jobs
          SET reason = 'retry', status = 'queued', queued_at = ?,
              started_at = NULL, failure_category = ?, failure_at = ?,
              updated_at = ?
          WHERE job_id = ? AND status = 'analyzing'
        `)
        .run(dueAt, category, failureAt, failureAt, jobId).changes,
    ) > 0;
  }

  deletePlaceholderArtifacts(): number {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db
        .prepare(`
          DELETE FROM session_brief_jobs
          WHERE thread_id IN (
            SELECT thread_id FROM session_briefs
            WHERE generator = 'deterministic_placeholder'
          )
        `)
        .run();
      const removed = Number(
        this.db
          .prepare(
            "DELETE FROM session_briefs WHERE generator = 'deterministic_placeholder'",
          )
          .run().changes,
      );
      this.db
        .prepare(`
          DELETE FROM session_brief_jobs
          WHERE thread_id NOT IN (SELECT id FROM observed_threads)
        `)
        .run();
      this.db.exec("COMMIT");
      return removed;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  promote(
    jobId: string,
    threadId: string,
    targetUpdatedAt: string,
    result: {
      content: SessionBriefContent;
      generator: string;
      modelId: string | null;
    },
    now: string,
    expectedCoordinatorEpoch: number,
  ): boolean {
    const content = assertSessionBriefContent(result.content);
    const stored = assertSessionBriefLastGood({
      ...content,
      sourceUpdatedAt: targetUpdatedAt,
      generatedAt: now,
      generator: result.generator,
      modelId: result.modelId,
    });
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const activeEpoch = this.db
        .prepare(`
          SELECT 1 FROM session_brief_coordinator_state
          WHERE singleton_id = 1 AND epoch = ?
        `)
        .get(expectedCoordinatorEpoch);
      const current = this.db
        .prepare(`
          SELECT 1 FROM session_brief_jobs
          WHERE thread_id = ? AND job_id = ? AND target_updated_at = ?
            AND status = 'analyzing'
        `)
        .get(threadId, jobId, targetUpdatedAt);
      if (!activeEpoch || !current) {
        this.db.exec("ROLLBACK");
        return false;
      }
      this.db
        .prepare(`
          INSERT INTO session_briefs(
            thread_id, source_updated_at, generated_at, generator, model_id,
            current_state, done_json, operator_actions_json, blockers_json,
            confidence, evidence_json, updated_at, out_of_window_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
          ON CONFLICT(thread_id) DO UPDATE SET
            source_updated_at = excluded.source_updated_at,
            generated_at = excluded.generated_at,
            generator = excluded.generator,
            model_id = excluded.model_id,
            current_state = excluded.current_state,
            done_json = excluded.done_json,
            operator_actions_json = excluded.operator_actions_json,
            blockers_json = excluded.blockers_json,
            confidence = excluded.confidence,
            evidence_json = excluded.evidence_json,
            updated_at = excluded.updated_at,
            out_of_window_at = NULL
        `)
        .run(
          threadId,
          stored.sourceUpdatedAt,
          stored.generatedAt,
          stored.generator,
          stored.modelId,
          stored.currentState,
          JSON.stringify(stored.done),
          JSON.stringify(stored.operatorActions),
          JSON.stringify(stored.blockers),
          stored.confidence,
          JSON.stringify(stored.evidence),
          now,
        );
      this.db
        .prepare("DELETE FROM session_brief_jobs WHERE job_id = ?")
        .run(jobId);
      this.db.exec("COMMIT");
      return true;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  reconcileWindow(
    selectedThreadIds: string[],
    now: string,
    expiryCutoff: string,
  ): void {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const selected = new Set(selectedThreadIds);
      const briefRows = this.db
        .prepare("SELECT thread_id FROM session_briefs")
        .all() as unknown as Array<{ thread_id: string }>;
      for (const row of briefRows) {
        if (selected.has(row.thread_id)) {
          this.db
            .prepare(`
              UPDATE session_briefs SET out_of_window_at = NULL
              WHERE thread_id = ?
            `)
            .run(row.thread_id);
        } else {
          this.db
            .prepare(`
              UPDATE session_briefs
              SET out_of_window_at = COALESCE(out_of_window_at, ?)
              WHERE thread_id = ?
            `)
            .run(now, row.thread_id);
        }
      }
      const jobRows = this.db
        .prepare("SELECT thread_id FROM session_brief_jobs")
        .all() as unknown as Array<{ thread_id: string }>;
      for (const row of jobRows) {
        if (!selected.has(row.thread_id)) {
          this.db
            .prepare("DELETE FROM session_brief_jobs WHERE thread_id = ?")
            .run(row.thread_id);
        }
      }
      this.db
        .prepare(`
          DELETE FROM session_briefs
          WHERE out_of_window_at IS NOT NULL AND out_of_window_at <= ?
        `)
        .run(expiryCutoff);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  prune(expiryCutoff: string): number {
    return Number(
      this.db
      .prepare(`
        DELETE FROM session_briefs
        WHERE out_of_window_at IS NOT NULL AND out_of_window_at <= ?
      `)
        .run(expiryCutoff).changes,
    );
  }

  item(threadId: string, targetUpdatedAt: string, now: string): SessionBriefItem {
    const briefRow = this.db
      .prepare("SELECT * FROM session_briefs WHERE thread_id = ?")
      .get(threadId) as unknown as BriefRow | undefined;
    const job = this.findJob(threadId);
    const lastGood = parseLastGood(briefRow);
    const freshness = lastGood
      ? lastGood.sourceUpdatedAt === targetUpdatedAt
        ? "current"
        : "stale"
      : "missing";
    const failure =
      job?.failureCategory && job.failureAt
        ? { category: job.failureCategory, at: job.failureAt }
        : null;
    return {
      threadId,
      targetUpdatedAt,
      analysisStatus: job?.status ?? (freshness === "current" ? "ready" : "unavailable"),
      freshness,
      lastGood,
      failure,
      queuedAt: job?.queuedAt ?? null,
      startedAt: job?.startedAt ?? null,
      updatedAt: job?.updatedAt ?? briefRow?.updated_at ?? now,
    };
  }

  listBriefRowsForExport(): Array<{
    threadId: string;
    lastGood: SessionBriefLastGood;
    updatedAt: string;
    outOfWindowAt: string | null;
  }> {
    const rows = this.db
      .prepare("SELECT * FROM session_briefs ORDER BY thread_id")
      .all() as unknown as BriefRow[];
    return rows.flatMap((row) => {
      const lastGood = parseLastGood(row);
      return lastGood
        ? [{
            threadId: row.thread_id,
            lastGood,
            updatedAt: row.updated_at,
            outOfWindowAt: row.out_of_window_at,
          }]
        : [];
    });
  }

  listJobsForExport(): SessionBriefJob[] {
    return (
      this.db
        .prepare("SELECT * FROM session_brief_jobs ORDER BY thread_id")
        .all() as unknown as JobRow[]
    ).map(mapJob);
  }
}
