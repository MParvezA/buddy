// @vitest-environment node
import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { openDatabase, runMigrations } from "./database.js";

const directories: string[] = [];

afterEach(() => {
  for (const directory of directories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("planning database", () => {
  it("applies numbered migrations once and enforces foreign keys", () => {
    const database = openDatabase({ path: ":memory:" });
    runMigrations(database.connection, path.resolve("src/server/storage/migrations"));

    const applied = database.connection
      .prepare("SELECT version FROM schema_migrations")
      .all() as { version: string }[];
    expect(applied).toEqual([
      { version: "001_morning_planning.sql" },
      { version: "002_codex_observer.sql" },
      { version: "003_attention.sql" },
      { version: "004_evening_report.sql" },
      { version: "005_operational_hardening.sql" },
      { version: "006_session_briefs.sql" },
      { version: "007_gpt_session_briefs.sql" },
    ]);
    expect(() =>
      database.connection
        .prepare(`
          INSERT INTO tasks(
            id, day_id, title, sort_position, lifecycle, created_at, updated_at
          ) VALUES ('orphan', 'missing', 'No owner', 0, 'open', 'now', 'now')
        `)
        .run(),
    ).toThrow();
    database.close();
  });

  it("uses a configurable file and persists only planning metadata", () => {
    const directory = mkdtempSync(path.join(tmpdir(), "codex-daily-db-"));
    directories.push(directory);
    const databasePath = path.join(directory, "planning.sqlite");
    const first = openDatabase({ path: databasePath });
    first.connection
      .prepare("INSERT INTO days(id, local_date, created_at, updated_at) VALUES (?, ?, ?, ?)")
      .run("day", "2026-07-29", "now", "now");
    first.close();

    const reopened = openDatabase({ path: databasePath });
    expect(
      reopened.connection.prepare("SELECT local_date FROM days").get(),
    ).toEqual({ local_date: "2026-07-29" });
    const columns = reopened.connection
      .prepare(`
        SELECT name FROM pragma_table_info('tasks')
        UNION ALL SELECT name FROM pragma_table_info('task_review_decisions')
        UNION ALL SELECT name FROM pragma_table_info('session_briefs')
        UNION ALL SELECT name FROM pragma_table_info('session_brief_jobs')
      `)
      .all()
      .map((row) => (row as { name: string }).name);
    expect(columns).not.toEqual(
      expect.arrayContaining(["transcript", "prompt", "response", "raw_item"]),
    );
    reopened.close();

    const migration = readFileSync(
      path.resolve("src/server/storage/migrations/001_morning_planning.sql"),
      "utf8",
    );
    expect(migration).not.toMatch(/\b(transcript|prompt|response|credential)\b/i);
  });

  it("upgrades Slice 01 storage and removes placeholder rows and jobs once", () => {
    const directory = mkdtempSync(path.join(tmpdir(), "codex-daily-upgrade-"));
    directories.push(directory);
    const migrations = path.join(directory, "migrations");
    mkdirSync(migrations);
    for (const name of [
      "001_morning_planning.sql",
      "002_codex_observer.sql",
      "003_attention.sql",
      "004_evening_report.sql",
      "005_operational_hardening.sql",
      "006_session_briefs.sql",
    ]) {
      copyFileSync(
        path.resolve("src/server/storage/migrations", name),
        path.join(migrations, name),
      );
    }
    const databasePath = path.join(directory, "upgrade.sqlite");
    const previous = openDatabase({
      path: databasePath,
      migrationsDirectory: migrations,
    });
    previous.connection.exec(`
      INSERT INTO observed_threads(
        id, session_id, title, cwd, source, cli_version, created_at, updated_at,
        recency_at, archived, last_observed_at, runtime, waiting_on_approval,
        waiting_on_user_input, last_activity_at
      ) VALUES (
        'thread-one', 'session-one', 'Chat', '/workspace', 'cli', '1',
        '2026-07-29T10:00:00.000Z', '2026-07-29T10:00:00.000Z',
        '2026-07-29T10:00:00.000Z', 0, '2026-07-29T10:00:00.000Z',
        'idle', 0, 0, NULL
      );
      INSERT INTO session_briefs(
        thread_id, source_updated_at, generated_at, generator, model_id,
        current_state, done_json, operator_actions_json, blockers_json,
        confidence, evidence_json, updated_at, out_of_window_at
      ) VALUES (
        'thread-one', '2026-07-29T10:00:00.000Z',
        '2026-07-29T10:01:00.000Z', 'deterministic_placeholder', NULL,
        'Session metadata is ready for future GPT-5.6 analysis.',
        '[]', '[]', '[]', 'low', '[]',
        '2026-07-29T10:01:00.000Z', NULL
      );
      INSERT INTO session_brief_jobs(
        thread_id, job_id, target_updated_at, reason, status, attempt_count,
        queued_at, started_at, failure_category, failure_at, updated_at
      ) VALUES (
        'thread-one', 'placeholder-job', '2026-07-29T10:00:00.000Z',
        'automatic', 'queued', 0, '2026-07-29T10:02:00.000Z',
        NULL, NULL, NULL, '2026-07-29T10:02:00.000Z'
      );
    `);
    previous.close();

    const upgraded = openDatabase({ path: databasePath });
    expect(
      upgraded.connection
        .prepare("SELECT MAX(version) AS version FROM schema_migrations")
        .get(),
    ).toEqual({ version: "007_gpt_session_briefs.sql" });
    expect(
      upgraded.connection
        .prepare(`
          SELECT name FROM sqlite_master
          WHERE type = 'table' AND name IN ('session_briefs', 'session_brief_jobs')
          ORDER BY name
        `)
        .all(),
    ).toEqual([
      { name: "session_brief_jobs" },
      { name: "session_briefs" },
    ]);
    expect(upgraded.connection.prepare("PRAGMA foreign_key_check").all()).toEqual([]);
    expect(
      upgraded.connection
        .prepare("SELECT COUNT(*) AS count FROM session_briefs")
        .get(),
    ).toEqual({ count: 0 });
    expect(
      upgraded.connection
        .prepare("SELECT COUNT(*) AS count FROM session_brief_jobs")
        .get(),
    ).toEqual({ count: 0 });
    upgraded.close();
  });

  it("rolls a failed write transaction back", () => {
    const database = openDatabase({ path: ":memory:" });
    database.connection.exec("BEGIN IMMEDIATE");
    try {
      database.connection
        .prepare("INSERT INTO days(id, local_date, created_at, updated_at) VALUES (?, ?, ?, ?)")
        .run("rolled-back", "2026-07-29", "now", "now");
      throw new Error("forced failure");
    } catch {
      database.connection.exec("ROLLBACK");
    }
    expect(database.connection.prepare("SELECT count(*) AS count FROM days").get()).toEqual({
      count: 0,
    });
    database.close();
  });
});
