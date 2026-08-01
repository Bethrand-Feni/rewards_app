ALTER TABLE chores ADD COLUMN schedule_frequency TEXT
  CHECK (schedule_frequency IS NULL OR schedule_frequency IN (
    'NONE', 'DAILY', 'WEEKDAYS', 'WEEKENDS', 'WEEKLY', 'MONTHLY'
  ));
