-- PostgreSQL Schema for Infomerics Scraper Deduplication System
-- This schema provides a persistent source of truth for scraped data
-- and enables efficient duplicate detection using database constraints

-- Enable UUID extension for potential future use
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- COMPANIES TABLE
-- ============================================================================
-- Stores company records with mapping to Airtable IDs
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(500) NOT NULL UNIQUE,
    airtable_record_id VARCHAR(50) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_airtable_id ON companies(airtable_record_id);

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at 
    BEFORE UPDATE ON companies 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CREDIT_RATINGS TABLE
-- ============================================================================
-- Stores all credit ratings with automatic deduplication via unique constraint
CREATE TABLE IF NOT EXISTS credit_ratings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    company_name VARCHAR(500) NOT NULL,  -- Denormalized for performance
    instrument VARCHAR(200) NOT NULL,
    rating VARCHAR(100) NOT NULL,
    outlook VARCHAR(100),
    instrument_amount VARCHAR(200),
    date DATE NOT NULL,
    source_url TEXT,
    
    -- Metadata fields
    airtable_record_id VARCHAR(50) UNIQUE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP,
    job_id VARCHAR(50),
    sync_failed BOOLEAN DEFAULT FALSE,
    sync_error TEXT,
    
    -- Composite unique constraint for automatic duplicate prevention
    -- This is the core of our deduplication strategy
    CONSTRAINT unique_rating UNIQUE (company_name, instrument, rating, date)
);

-- Indexes for fast queries and lookups
CREATE INDEX IF NOT EXISTS idx_ratings_company_id ON credit_ratings(company_id);
CREATE INDEX IF NOT EXISTS idx_ratings_company_name ON credit_ratings(company_name);
CREATE INDEX IF NOT EXISTS idx_ratings_date ON credit_ratings(date);
CREATE INDEX IF NOT EXISTS idx_ratings_airtable_id ON credit_ratings(airtable_record_id);
CREATE INDEX IF NOT EXISTS idx_ratings_scraped_at ON credit_ratings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_ratings_job_id ON credit_ratings(job_id);
CREATE INDEX IF NOT EXISTS idx_ratings_sync_failed ON credit_ratings(sync_failed) WHERE sync_failed = TRUE;
CREATE INDEX IF NOT EXISTS idx_ratings_unsynced ON credit_ratings(job_id, airtable_record_id) WHERE airtable_record_id IS NULL;

-- Trigger to automatically link company_id when company_name is set
CREATE OR REPLACE FUNCTION link_company_id()
RETURNS TRIGGER AS $$
BEGIN
    -- If company_id is not set but company_name is, try to find and link company
    IF NEW.company_id IS NULL AND NEW.company_name IS NOT NULL THEN
        SELECT id INTO NEW.company_id 
        FROM companies 
        WHERE company_name = NEW.company_name;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER link_credit_rating_company 
    BEFORE INSERT ON credit_ratings 
    FOR EACH ROW 
    EXECUTE FUNCTION link_company_id();

-- ============================================================================
-- SCRAPE_JOBS TABLE
-- ============================================================================
-- Tracks all scraping jobs with detailed statistics
CREATE TABLE IF NOT EXISTS scrape_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    progress INTEGER DEFAULT 0,
    
    -- Statistics
    total_scraped INTEGER DEFAULT 0,
    new_records INTEGER DEFAULT 0,
    duplicate_records INTEGER DEFAULT 0,
    uploaded_to_airtable INTEGER DEFAULT 0,
    sync_failures INTEGER DEFAULT 0,
    
    -- Timestamps
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Error tracking
    error_message TEXT,
    error_count INTEGER DEFAULT 0
);

-- Indexes for job queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON scrape_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_started_at ON scrape_jobs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_date_range ON scrape_jobs(start_date, end_date);

-- ============================================================================
-- USEFUL VIEWS FOR MONITORING
-- ============================================================================

-- View: Recent jobs summary
CREATE OR REPLACE VIEW recent_jobs_summary AS
SELECT 
    job_id,
    start_date,
    end_date,
    status,
    progress,
    total_scraped,
    new_records,
    duplicate_records,
    uploaded_to_airtable,
    sync_failures,
    started_at,
    completed_at,
    EXTRACT(EPOCH FROM (COALESCE(completed_at, CURRENT_TIMESTAMP) - started_at)) as duration_seconds
FROM scrape_jobs
ORDER BY started_at DESC
LIMIT 100;

-- View: Companies without Airtable mapping
CREATE OR REPLACE VIEW companies_not_synced AS
SELECT 
    id,
    company_name,
    created_at,
    (SELECT COUNT(*) FROM credit_ratings WHERE company_id = companies.id) as rating_count
FROM companies
WHERE airtable_record_id IS NULL;

-- View: Ratings pending sync to Airtable
CREATE OR REPLACE VIEW ratings_pending_sync AS
SELECT 
    cr.id,
    cr.company_name,
    cr.instrument,
    cr.rating,
    cr.date,
    cr.job_id,
    cr.scraped_at,
    cr.sync_failed,
    cr.sync_error
FROM credit_ratings cr
WHERE cr.airtable_record_id IS NULL
ORDER BY cr.scraped_at DESC;

-- View: Daily scraping statistics
CREATE OR REPLACE VIEW daily_scraping_stats AS
SELECT 
    DATE(scraped_at) as scrape_date,
    COUNT(*) as total_ratings,
    COUNT(DISTINCT company_name) as unique_companies,
    COUNT(DISTINCT job_id) as jobs_count,
    COUNT(*) FILTER (WHERE airtable_record_id IS NOT NULL) as synced_count,
    COUNT(*) FILTER (WHERE sync_failed = TRUE) as failed_count
FROM credit_ratings
GROUP BY DATE(scraped_at)
ORDER BY scrape_date DESC;

-- View: Duplicate detection statistics
CREATE OR REPLACE VIEW duplicate_detection_stats AS
SELECT 
    job_id,
    total_scraped,
    new_records,
    duplicate_records,
    ROUND(100.0 * duplicate_records / NULLIF(total_scraped, 0), 2) as duplicate_percentage,
    started_at
FROM scrape_jobs
WHERE total_scraped > 0
ORDER BY started_at DESC;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Get company Airtable ID (or create placeholder)
CREATE OR REPLACE FUNCTION get_or_create_company(p_company_name VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_company_id INTEGER;
BEGIN
    -- Try to get existing company
    SELECT id INTO v_company_id
    FROM companies
    WHERE company_name = p_company_name;
    
    -- If not found, create it
    IF v_company_id IS NULL THEN
        INSERT INTO companies (company_name)
        VALUES (p_company_name)
        RETURNING id INTO v_company_id;
    END IF;
    
    RETURN v_company_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Mark ratings as synced with Airtable
CREATE OR REPLACE FUNCTION mark_ratings_synced(
    p_rating_ids INTEGER[],
    p_airtable_ids VARCHAR[]
)
RETURNS INTEGER AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    -- Update ratings with their Airtable IDs
    UPDATE credit_ratings
    SET 
        airtable_record_id = p_airtable_ids[array_position(p_rating_ids, id)],
        uploaded_at = CURRENT_TIMESTAMP,
        sync_failed = FALSE,
        sync_error = NULL
    WHERE id = ANY(p_rating_ids);
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA / COMMENTS
-- ============================================================================

COMMENT ON TABLE companies IS 'Stores company records with Airtable ID mappings';
COMMENT ON TABLE credit_ratings IS 'All scraped credit ratings with automatic deduplication via unique constraint';
COMMENT ON TABLE scrape_jobs IS 'Tracks all scraping jobs with statistics and status';

COMMENT ON CONSTRAINT unique_rating ON credit_ratings IS 
'Core deduplication constraint: prevents duplicate ratings for same company, instrument, rating, and date';

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Infomerics schema initialized successfully';
    RAISE NOTICE 'Tables created: companies, credit_ratings, scrape_jobs';
    RAISE NOTICE 'Views created: recent_jobs_summary, companies_not_synced, ratings_pending_sync, daily_scraping_stats, duplicate_detection_stats';
END $$;

