ALTER TABLE days ADD COLUMN timezone TEXT;

UPDATE days
SET timezone = COALESCE(
  (SELECT timezone FROM report_schedule_preferences WHERE singleton = 1),
  'Europe/Berlin'
)
WHERE timezone IS NULL;

ALTER TABLE report_snapshots ADD COLUMN timezone TEXT;

UPDATE report_snapshots
SET timezone = COALESCE(
  (SELECT timezone FROM report_schedule_preferences WHERE singleton = 1),
  'Europe/Berlin'
)
WHERE timezone IS NULL;

