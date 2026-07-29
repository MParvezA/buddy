CREATE TABLE report_snapshots (
  id TEXT PRIMARY KEY,
  local_date TEXT NOT NULL,
  sequence INTEGER NOT NULL CHECK (sequence > 0),
  trigger TEXT NOT NULL CHECK (trigger IN ('manual', 'scheduled', 'missed_recovery')),
  automatic_run_key TEXT UNIQUE,
  cutoff_at TEXT NOT NULL,
  factual_digest_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(local_date, sequence),
  CHECK (
    (trigger = 'manual' AND automatic_run_key IS NULL)
    OR
    (trigger IN ('scheduled', 'missed_recovery') AND automatic_run_key = local_date)
  )
);

CREATE INDEX report_snapshots_history_idx
  ON report_snapshots(created_at DESC, local_date DESC, sequence DESC);

CREATE TABLE report_narratives (
  snapshot_id TEXT PRIMARY KEY REFERENCES report_snapshots(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('not_requested', 'pending', 'ready', 'failed')),
  narrative_text TEXT,
  failure_code TEXT,
  updated_at TEXT NOT NULL,
  CHECK (length(COALESCE(narrative_text, '')) <= 8000),
  CHECK (length(COALESCE(failure_code, '')) <= 120)
);

CREATE TABLE report_completion_suggestions (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES report_snapshots(id) ON DELETE CASCADE,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 280),
  source_thread_ids_json TEXT NOT NULL CHECK (length(source_thread_ids_json) <= 4000),
  superseded_at TEXT
);

CREATE INDEX report_suggestions_task_idx
  ON report_completion_suggestions(task_id, superseded_at, snapshot_id);

CREATE TRIGGER supersede_report_suggestions_after_task_update
AFTER UPDATE OF title, clarification, lifecycle ON tasks
BEGIN
  UPDATE report_completion_suggestions
  SET superseded_at = NEW.updated_at
  WHERE task_id = NEW.id AND superseded_at IS NULL;
END;

CREATE TABLE report_schedule_preferences (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  local_time TEXT NOT NULL,
  timezone TEXT NOT NULL,
  narrative_enabled INTEGER NOT NULL CHECK (narrative_enabled IN (0, 1)),
  updated_at TEXT NOT NULL
);

INSERT INTO report_schedule_preferences(
  singleton, local_time, timezone, narrative_enabled, updated_at
) VALUES (1, '18:00', 'Europe/Berlin', 0, '1970-01-01T00:00:00.000Z');

CREATE TABLE reporting_thread_roles (
  thread_id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role = 'daily_reporter'),
  created_at TEXT NOT NULL
);
