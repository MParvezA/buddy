CREATE TABLE observed_threads (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  title TEXT,
  cwd TEXT NOT NULL,
  source TEXT NOT NULL,
  cli_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  recency_at TEXT,
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  last_observed_at TEXT NOT NULL,
  runtime TEXT NOT NULL
    CHECK (runtime IN ('unknown', 'not_loaded', 'idle', 'active', 'system_error')),
  waiting_on_approval INTEGER NOT NULL DEFAULT 0 CHECK (waiting_on_approval IN (0, 1)),
  waiting_on_user_input INTEGER NOT NULL DEFAULT 0 CHECK (waiting_on_user_input IN (0, 1)),
  last_activity_at TEXT
);

CREATE INDEX observed_threads_recency_idx
  ON observed_threads(archived, recency_at DESC, updated_at DESC);

CREATE TABLE observed_activities (
  source_key TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL REFERENCES observed_threads(id) ON DELETE CASCADE,
  turn_id TEXT,
  item_id TEXT,
  occurred_at TEXT NOT NULL,
  category TEXT NOT NULL
    CHECK (category IN ('thread', 'goal', 'turn', 'item', 'approval', 'input_request', 'error')),
  lifecycle TEXT NOT NULL,
  label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 120)
);

CREATE INDEX observed_activities_timeline_idx
  ON observed_activities(occurred_at DESC, source_key);

CREATE TABLE task_thread_links (
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  thread_id TEXT NOT NULL REFERENCES observed_threads(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY (task_id, thread_id)
);

CREATE TABLE observer_thread_exclusions (
  thread_id TEXT PRIMARY KEY,
  reason TEXT NOT NULL CHECK (reason IN ('reporting')),
  created_at TEXT NOT NULL
);
