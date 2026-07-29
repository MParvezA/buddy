-- Slice 01's queue could only target the deterministic placeholder. Clear that
-- superseded generation state once, then preserve only real App Server briefs.
DELETE FROM session_brief_jobs;
DELETE FROM session_briefs
WHERE generator = 'deterministic_placeholder';

CREATE TABLE session_brief_coordinator_state (
  singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
  epoch INTEGER NOT NULL CHECK (epoch >= 0)
);

INSERT INTO session_brief_coordinator_state(singleton_id, epoch)
VALUES (1, 0);
