-- Add contacts table for storing director and signatory contact information
-- This migration adds support for storing contacts fetched from Attestr API

-- ============================================================================
-- CONTACTS TABLE
-- ============================================================================
-- Stores contact information for directors and signatories linked to companies
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    
    -- Contact identification
    din VARCHAR(50),  -- Director Identification Number from MCA
    full_name VARCHAR(500) NOT NULL,
    
    -- Contact details
    mobile_number VARCHAR(20),
    email_address VARCHAR(255),
    
    -- Address information stored as JSONB for flexibility
    -- Each address has: line1, line2, line3, line4, locality, district, city, state, country, zip, fullAddress
    addresses JSONB,
    
    -- Company linkage
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    company_airtable_id VARCHAR(50),  -- Airtable record ID of the company
    
    -- Airtable synchronization
    airtable_record_id VARCHAR(50) UNIQUE,
    synced_at TIMESTAMP,
    sync_failed BOOLEAN DEFAULT FALSE,
    sync_error TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite unique constraint for deduplication
    -- A contact is considered duplicate if mobile_number OR email_address matches
    -- NULL values are excluded from uniqueness check
    CONSTRAINT unique_contact_phone UNIQUE NULLS NOT DISTINCT (mobile_number),
    CONSTRAINT unique_contact_email UNIQUE NULLS NOT DISTINCT (email_address)
);

-- Indexes for fast lookups and queries
CREATE INDEX IF NOT EXISTS idx_contacts_din ON contacts(din);
CREATE INDEX IF NOT EXISTS idx_contacts_full_name ON contacts(full_name);
CREATE INDEX IF NOT EXISTS idx_contacts_mobile ON contacts(mobile_number) WHERE mobile_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email_address) WHERE email_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_company_airtable_id ON contacts(company_airtable_id);
CREATE INDEX IF NOT EXISTS idx_contacts_airtable_id ON contacts(airtable_record_id);
CREATE INDEX IF NOT EXISTS idx_contacts_sync_failed ON contacts(sync_failed) WHERE sync_failed = TRUE;
CREATE INDEX IF NOT EXISTS idx_contacts_unsynced ON contacts(company_airtable_id) WHERE airtable_record_id IS NULL;

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_contacts_updated_at 
    BEFORE UPDATE ON contacts 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: Contacts pending sync to Airtable
CREATE OR REPLACE VIEW contacts_pending_sync AS
SELECT 
    c.id,
    c.din,
    c.full_name,
    c.mobile_number,
    c.email_address,
    c.company_airtable_id,
    c.created_at,
    c.sync_failed,
    c.sync_error,
    co.company_name
FROM contacts c
LEFT JOIN companies co ON c.company_id = co.id
WHERE c.airtable_record_id IS NULL
ORDER BY c.created_at DESC;

-- View: Contact statistics by company
CREATE OR REPLACE VIEW contact_stats_by_company AS
SELECT 
    co.company_name,
    co.airtable_record_id as company_airtable_id,
    COUNT(c.id) as total_contacts,
    COUNT(c.airtable_record_id) as synced_contacts,
    COUNT(*) FILTER (WHERE c.sync_failed = TRUE) as failed_contacts,
    COUNT(*) FILTER (WHERE c.mobile_number IS NOT NULL) as contacts_with_phone,
    COUNT(*) FILTER (WHERE c.email_address IS NOT NULL) as contacts_with_email
FROM companies co
LEFT JOIN contacts c ON c.company_id = co.id
GROUP BY co.id, co.company_name, co.airtable_record_id
HAVING COUNT(c.id) > 0
ORDER BY total_contacts DESC;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE contacts IS 'Stores contact information for company directors and signatories fetched from Attestr API';
COMMENT ON COLUMN contacts.din IS 'Director Identification Number from MCA';
COMMENT ON COLUMN contacts.addresses IS 'JSONB array of address objects with structure: {line1, line2, line3, line4, locality, district, city, state, country, zip, fullAddress}';
COMMENT ON COLUMN contacts.company_airtable_id IS 'Airtable record ID of the linked company for direct linkage';
COMMENT ON CONSTRAINT unique_contact_phone ON contacts IS 'Ensures mobile numbers are unique across all contacts';
COMMENT ON CONSTRAINT unique_contact_email ON contacts IS 'Ensures email addresses are unique across all contacts';

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 003: Contacts table created successfully';
    RAISE NOTICE 'Added: contacts table, indexes, views (contacts_pending_sync, contact_stats_by_company)';
END $$;

