-- Migration 004: Add Multi-tenancy Support
-- Adds organizations (tenants), users, roles, and permissions system

-- ============================================================================
-- ENUMS
-- ============================================================================

-- User roles enumeration
CREATE TYPE user_role_enum AS ENUM ('owner', 'admin', 'manager', 'agent');

-- ============================================================================
-- ORGANIZATIONS TABLE (Tenants)
-- ============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Contact information
    email VARCHAR(255),
    phone VARCHAR(50),
    website VARCHAR(255),
    
    -- Subscription/billing info (for future use)
    subscription_status VARCHAR(50) DEFAULT 'trial',
    subscription_plan VARCHAR(50) DEFAULT 'basic',
    trial_ends_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    
    -- API keys and integrations (per-tenant)
    airtable_api_key TEXT,
    airtable_base_id VARCHAR(100),
    attestr_api_key TEXT,
    bright_data_api_key TEXT,
    
    -- Settings
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT organizations_name_check CHECK (length(name) >= 2),
    CONSTRAINT organizations_slug_check CHECK (slug ~ '^[a-z0-9-]+$')
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_is_active ON organizations(is_active);
CREATE INDEX idx_organizations_subscription_status ON organizations(subscription_status);

COMMENT ON TABLE organizations IS 'Multi-tenant organizations (tenants)';
COMMENT ON COLUMN organizations.slug IS 'URL-safe unique identifier for organization';

-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Authentication
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    avatar_url TEXT,
    
    -- Role and permissions
    role user_role_enum NOT NULL DEFAULT 'agent',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_email_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMP,
    
    -- Security
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(50),
    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: email must be unique across all organizations
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT users_email_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

COMMENT ON TABLE users IS 'User accounts with role-based access control';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hashed password';

-- Trigger to update updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at 
    BEFORE UPDATE ON organizations 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- PERMISSIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT permissions_name_check CHECK (name ~ '^[a-z_]+\.[a-z_]+$')
);

CREATE INDEX idx_permissions_resource ON permissions(resource);
CREATE INDEX idx_permissions_name ON permissions(name);

COMMENT ON TABLE permissions IS 'Granular permissions for role-based access control';
COMMENT ON COLUMN permissions.name IS 'Permission identifier in format: resource.action (e.g., companies.write)';

-- ============================================================================
-- ROLE_PERMISSIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role user_role_enum NOT NULL,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT role_permissions_unique UNIQUE (role, permission_id)
);

CREATE INDEX idx_role_permissions_role ON role_permissions(role);
CREATE INDEX idx_role_permissions_permission_id ON role_permissions(permission_id);

COMMENT ON TABLE role_permissions IS 'Maps roles to permissions';

-- ============================================================================
-- AUDIT_LOGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Action details
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    
    -- Changes
    old_values JSONB,
    new_values JSONB,
    
    -- Metadata
    ip_address VARCHAR(50),
    user_agent TEXT,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_organization_id ON audit_logs(organization_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

COMMENT ON TABLE audit_logs IS 'Audit trail of all changes per organization';

-- ============================================================================
-- INSERT DEFAULT PERMISSIONS
-- ============================================================================

INSERT INTO permissions (name, resource, action, description) VALUES
    -- Companies
    ('companies.read', 'companies', 'read', 'View companies'),
    ('companies.write', 'companies', 'write', 'Create and update companies'),
    ('companies.delete', 'companies', 'delete', 'Delete companies'),
    
    -- Contacts
    ('contacts.read', 'contacts', 'read', 'View contacts'),
    ('contacts.write', 'contacts', 'write', 'Create and update contacts'),
    ('contacts.delete', 'contacts', 'delete', 'Delete contacts'),
    ('contacts.import', 'contacts', 'import', 'Import contacts from CSV'),
    
    -- Deals
    ('deals.read', 'deals', 'read', 'View deals'),
    ('deals.write', 'deals', 'write', 'Create and update deals'),
    ('deals.delete', 'deals', 'delete', 'Delete deals'),
    
    -- Activities
    ('activities.read', 'activities', 'read', 'View activities'),
    ('activities.write', 'activities', 'write', 'Create and update activities'),
    ('activities.delete', 'activities', 'delete', 'Delete activities'),
    
    -- Campaigns
    ('campaigns.read', 'campaigns', 'read', 'View campaigns'),
    ('campaigns.create', 'campaigns', 'create', 'Create campaigns'),
    ('campaigns.execute', 'campaigns', 'execute', 'Start and stop campaigns'),
    ('campaigns.delete', 'campaigns', 'delete', 'Delete campaigns'),
    
    -- WhatsApp
    ('whatsapp.read', 'whatsapp', 'read', 'View WhatsApp instances'),
    ('whatsapp.manage_instances', 'whatsapp', 'manage_instances', 'Add and remove WhatsApp instances'),
    ('whatsapp.send', 'whatsapp', 'send', 'Send WhatsApp messages'),
    
    -- Scraper
    ('scraper.create_jobs', 'scraper', 'create_jobs', 'Create scraper jobs'),
    ('scraper.view_results', 'scraper', 'view_results', 'View scraper results'),
    
    -- Users
    ('users.read', 'users', 'read', 'View users'),
    ('users.invite', 'users', 'invite', 'Invite new users'),
    ('users.manage', 'users', 'manage', 'Manage user roles and permissions'),
    ('users.delete', 'users', 'delete', 'Remove users'),
    
    -- Settings
    ('settings.read', 'settings', 'read', 'View organization settings'),
    ('settings.write', 'settings', 'write', 'Update organization settings'),
    ('settings.api_keys', 'settings', 'api_keys', 'Manage API keys and integrations'),
    ('settings.billing', 'settings', 'billing', 'Manage billing and subscription')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- ASSIGN PERMISSIONS TO ROLES
-- ============================================================================

-- Owner: All permissions
INSERT INTO role_permissions (role, permission_id)
SELECT 'owner', id FROM permissions
ON CONFLICT (role, permission_id) DO NOTHING;

-- Admin: All except billing
INSERT INTO role_permissions (role, permission_id)
SELECT 'admin', id FROM permissions WHERE name != 'settings.billing'
ON CONFLICT (role, permission_id) DO NOTHING;

-- Manager: Read all, write companies/contacts/deals/campaigns
INSERT INTO role_permissions (role, permission_id)
SELECT 'manager', id FROM permissions WHERE 
    name IN (
        'companies.read', 'companies.write',
        'contacts.read', 'contacts.write', 'contacts.import',
        'deals.read', 'deals.write',
        'activities.read', 'activities.write',
        'campaigns.read', 'campaigns.create', 'campaigns.execute',
        'whatsapp.read', 'whatsapp.send',
        'scraper.view_results',
        'users.read',
        'settings.read'
    )
ON CONFLICT (role, permission_id) DO NOTHING;

-- Agent: Read all, write activities/notes, send messages
INSERT INTO role_permissions (role, permission_id)
SELECT 'agent', id FROM permissions WHERE 
    name IN (
        'companies.read',
        'contacts.read',
        'deals.read',
        'activities.read', 'activities.write',
        'campaigns.read',
        'whatsapp.read', 'whatsapp.send',
        'scraper.view_results',
        'settings.read'
    )
ON CONFLICT (role, permission_id) DO NOTHING;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Check if user has permission
CREATE OR REPLACE FUNCTION user_has_permission(
    p_user_id INTEGER,
    p_permission_name VARCHAR
)
RETURNS BOOLEAN AS $$
DECLARE
    v_user_role user_role_enum;
    v_has_permission BOOLEAN;
BEGIN
    -- Get user role
    SELECT role INTO v_user_role
    FROM users
    WHERE id = p_user_id AND is_active = TRUE;
    
    IF v_user_role IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Check if role has permission
    SELECT EXISTS(
        SELECT 1
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.role = v_user_role
        AND p.name = p_permission_name
    ) INTO v_has_permission;
    
    RETURN v_has_permission;
END;
$$ LANGUAGE plpgsql;

-- Function: Get user's organization_id
CREATE OR REPLACE FUNCTION get_user_organization_id(p_user_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_organization_id INTEGER;
BEGIN
    SELECT organization_id INTO v_organization_id
    FROM users
    WHERE id = p_user_id AND is_active = TRUE;
    
    RETURN v_organization_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Create audit log entry
CREATE OR REPLACE FUNCTION create_audit_log(
    p_organization_id INTEGER,
    p_user_id INTEGER,
    p_action VARCHAR,
    p_resource_type VARCHAR,
    p_resource_id VARCHAR,
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    v_log_id BIGINT;
BEGIN
    INSERT INTO audit_logs (
        organization_id,
        user_id,
        action,
        resource_type,
        resource_id,
        old_values,
        new_values
    ) VALUES (
        p_organization_id,
        p_user_id,
        p_action,
        p_resource_type,
        p_resource_id,
        p_old_values,
        p_new_values
    )
    RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: User details with organization
CREATE OR REPLACE VIEW user_details AS
SELECT 
    u.id,
    u.email,
    u.first_name,
    u.last_name,
    u.phone,
    u.role,
    u.is_active,
    u.is_email_verified,
    u.last_login_at,
    u.created_at,
    o.id as organization_id,
    o.name as organization_name,
    o.slug as organization_slug,
    o.subscription_status,
    o.subscription_plan
FROM users u
JOIN organizations o ON o.id = u.organization_id;

COMMENT ON VIEW user_details IS 'User details with organization information';

-- ============================================================================
-- COMPLETION LOG
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 004 completed successfully';
    RAISE NOTICE 'Created tables: organizations, users, permissions, role_permissions, audit_logs';
    RAISE NOTICE 'Created enums: user_role_enum';
    RAISE NOTICE 'Inserted default permissions and role mappings';
END $$;

