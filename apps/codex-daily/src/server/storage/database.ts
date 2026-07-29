import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

export interface DatabaseOptions {
  path: string;
  migrationsDirectory?: string;
}

export interface PlanningDatabase {
  connection: DatabaseSync;
  path: string;
  close: () => void;
}

function migrationDirectory(override?: string): string {
  return override ?? path.resolve(process.cwd(), "src/server/storage/migrations");
}

export function runMigrations(connection: DatabaseSync, directory: string): void {
  connection.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    )
  `);

  const migrations = readdirSync(directory)
    .filter((name) => /^\d{3}_[a-z0-9_]+\.sql$/.test(name))
    .sort();
  const applied = connection.prepare("SELECT 1 FROM schema_migrations WHERE version = ?");
  const record = connection.prepare(
    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
  );

  for (const name of migrations) {
    if (applied.get(name)) continue;
    connection.exec("BEGIN IMMEDIATE");
    try {
      connection.exec(readFileSync(path.join(directory, name), "utf8"));
      record.run(name, new Date().toISOString());
      connection.exec("COMMIT");
    } catch (error) {
      connection.exec("ROLLBACK");
      throw error;
    }
  }
}

export function openDatabase(options: DatabaseOptions): PlanningDatabase {
  if (options.path !== ":memory:") {
    const parent = path.dirname(options.path);
    if (!existsSync(parent)) mkdirSync(parent, { recursive: true });
  }
  const connection = new DatabaseSync(options.path);
  connection.exec("PRAGMA foreign_keys = ON");
  connection.exec("PRAGMA busy_timeout = 3000");
  runMigrations(connection, migrationDirectory(options.migrationsDirectory));
  return {
    connection,
    path: options.path,
    close: () => connection.close(),
  };
}
