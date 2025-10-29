-- Add CIN (Company Identification Number) fields to companies table
-- This migration adds support for storing and tracking CIN lookups from ZaubaCorp

-- Add CIN lookup status enum type
DO $$ BEGIN
    CREATE TYPE cin_lookup_status_enum AS ENUM ('pending', 'found', 'not_found', 'multiple_matches', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add CIN-related columns to companies table
ALTER TABLE companies 
    ADD COLUMN IF NOT EXISTS cin VARCHAR(50),
    ADD COLUMN IF NOT EXISTS cin_lookup_status cin_lookup_status_enum DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS cin_updated_at TIMESTAMP;

-- Add index on CIN for fast lookups
CREATE INDEX IF NOT EXISTS idx_companies_cin ON companies(cin);

-- Add index on cin_lookup_status for querying companies needing lookup
CREATE INDEX IF NOT EXISTS idx_companies_cin_lookup_status ON companies(cin_lookup_status) 
    WHERE cin_lookup_status = 'pending';

-- Add unique constraint on CIN (a CIN uniquely identifies a company)
-- We use a partial unique index to allow multiple NULL CINs
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_cin_unique ON companies(cin) 
    WHERE cin IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN companies.cin IS 'Company Identification Number from ZaubaCorp';
COMMENT ON COLUMN companies.cin_lookup_status IS 'Status of CIN lookup: pending, found, not_found, multiple_matches, error';
COMMENT ON COLUMN companies.cin_updated_at IS 'Timestamp when CIN was last updated';

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 002: CIN fields added to companies table';
END $$;

