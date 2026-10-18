-- Run once on the previous two-column equipment table, which must be empty.
-- Existing equipment rows require real category/location values before migration.
BEGIN TRANSACTION;
ALTER TABLE equipment ADD COLUMN category VARCHAR(100) NOT NULL;
ALTER TABLE equipment ADD COLUMN location VARCHAR(200) NOT NULL;
ALTER TABLE equipment ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'available'
    CHECK (status IN ('available', 'maintenance', 'inactive'));
COMMIT;
