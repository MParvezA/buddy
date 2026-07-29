CREATE TABLE days (
  id TEXT PRIMARY KEY,
  local_date TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  day_id TEXT NOT NULL REFERENCES days(id) ON DELETE CASCADE,
  title TEXT NOT NULL CHECK (length(trim(title)) > 0),
  clarification TEXT,
  sort_position INTEGER NOT NULL CHECK (sort_position >= 0),
  lifecycle TEXT NOT NULL DEFAULT 'open'
    CHECK (lifecycle IN ('open', 'confirmed_complete', 'closed')),
  origin_task_id TEXT REFERENCES tasks(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  closed_at TEXT
);

CREATE INDEX tasks_day_order_idx ON tasks(day_id, sort_position, created_at, id);
CREATE INDEX tasks_origin_idx ON tasks(origin_task_id);

CREATE TABLE task_review_decisions (
  id TEXT PRIMARY KEY,
  source_task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
  action TEXT NOT NULL
    CHECK (action IN ('carry_forward', 'reschedule', 'close')),
  target_local_date TEXT,
  successor_task_id TEXT REFERENCES tasks(id),
  decided_at TEXT NOT NULL,
  CHECK (
    (action = 'close' AND target_local_date IS NULL AND successor_task_id IS NULL)
    OR
    (action IN ('carry_forward', 'reschedule')
      AND target_local_date IS NOT NULL
      AND successor_task_id IS NOT NULL)
  )
);
