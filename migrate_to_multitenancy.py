#!/usr/bin/env python3
"""
Migration script to convert existing single-tenant data to multi-tenant structure

This script:
1. Creates a default organization
2. Creates a default admin user
3. Assigns organization_id to all existing records
4. Updates foreign key relationships
"""
import sys
import os
import logging
from datetime import datetime
from getpass import getpass

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from api.database import get_db_cursor
from api.auth.password_utils import hash_password
from slugify import slugify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_default_organization(org_name: str, slug: str) -> int:
    """
    Create default organization
    
    Returns:
        Organization ID
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Check if organization already exists
            cursor.execute("SELECT id FROM organizations WHERE slug = %s", (slug,))
            existing = cursor.fetchone()
            
            if existing:
                logger.info(f"Organization '{org_name}' already exists (ID: {existing['id']})")
                return existing['id']
            
            # Create organization
            cursor.execute("""
                INSERT INTO organizations (
                    name,
                    slug,
                    subscription_status,
                    subscription_plan,
                    is_active
                )
                VALUES (%s, %s, 'active', 'enterprise', TRUE)
                RETURNING id, name
            """, (org_name, slug))
            
            org = cursor.fetchone()
            logger.info(f"Created organization: {org['name']} (ID: {org['id']})")
            return org['id']
            
    except Exception as e:
        logger.error(f"Error creating organization: {str(e)}")
        raise


def create_default_admin(organization_id: int, email: str, password: str, first_name: str, last_name: str) -> int:
    """
    Create default admin user
    
    Returns:
        User ID
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = cursor.fetchone()
            
            if existing:
                logger.info(f"User '{email}' already exists (ID: {existing['id']})")
                return existing['id']
            
            # Hash password
            password_hash = hash_password(password)
            
            # Create user
            cursor.execute("""
                INSERT INTO users (
                    organization_id,
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    role,
                    is_active,
                    is_email_verified
                )
                VALUES (%s, %s, %s, %s, %s, 'owner', TRUE, TRUE)
                RETURNING id, email
            """, (organization_id, email, password_hash, first_name, last_name))
            
            user = cursor.fetchone()
            logger.info(f"Created admin user: {user['email']} (ID: {user['id']})")
            return user['id']
            
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        raise


def migrate_companies(organization_id: int) -> int:
    """Migrate companies table"""
    try:
        with get_db_cursor() as cursor:
            # Count companies without organization_id
            cursor.execute("SELECT COUNT(*) FROM companies WHERE organization_id IS NULL")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("No companies to migrate")
                return 0
            
            # Update companies
            cursor.execute("""
                UPDATE companies
                SET organization_id = %s
                WHERE organization_id IS NULL
            """, (organization_id,))
            
            logger.info(f"Migrated {count} companies to organization {organization_id}")
            return count
            
    except Exception as e:
        logger.error(f"Error migrating companies: {str(e)}")
        raise


def migrate_credit_ratings(organization_id: int) -> int:
    """Migrate credit_ratings table"""
    try:
        with get_db_cursor() as cursor:
            # Count ratings without organization_id
            cursor.execute("SELECT COUNT(*) FROM credit_ratings WHERE organization_id IS NULL")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("No credit ratings to migrate")
                return 0
            
            # Update ratings
            cursor.execute("""
                UPDATE credit_ratings
                SET organization_id = %s
                WHERE organization_id IS NULL
            """, (organization_id,))
            
            logger.info(f"Migrated {count} credit ratings to organization {organization_id}")
            return count
            
    except Exception as e:
        logger.error(f"Error migrating credit ratings: {str(e)}")
        raise


def migrate_contacts(organization_id: int) -> int:
    """Migrate contacts table"""
    try:
        with get_db_cursor() as cursor:
            # Count contacts without organization_id
            cursor.execute("SELECT COUNT(*) FROM contacts WHERE organization_id IS NULL")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("No contacts to migrate")
                return 0
            
            # Update contacts
            cursor.execute("""
                UPDATE contacts
                SET organization_id = %s
                WHERE organization_id IS NULL
            """, (organization_id,))
            
            logger.info(f"Migrated {count} contacts to organization {organization_id}")
            return count
            
    except Exception as e:
        logger.error(f"Error migrating contacts: {str(e)}")
        raise


def migrate_scrape_jobs(organization_id: int) -> int:
    """Migrate scrape_jobs table"""
    try:
        with get_db_cursor() as cursor:
            # Count jobs without organization_id
            cursor.execute("SELECT COUNT(*) FROM scrape_jobs WHERE organization_id IS NULL")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("No scrape jobs to migrate")
                return 0
            
            # Update jobs
            cursor.execute("""
                UPDATE scrape_jobs
                SET organization_id = %s
                WHERE organization_id IS NULL
            """, (organization_id,))
            
            logger.info(f"Migrated {count} scrape jobs to organization {organization_id}")
            return count
            
    except Exception as e:
        logger.error(f"Error migrating scrape jobs: {str(e)}")
        raise


def verify_migration(organization_id: int):
    """Verify migration was successful"""
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Check companies
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE organization_id = %s) as migrated,
                    COUNT(*) FILTER (WHERE organization_id IS NULL) as unmigrated
                FROM companies
            """, (organization_id,))
            companies = cursor.fetchone()
            
            # Check credit_ratings
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE organization_id = %s) as migrated,
                    COUNT(*) FILTER (WHERE organization_id IS NULL) as unmigrated
                FROM credit_ratings
            """, (organization_id,))
            ratings = cursor.fetchone()
            
            # Check contacts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE organization_id = %s) as migrated,
                    COUNT(*) FILTER (WHERE organization_id IS NULL) as unmigrated
                FROM contacts
            """, (organization_id,))
            contacts = cursor.fetchone()
            
            # Check scrape_jobs
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE organization_id = %s) as migrated,
                    COUNT(*) FILTER (WHERE organization_id IS NULL) as unmigrated
                FROM scrape_jobs
            """, (organization_id,))
            jobs = cursor.fetchone()
            
            logger.info("\n" + "="*60)
            logger.info("MIGRATION VERIFICATION")
            logger.info("="*60)
            logger.info(f"Companies: {companies['migrated']}/{companies['total']} migrated, {companies['unmigrated']} unmigrated")
            logger.info(f"Credit Ratings: {ratings['migrated']}/{ratings['total']} migrated, {ratings['unmigrated']} unmigrated")
            logger.info(f"Contacts: {contacts['migrated']}/{contacts['total']} migrated, {contacts['unmigrated']} unmigrated")
            logger.info(f"Scrape Jobs: {jobs['migrated']}/{jobs['total']} migrated, {jobs['unmigrated']} unmigrated")
            logger.info("="*60)
            
            # Check for unmigrated records
            total_unmigrated = (
                companies['unmigrated'] +
                ratings['unmigrated'] +
                contacts['unmigrated'] +
                jobs['unmigrated']
            )
            
            if total_unmigrated > 0:
                logger.warning(f"⚠️  {total_unmigrated} records were not migrated!")
                return False
            else:
                logger.info("✅ All records successfully migrated!")
                return True
            
    except Exception as e:
        logger.error(f"Error verifying migration: {str(e)}")
        return False


def main():
    """Main migration function"""
    logger.info("="*60)
    logger.info("MULTI-TENANCY MIGRATION SCRIPT")
    logger.info("="*60)
    logger.info("")
    
    # Get organization details
    print("\n--- Default Organization Setup ---")
    org_name = input("Organization name [Default Org]: ").strip() or "Default Org"
    slug = slugify(org_name)
    print(f"Organization slug: {slug}")
    
    # Get admin user details
    print("\n--- Admin User Setup ---")
    email = input("Admin email: ").strip()
    if not email:
        print("Error: Email is required")
        sys.exit(1)
    
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    password = getpass("Password (min 8 chars, uppercase, lowercase, digit): ")
    password_confirm = getpass("Confirm password: ")
    
    if password != password_confirm:
        print("Error: Passwords do not match")
        sys.exit(1)
    
    # Validate password
    from api.auth.password_utils import is_strong_password
    is_valid, error_msg = is_strong_password(password)
    if not is_valid:
        print(f"Error: {error_msg}")
        sys.exit(1)
    
    # Confirm migration
    print("\n--- Migration Summary ---")
    print(f"Organization: {org_name} ({slug})")
    print(f"Admin User: {first_name} {last_name} ({email})")
    print("")
    confirm = input("Proceed with migration? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Migration cancelled")
        sys.exit(0)
    
    try:
        # Step 1: Create organization
        logger.info("\nStep 1: Creating organization...")
        org_id = create_default_organization(org_name, slug)
        
        # Step 2: Create admin user
        logger.info("\nStep 2: Creating admin user...")
        user_id = create_default_admin(org_id, email, password, first_name, last_name)
        
        # Step 3: Migrate existing data
        logger.info("\nStep 3: Migrating existing data...")
        companies_count = migrate_companies(org_id)
        ratings_count = migrate_credit_ratings(org_id)
        contacts_count = migrate_contacts(org_id)
        jobs_count = migrate_scrape_jobs(org_id)
        
        # Step 4: Verify migration
        logger.info("\nStep 4: Verifying migration...")
        success = verify_migration(org_id)
        
        if success:
            logger.info("\n" + "="*60)
            logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info(f"Organization ID: {org_id}")
            logger.info(f"Admin User ID: {user_id}")
            logger.info(f"Login email: {email}")
            logger.info("")
            logger.info("You can now login to the system using the credentials above.")
            logger.info("="*60)
        else:
            logger.error("\n⚠️  MIGRATION COMPLETED WITH WARNINGS")
            logger.error("Please check the logs above for unmigrated records")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n❌ MIGRATION FAILED: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

