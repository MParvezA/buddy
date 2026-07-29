// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import type { DatabaseSync } from "node:sqlite";
import { ReportRepository } from "../../../src/server/reports/report-repository.js";
import { openDatabase, type PlanningDatabase } from "../../../src/server/storage/database.js";

let database: PlanningDatabase | undefined;

afterEach(() => {
  database?.close();
  database = undefined;
});

function setup(): { db: DatabaseSync; reports: ReportRepository } {
  database = openDatabase({ path: ":memory:" });
  const db = database.connection;
  db.prepare("INSERT INTO days(id, local_date, created_at, updated_at) VALUES (?, ?, ?, ?)")
    .run("day", "2026-03-29", "2026-03-29T00:00:00Z", "2026-03-29T00:00:00Z");
  for (const [id, title, position, lifecycle] of [
    ["done", "Confirmed", 0, "confirmed_complete"],
    ["blocked", "Blocked", 1, "open"],
    ["pending", "Pending", 2, "open"],
  ] as const) {
    db.prepare(`
      INSERT INTO tasks(
        id, day_id, title, clarification, sort_position, lifecycle,
        origin_task_id, created_at, updated_at, completed_at, closed_at
      ) VALUES (?, 'day', ?, NULL, ?, ?, NULL, ?, ?, NULL, NULL)
    `).run(id, title, position, lifecycle, "2026-03-29T00:00:00Z", "2026-03-29T00:00:00Z");
  }
  for (const [id, title] of [
    ["linked", "Linked work"],
    ["inside", "Inside local day"],
    ["outside", "Outside local day"],
  ]) {
    db.prepare(`
      INSERT INTO observed_threads(
        id, session_id, title, cwd, source, cli_version, created_at, updated_at,
        recency_at, archived, last_observed_at, runtime, waiting_on_approval,
        waiting_on_user_input, last_activity_at
      ) VALUES (?, ?, ?, '/repo', 'cli', '1', ?, ?, ?, 0, ?, 'idle', 0, 0, ?)
    `).run(
      id,
      id,
      title,
      "2026-03-28T23:00:00.000Z",
      "2026-03-29T22:30:00.000Z",
      "2026-03-29T22:30:00.000Z",
      "2026-03-29T22:30:00.000Z",
      "2026-03-29T22:30:00.000Z",
    );
  }
  db.prepare("INSERT INTO task_thread_links(task_id, thread_id, created_at) VALUES ('blocked', 'linked', ?)")
    .run("2026-03-29T00:00:00.000Z");
  db.prepare(`
    INSERT INTO attention_items(
      id, source_key, thread_id, turn_id, item_id, kind, certainty,
      source_occurred_at, last_derived_at, source_label, lifecycle, local_action_at
    ) VALUES ('attention', 'blocker', 'linked', NULL, NULL, 'explicit_blocker',
      'explicit', ?, ?, 'Explicit blocker', 'open', NULL)
  `).run("2026-03-29T12:00:00.000Z", "2026-03-29T12:00:00.000Z");
  for (const [key, threadId, occurredAt] of [
    ["inside", "inside", "2026-03-28T23:30:00.000Z"],
    ["outside", "outside", "2026-03-29T22:30:00.000Z"],
    ["linked", "linked", "2026-03-29T12:00:00.000Z"],
  ]) {
    db.prepare(`
      INSERT INTO observed_activities(
        source_key, thread_id, turn_id, item_id, occurred_at, category, lifecycle, label
      ) VALUES (?, ?, NULL, NULL, ?, 'turn', 'completed', 'Turn completed')
    `).run(key, threadId, occurredAt);
  }
  return { db, reports: new ReportRepository(db) };
}

function create(reports: ReportRepository, trigger: "manual" | "scheduled" = "manual") {
  return reports.createSnapshot({
    localDate: "2026-03-29",
    dayStart: "2026-03-28T23:00:00.000Z",
    dayEnd: "2026-03-29T22:00:00.000Z",
    cutoff: "2026-03-29T21:59:00.000Z",
    trigger,
    narrativeRequested: false,
    now: "2026-03-29T21:59:00.000Z",
  });
}

describe("report repository", () => {
  it("freezes immutable facts with exact local-day inclusion and stable history", () => {
    const { db, reports } = setup();
    const first = create(reports);
    const frozen = JSON.stringify(first.factualDigest);
    expect(first.factualDigest.unplannedWork.map((item) => item.threadId)).toEqual(["inside"]);
    expect(first.factualDigest.blocked.map((task) => task.taskId)).toEqual(["blocked"]);

    db.prepare("UPDATE tasks SET title = 'Changed later', updated_at = ? WHERE id = 'pending'")
      .run("2026-03-30T00:00:00.000Z");
    const second = create(reports);
    expect(second.sequence).toBe(2);
    expect(JSON.stringify(reports.findSnapshot(first.id)?.factualDigest)).toBe(frozen);
    expect(reports.listSnapshots().map((item) => item.id)).toEqual([second.id, first.id]);
  });

  it("allows manual snapshots beside one durable automatic slot", () => {
    const { reports } = setup();
    create(reports);
    create(reports, "scheduled");
    expect(() => create(reports, "scheduled")).toThrow(/already filled/);
    expect(reports.listSnapshots()).toHaveLength(2);
  });

  it("uses sequence to select the latest same-millisecond snapshot", () => {
    const { reports } = setup();
    const first = create(reports);
    const second = create(reports);
    expect(first.createdAt).toBe(second.createdAt);
    expect(reports.latestSnapshot("2026-03-29")?.id).toBe(second.id);
    expect(reports.latestSnapshot()?.id).toBe(second.id);
  });

  it("supersedes prior suggestions when a newer factual snapshot includes the task", () => {
    const { reports } = setup();
    const first = create(reports);
    reports.saveNarrative(
      first.id,
      "Generated",
      [{ taskId: "pending", reason: "Looks done", sourceThreadIds: [] }],
      "2026-03-29T22:00:00.000Z",
    );
    const second = reports.createSnapshot({
      localDate: "2026-03-29",
      dayStart: "2026-03-28T23:00:00.000Z",
      dayEnd: "2026-03-29T22:00:00.000Z",
      cutoff: "2026-03-29T22:01:00.000Z",
      trigger: "manual",
      narrativeRequested: false,
      now: "2026-03-29T22:01:00.000Z",
    });
    expect(second.factualDigest.suggestedComplete.map((task) => task.taskId)).toEqual(["pending"]);
    expect(reports.findSnapshot(first.id)?.narrative.suggestions[0].supersededAt).toBe(
      "2026-03-29T22:01:00.000Z",
    );
  });
});
