-- Migration 005: Add CRM Tables and Multi-tenancy to Existing Tables
-- Adds organization_id to existing tables and creates CRM tables

-- ============================================================================
-- ADD ORGANIZATION_ID TO EXISTING TABLES
-- ============================================================================

-- Add organization_id to companies table
ALTER TABLE companies 
    ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;

-- Add organization_id to credit_ratings table
ALTER TABLE credit_ratings 
    ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;

-- Add organization_id to contacts table  
ALTER TABLE contacts 
    ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;

-- Add organization_id to scrape_jobs table
ALTER TABLE scrape_jobs 
    ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;

-- Create indexes on organization_id for performance
CREATE INDEX IF NOT EXISTS idx_companies_organization_id ON companies(organization_id);
CREATE INDEX IF NOT EXISTS idx_credit_ratings_organization_id ON credit_ratings(organization_id);
CREATE INDEX IF NOT EXISTS idx_contacts_organization_id ON contacts(organization_id);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_organization_id ON scrape_jobs(organization_id);

-- Update unique constraints to include organization_id
-- Drop old constraints and create new ones with organization_id

-- Companies: company_name unique per organization
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_company_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS companies_name_org_unique 
    ON companies(company_name, organization_id);

-- Credit ratings: unique per organization
ALTER TABLE credit_ratings DROP CONSTRAINT IF EXISTS unique_rating;
CREATE UNIQUE INDEX IF NOT EXISTS credit_ratings_unique_per_org 
    ON credit_ratings(company_name, instrument, rating, date, organization_id);

-- Contacts: phone/email unique per organization (not globally)
ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_mobile_number_key;
ALTER TABLE contacts DROP CONSTRAINT IF EXISTS contacts_email_address_key;
CREATE UNIQUE INDEX IF NOT EXISTS contacts_phone_org_unique 
    ON contacts(mobile_number, organization_id) 
    WHERE mobile_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS contacts_email_org_unique 
    ON contacts(email_address, organization_id) 
    WHERE email_address IS NOT NULL;

-- ============================================================================
-- ENUMS FOR CRM
-- ============================================================================

-- Deal stages
CREATE TYPE deal_stage_enum AS ENUM (
    'lead',
    'qualified',
    'proposal',
    'negotiation',
    'won',
    'lost'
);

-- Activity types
CREATE TYPE activity_type_enum AS ENUM (
    'note',
    'call',
    'meeting',
    'email',
    'task',
    'whatsapp'
);

-- Campaign status
CREATE TYPE campaign_status_enum AS ENUM (
    'draft',
    'scheduled',
    'running',
    'paused',
    'completed',
    'cancelled'
);

-- ============================================================================
-- TAGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    name VARCHAR(50) NOT NULL,
    color VARCHAR(7) DEFAULT '#3B82F6',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT tags_org_name_unique UNIQUE (organization_id, name),
    CONSTRAINT tags_color_check CHECK (color ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE INDEX idx_tags_organization_id ON tags(organization_id);
CREATE INDEX idx_tags_name ON tags(name);

COMMENT ON TABLE tags IS 'Tags for categorizing companies, contacts, and deals';

-- ============================================================================
-- DEALS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS deals (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Basic info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Stage and value
    stage deal_stage_enum NOT NULL DEFAULT 'lead',
    value DECIMAL(15, 2),
    currency VARCHAR(3) DEFAULT 'INR',
    probability INTEGER DEFAULT 0,
    
    -- Relationships
    company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Dates
    expected_close_date DATE,
    closed_date DATE,
    
    -- Metadata
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT deals_probability_check CHECK (probability >= 0 AND probability <= 100),
    CONSTRAINT deals_value_check CHECK (value >= 0)
);

CREATE INDEX idx_deals_organization_id ON deals(organization_id);
CREATE INDEX idx_deals_stage ON deals(stage);
CREATE INDEX idx_deals_company_id ON deals(company_id);
CREATE INDEX idx_deals_contact_id ON deals(contact_id);
CREATE INDEX idx_deals_owner_id ON deals(owner_id);
CREATE INDEX idx_deals_created_at ON deals(created_at DESC);
CREATE INDEX idx_deals_expected_close_date ON deals(expected_close_date);

COMMENT ON TABLE deals IS 'CRM deals/opportunities pipeline';

-- Trigger to update updated_at
CREATE TRIGGER update_deals_updated_at 
    BEFORE UPDATE ON deals 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DEAL_TAGS TABLE (Junction)
-- ============================================================================

CREATE TABLE IF NOT EXISTS deal_tags (
    deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (deal_id, tag_id)
);

CREATE INDEX idx_deal_tags_deal_id ON deal_tags(deal_id);
CREATE INDEX idx_deal_tags_tag_id ON deal_tags(tag_id);

-- ============================================================================
-- COMPANY_TAGS TABLE (Junction)
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_tags (
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (company_id, tag_id)
);

CREATE INDEX idx_company_tags_company_id ON company_tags(company_id);
CREATE INDEX idx_company_tags_tag_id ON company_tags(tag_id);

-- ============================================================================
-- CONTACT_TAGS TABLE (Junction)
-- ============================================================================

CREATE TABLE IF NOT EXISTS contact_tags (
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (contact_id, tag_id)
);

CREATE INDEX idx_contact_tags_contact_id ON contact_tags(contact_id);
CREATE INDEX idx_contact_tags_tag_id ON contact_tags(tag_id);

-- ============================================================================
-- ACTIVITIES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS activities (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Activity details
    type activity_type_enum NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Relationships - can be linked to multiple entities
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    deal_id INTEGER REFERENCES deals(id) ON DELETE CASCADE,
    
    -- Assignment
    assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Scheduling (for tasks and meetings)
    due_date TIMESTAMP,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activities_organization_id ON activities(organization_id);
CREATE INDEX idx_activities_type ON activities(type);
CREATE INDEX idx_activities_company_id ON activities(company_id);
CREATE INDEX idx_activities_contact_id ON activities(contact_id);
CREATE INDEX idx_activities_deal_id ON activities(deal_id);
CREATE INDEX idx_activities_assigned_to ON activities(assigned_to);
CREATE INDEX idx_activities_created_by ON activities(created_by);
CREATE INDEX idx_activities_due_date ON activities(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX idx_activities_completed ON activities(completed);
CREATE INDEX idx_activities_created_at ON activities(created_at DESC);

COMMENT ON TABLE activities IS 'All CRM activities: notes, calls, meetings, emails, tasks';

-- Trigger to update updated_at
CREATE TRIGGER update_activities_updated_at 
    BEFORE UPDATE ON activities 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- WHATSAPP_INSTANCES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS whatsapp_instances (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Instance details
    name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    
    -- Authentication status
    is_authenticated BOOLEAN DEFAULT FALSE,
    qr_code TEXT,
    qr_expires_at TIMESTAMP,
    
    -- Session info
    session_data JSONB,
    client_info JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_connected_at TIMESTAMP,
    last_disconnected_at TIMESTAMP,
    
    -- Rate limiting
    messages_sent_today INTEGER DEFAULT 0,
    daily_message_limit INTEGER DEFAULT 1000,
    last_message_sent_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT whatsapp_instances_org_phone_unique UNIQUE (organization_id, phone_number)
);

CREATE INDEX idx_whatsapp_instances_organization_id ON whatsapp_instances(organization_id);
CREATE INDEX idx_whatsapp_instances_phone_number ON whatsapp_instances(phone_number);
CREATE INDEX idx_whatsapp_instances_is_active ON whatsapp_instances(is_active);
CREATE INDEX idx_whatsapp_instances_is_authenticated ON whatsapp_instances(is_authenticated);

COMMENT ON TABLE whatsapp_instances IS 'WhatsApp phone number instances per organization';

-- Trigger to update updated_at
CREATE TRIGGER update_whatsapp_instances_updated_at 
    BEFORE UPDATE ON whatsapp_instances 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CAMPAIGNS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    whatsapp_instance_id INTEGER NOT NULL REFERENCES whatsapp_instances(id) ON DELETE CASCADE,
    
    -- Campaign details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    message_template TEXT NOT NULL,
    
    -- Status and scheduling
    status campaign_status_enum NOT NULL DEFAULT 'draft',
    scheduled_start_time TIMESTAMP,
    actual_start_time TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Rate limiting
    messages_per_hour INTEGER DEFAULT 60,
    delay_between_messages_seconds INTEGER DEFAULT 10,
    
    -- Stats
    total_contacts INTEGER DEFAULT 0,
    messages_sent INTEGER DEFAULT 0,
    messages_failed INTEGER DEFAULT 0,
    messages_pending INTEGER DEFAULT 0,
    
    -- Owner
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT campaigns_messages_per_hour_check CHECK (messages_per_hour > 0 AND messages_per_hour <= 500),
    CONSTRAINT campaigns_delay_check CHECK (delay_between_messages_seconds >= 1)
);

CREATE INDEX idx_campaigns_organization_id ON campaigns(organization_id);
CREATE INDEX idx_campaigns_whatsapp_instance_id ON campaigns(whatsapp_instance_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_created_by ON campaigns(created_by);
CREATE INDEX idx_campaigns_scheduled_start_time ON campaigns(scheduled_start_time);
CREATE INDEX idx_campaigns_created_at ON campaigns(created_at DESC);

COMMENT ON TABLE campaigns IS 'WhatsApp outreach campaigns';

-- Trigger to update updated_at
CREATE TRIGGER update_campaigns_updated_at 
    BEFORE UPDATE ON campaigns 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CAMPAIGN_CONTACTS TABLE (Junction with status tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS campaign_contacts (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    
    -- Message details
    personalized_message TEXT,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    failed_at TIMESTAMP,
    error_message TEXT,
    
    -- WhatsApp message ID
    whatsapp_message_id VARCHAR(100),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT campaign_contacts_unique UNIQUE (campaign_id, contact_id)
);

CREATE INDEX idx_campaign_contacts_campaign_id ON campaign_contacts(campaign_id);
CREATE INDEX idx_campaign_contacts_contact_id ON campaign_contacts(contact_id);
CREATE INDEX idx_campaign_contacts_status ON campaign_contacts(status);
CREATE INDEX idx_campaign_contacts_sent_at ON campaign_contacts(sent_at);

COMMENT ON TABLE campaign_contacts IS 'Tracks contacts in campaigns with delivery status';

-- ============================================================================
-- WHATSAPP_MESSAGES TABLE (Message history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    whatsapp_instance_id INTEGER NOT NULL REFERENCES whatsapp_instances(id) ON DELETE CASCADE,
    
    -- Message details
    phone_number VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    direction VARCHAR(10) NOT NULL DEFAULT 'outbound',
    
    -- Relationships
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'queued',
    whatsapp_message_id VARCHAR(100),
    
    -- Timestamps
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    failed_at TIMESTAMP,
    error_message TEXT,
    
    -- User who sent (if manual)
    sent_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT whatsapp_messages_direction_check CHECK (direction IN ('inbound', 'outbound'))
);

CREATE INDEX idx_whatsapp_messages_organization_id ON whatsapp_messages(organization_id);
CREATE INDEX idx_whatsapp_messages_whatsapp_instance_id ON whatsapp_messages(whatsapp_instance_id);
CREATE INDEX idx_whatsapp_messages_phone_number ON whatsapp_messages(phone_number);
CREATE INDEX idx_whatsapp_messages_contact_id ON whatsapp_messages(contact_id);
CREATE INDEX idx_whatsapp_messages_campaign_id ON whatsapp_messages(campaign_id);
CREATE INDEX idx_whatsapp_messages_status ON whatsapp_messages(status);
CREATE INDEX idx_whatsapp_messages_queued_at ON whatsapp_messages(queued_at DESC);
CREATE INDEX idx_whatsapp_messages_direction ON whatsapp_messages(direction);

COMMENT ON TABLE whatsapp_messages IS 'Complete history of WhatsApp messages';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Deal pipeline summary
CREATE OR REPLACE VIEW deal_pipeline_summary AS
SELECT 
    d.organization_id,
    d.stage,
    COUNT(*) as deal_count,
    SUM(d.value) as total_value,
    AVG(d.probability) as avg_probability
FROM deals d
GROUP BY d.organization_id, d.stage;

COMMENT ON VIEW deal_pipeline_summary IS 'Summary of deals by stage per organization';

-- View: Campaign performance
CREATE OR REPLACE VIEW campaign_performance AS
SELECT 
    c.id,
    c.organization_id,
    c.name,
    c.status,
    c.total_contacts,
    c.messages_sent,
    c.messages_failed,
    c.messages_pending,
    ROUND(100.0 * c.messages_sent / NULLIF(c.total_contacts, 0), 2) as delivery_rate,
    wi.name as whatsapp_instance_name,
    wi.phone_number,
    c.created_at,
    c.actual_start_time,
    c.completed_at
FROM campaigns c
JOIN whatsapp_instances wi ON wi.id = c.whatsapp_instance_id;

COMMENT ON VIEW campaign_performance IS 'Campaign performance metrics with delivery rates';

-- View: Contact engagement summary
CREATE OR REPLACE VIEW contact_engagement_summary AS
SELECT 
    c.id as contact_id,
    c.organization_id,
    c.full_name,
    c.mobile_number,
    c.email_address,
    COUNT(DISTINCT a.id) as activity_count,
    COUNT(DISTINCT wm.id) as whatsapp_message_count,
    COUNT(DISTINCT cc.campaign_id) as campaign_count,
    MAX(a.created_at) as last_activity_at,
    MAX(wm.sent_at) as last_message_sent_at
FROM contacts c
LEFT JOIN activities a ON a.contact_id = c.id
LEFT JOIN whatsapp_messages wm ON wm.contact_id = c.id
LEFT JOIN campaign_contacts cc ON cc.contact_id = c.id
GROUP BY c.id, c.organization_id, c.full_name, c.mobile_number, c.email_address;

COMMENT ON VIEW contact_engagement_summary IS 'Contact engagement metrics';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Get organization stats
CREATE OR REPLACE FUNCTION get_organization_stats(p_organization_id INTEGER)
RETURNS TABLE (
    companies_count BIGINT,
    contacts_count BIGINT,
    deals_count BIGINT,
    active_campaigns_count BIGINT,
    whatsapp_instances_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM companies WHERE organization_id = p_organization_id),
        (SELECT COUNT(*) FROM contacts WHERE organization_id = p_organization_id),
        (SELECT COUNT(*) FROM deals WHERE organization_id = p_organization_id),
        (SELECT COUNT(*) FROM campaigns WHERE organization_id = p_organization_id AND status IN ('scheduled', 'running')),
        (SELECT COUNT(*) FROM whatsapp_instances WHERE organization_id = p_organization_id AND is_active = TRUE);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_organization_stats IS 'Get key statistics for an organization dashboard';

-- ============================================================================
-- COMPLETION LOG
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 005 completed successfully';
    RAISE NOTICE 'Added organization_id to existing tables: companies, credit_ratings, contacts, scrape_jobs';
    RAISE NOTICE 'Created CRM tables: tags, deals, activities';
    RAISE NOTICE 'Created WhatsApp tables: whatsapp_instances, campaigns, campaign_contacts, whatsapp_messages';
    RAISE NOTICE 'Created junction tables: deal_tags, company_tags, contact_tags';
    RAISE NOTICE 'Created views: deal_pipeline_summary, campaign_performance, contact_engagement_summary';
END $$;

