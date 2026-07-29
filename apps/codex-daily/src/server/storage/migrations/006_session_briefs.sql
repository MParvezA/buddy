CREATE TABLE session_briefs (
  thread_id TEXT PRIMARY KEY REFERENCES observed_threads(id) ON DELETE CASCADE,
  source_updated_at TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  generator TEXT NOT NULL CHECK (length(generator) BETWEEN 1 AND 100),
  model_id TEXT CHECK (model_id IS NULL OR length(model_id) BETWEEN 1 AND 100),
  current_state TEXT NOT NULL CHECK (length(current_state) BETWEEN 1 AND 600),
  done_json TEXT NOT NULL,
  operator_actions_json TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
  evidence_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  out_of_window_at TEXT
);

CREATE INDEX session_briefs_retention_idx
  ON session_briefs(out_of_window_at);

CREATE TABLE session_brief_jobs (
  thread_id TEXT PRIMARY KEY REFERENCES observed_threads(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL UNIQUE,
  target_updated_at TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('automatic', 'manual', 'retry')),
  status TEXT NOT NULL
    CHECK (status IN ('queued', 'analyzing', 'unavailable', 'failed')),
  attempt_count INTEGER NOT NULL DEFAULT 0
    CHECK (attempt_count >= 0 AND attempt_count <= 100),
  queued_at TEXT NOT NULL,
  started_at TEXT,
  failure_category TEXT CHECK (
    failure_category IS NULL OR failure_category IN (
      'observer_unavailable',
      'source_missing',
      'empty_usable_content',
      'analysis_unavailable',
      'timeout',
      'refusal',
      'invalid_output',
      'internal'
    )
  ),
  failure_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX session_brief_jobs_queue_idx
  ON session_brief_jobs(status, queued_at, thread_id);
