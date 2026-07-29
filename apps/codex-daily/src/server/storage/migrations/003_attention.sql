CREATE TABLE attention_items (
  id TEXT PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  thread_id TEXT NOT NULL REFERENCES observed_threads(id) ON DELETE CASCADE,
  turn_id TEXT,
  item_id TEXT,
  kind TEXT NOT NULL
    CHECK (kind IN (
      'approval',
      'direct_question',
      'failed_turn',
      'interrupted_turn',
      'explicit_blocker',
      'possibly_stale'
    )),
  certainty TEXT NOT NULL CHECK (certainty IN ('explicit', 'possible')),
  source_occurred_at TEXT NOT NULL,
  last_derived_at TEXT NOT NULL,
  source_label TEXT NOT NULL CHECK (length(source_label) BETWEEN 1 AND 120),
  lifecycle TEXT NOT NULL
    CHECK (lifecycle IN ('open', 'acknowledged', 'dismissed', 'source_resolved')),
  local_action_at TEXT
);

CREATE INDEX attention_items_open_queue_idx
  ON attention_items(
    lifecycle,
    certainty,
    source_occurred_at DESC,
    id
  );

CREATE INDEX attention_items_thread_idx
  ON attention_items(thread_id, source_occurred_at DESC);
