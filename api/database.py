"""
PostgreSQL database connection and management module
Provides connection pooling, migration runner, and helper functions
"""
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor, execute_batch
from .config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """
    Get or create PostgreSQL connection pool
    
    Returns:
        ThreadedConnectionPool instance
    """
    global _connection_pool
    
    if _connection_pool is None:
        try:
            logger.info(f"Creating PostgreSQL connection pool to {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                connect_timeout=10,
                # Application name for pg_stat_activity
                application_name='infomerics_scraper'
            )
            logger.info("PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
    
    return _connection_pool


@contextmanager
def get_db_connection():
    """
    Context manager for getting a database connection from the pool
    
    Yields:
        psycopg2 connection
    """
    pool_instance = get_connection_pool()
    conn = None
    try:
        conn = pool_instance.getconn()
        yield conn
    finally:
        if conn:
            pool_instance.putconn(conn)


@contextmanager
def get_db_cursor(dict_cursor: bool = False):
    """
    Context manager for getting a database cursor
    
    Args:
        dict_cursor: If True, returns RealDictCursor for dict-like row access
        
    Yields:
        psycopg2 cursor
    """
    with get_db_connection() as conn:
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error, rolling back: {e}")
            raise
        finally:
            cursor.close()


def close_connection_pool():
    """Close all connections in the pool"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed")


def parse_date_for_db(date_str: str) -> Optional[datetime]:
    """
    Parse date string to datetime object for database insertion
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str or date_str == "Not found":
        return None
    
    # Common date formats to try
    date_formats = [
        '%Y-%m-%d',       # 2025-10-10 (ISO format)
        '%b %d, %Y',      # Oct 10, 2025
        '%B %d, %Y',      # October 10, 2025
        '%d-%b-%Y',       # 10-Oct-2025
        '%d/%m/%Y',       # 10/10/2025
        '%d %b %Y',       # 10 Oct 2025
        '%d %B %Y',       # 10 October 2025
    ]
    
    for date_format in date_formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), date_format)
            return parsed_date
        except ValueError:
            continue
    
    logger.warning(f"Could not parse date: {date_str}")
    return None


def init_database() -> bool:
    """
    Initialize database schema by running migrations
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Initializing PostgreSQL database...")
        
        # Check if we can connect
        with get_db_cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            logger.info(f"Connected to PostgreSQL: {version}")
        
        # Check if schema is already initialized
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'companies'
                );
            """)
            schema_exists = cursor.fetchone()[0]
        
        if schema_exists:
            logger.info("Database schema already initialized")
            return True
        
        # Run migration file
        migration_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migrations',
            '001_initial_schema.sql'
        )
        
        if os.path.exists(migration_file):
            logger.info(f"Running migration: {migration_file}")
            with open(migration_file, 'r') as f:
                migration_sql = f.read()
            
            with get_db_cursor() as cursor:
                cursor.execute(migration_sql)
            
            logger.info("Database schema initialized successfully")
            return True
        else:
            logger.warning(f"Migration file not found: {migration_file}")
            logger.warning("Schema will be created on first use if needed")
            return False
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def insert_rating_with_deduplication(
    company_name: str,
    instrument: str,
    rating: str,
    outlook: Optional[str],
    instrument_amount: Optional[str],
    date: str,
    source_url: Optional[str],
    job_id: str
) -> Tuple[bool, Optional[int]]:
    """
    Insert a credit rating with automatic deduplication
    
    Uses INSERT ... ON CONFLICT DO NOTHING to atomically handle duplicates
    
    Args:
        company_name: Name of the company
        instrument: Instrument category
        rating: Credit rating
        outlook: Rating outlook
        instrument_amount: Instrument amount
        date: Date string
        source_url: Source URL
        job_id: Job ID for tracking
        
    Returns:
        Tuple of (is_new_record, record_id or None)
    """
    try:
        # Parse date
        parsed_date = parse_date_for_db(date)
        if not parsed_date:
            logger.warning(f"Skipping rating with invalid date: {date}")
            return (False, None)
        
        # Get or create company
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT get_or_create_company(%s);",
                (company_name,)
            )
            company_id = cursor.fetchone()[0]
        
        # Insert rating with conflict handling
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO credit_ratings 
                (company_id, company_name, instrument, rating, outlook, 
                 instrument_amount, date, source_url, job_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_name, instrument, rating, date) 
                DO NOTHING
                RETURNING id;
            """, (
                company_id,
                company_name,
                instrument,
                rating,
                outlook if outlook and outlook != "Not found" else None,
                instrument_amount if instrument_amount and instrument_amount != "Not found" else None,
                parsed_date,
                source_url if source_url and source_url != "Not found" else None,
                job_id
            ))
            
            result = cursor.fetchone()
            if result:
                return (True, result[0])  # New record created
            else:
                return (False, None)  # Duplicate detected
                
    except Exception as e:
        logger.error(f"Error inserting rating: {e}")
        logger.error(f"  Company: {company_name}, Instrument: {instrument}, Rating: {rating}, Date: {date}")
        return (False, None)


def batch_insert_ratings(
    ratings_data: List[Dict[str, Any]],
    job_id: str
) -> Tuple[int, int]:
    """
    Batch insert credit ratings with deduplication using execute_batch for performance
    
    Args:
        ratings_data: List of rating dictionaries
        job_id: Job ID for tracking
        
    Returns:
        Tuple of (new_records_count, duplicate_records_count)
    """
    if not ratings_data:
        return (0, 0)
    
    new_records = 0
    duplicate_records = 0
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Prepare batch data
                batch_data = []
                for rating in ratings_data:
                    parsed_date = parse_date_for_db(rating.get('date', ''))
                    if not parsed_date:
                        duplicate_records += 1
                        continue
                    
                    company_name = rating.get('company_name', '')
                    if not company_name:
                        duplicate_records += 1
                        continue
                    
                    # Get or create company
                    cursor.execute(
                        "SELECT get_or_create_company(%s);",
                        (company_name,)
                    )
                    company_id = cursor.fetchone()[0]
                    
                    batch_data.append((
                        company_id,
                        company_name,
                        rating.get('instrument_category', ''),
                        rating.get('rating', ''),
                        rating.get('outlook') if rating.get('outlook') and rating.get('outlook') != "Not found" else None,
                        rating.get('instrument_amount') if rating.get('instrument_amount') and rating.get('instrument_amount') != "Not found" else None,
                        parsed_date,
                        rating.get('url') if rating.get('url') and rating.get('url') != "Not found" else None,
                        job_id
                    ))
                
                # Batch insert with deduplication
                if batch_data:
                    for data in batch_data:
                        cursor.execute("""
                            INSERT INTO credit_ratings 
                            (company_id, company_name, instrument, rating, outlook, 
                             instrument_amount, date, source_url, job_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (company_name, instrument, rating, date) 
                            DO NOTHING
                            RETURNING id;
                        """, data)
                        
                        result = cursor.fetchone()
                        if result:
                            new_records += 1
                        else:
                            duplicate_records += 1
                
                conn.commit()
                logger.info(f"Batch insert complete: {new_records} new, {duplicate_records} duplicates")
                return (new_records, duplicate_records)
                
    except Exception as e:
        logger.error(f"Error in batch_insert_ratings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def get_unsynced_ratings(job_id: str) -> List[Dict[str, Any]]:
    """
    Get all ratings for a job that haven't been synced to Airtable
    
    Args:
        job_id: Job ID
        
    Returns:
        List of rating dictionaries
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    company_name,
                    instrument,
                    rating,
                    outlook,
                    instrument_amount,
                    date,
                    source_url
                FROM credit_ratings
                WHERE job_id = %s 
                  AND airtable_record_id IS NULL
                  AND sync_failed = FALSE
                ORDER BY id
            """, (job_id,))
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting unsynced ratings: {e}")
        return []


def get_company_airtable_id(company_name: str) -> Optional[str]:
    """
    Get Airtable record ID for a company
    
    Args:
        company_name: Name of the company
        
    Returns:
        Airtable record ID or None
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT airtable_record_id FROM companies WHERE company_name = %s;",
                (company_name,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting company Airtable ID: {e}")
        return None


def update_company_airtable_id(company_name: str, airtable_record_id: str) -> bool:
    """
    Update Airtable record ID for a single company
    
    Args:
        company_name: Name of the company
        airtable_record_id: Airtable record ID
        
    Returns:
        True if successful
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO companies (company_name, airtable_record_id)
                VALUES (%s, %s)
                ON CONFLICT (company_name) 
                DO UPDATE SET 
                    airtable_record_id = EXCLUDED.airtable_record_id,
                    updated_at = CURRENT_TIMESTAMP;
            """, (company_name, airtable_record_id))
            return True
    except Exception as e:
        logger.error(f"Error updating company Airtable ID: {e}")
        return False


def get_companies_without_airtable_id(job_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get companies that need to be synced to Airtable
    
    Args:
        job_id: Optional job ID to filter companies from a specific job
        
    Returns:
        List of company dictionaries with 'company_name'
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            if job_id:
                cursor.execute("""
                    SELECT DISTINCT c.company_name
                    FROM companies c
                    INNER JOIN credit_ratings cr ON c.company_name = cr.company_name
                    WHERE c.airtable_record_id IS NULL
                      AND cr.job_id = %s
                    ORDER BY c.company_name
                """, (job_id,))
            else:
                cursor.execute("""
                    SELECT company_name
                    FROM companies
                    WHERE airtable_record_id IS NULL
                    ORDER BY company_name
                """)
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting companies without Airtable ID: {e}")
        return []


def batch_update_company_airtable_ids(
    company_mapping: Dict[str, str]
) -> int:
    """
    Batch update Airtable record IDs for multiple companies
    
    Args:
        company_mapping: Dictionary mapping company_name -> airtable_record_id
        
    Returns:
        Number of records updated
    """
    if not company_mapping:
        return 0
    
    try:
        with get_db_cursor() as cursor:
            # Use execute_batch for efficient batch updates
            data = [(airtable_id, company_name) for company_name, airtable_id in company_mapping.items()]
            execute_batch(cursor, """
                INSERT INTO companies (company_name, airtable_record_id)
                VALUES (%s, %s)
                ON CONFLICT (company_name)
                DO UPDATE SET
                    airtable_record_id = EXCLUDED.airtable_record_id,
                    updated_at = CURRENT_TIMESTAMP;
            """, [(company_name, airtable_id) for company_name, airtable_id in company_mapping.items()])
            
            logger.info(f"Batch updated {len(company_mapping)} companies with Airtable IDs")
            return len(company_mapping)
    except Exception as e:
        logger.error(f"Error batch updating company Airtable IDs: {e}")
        return 0


def update_ratings_airtable_ids(rating_airtable_mapping: List[Tuple[int, str]]) -> int:
    """
    Batch update Airtable record IDs for ratings
    
    Args:
        rating_airtable_mapping: List of (rating_id, airtable_record_id) tuples
        
    Returns:
        Number of records updated
    """
    try:
        with get_db_cursor() as cursor:
            execute_batch(cursor, """
                UPDATE credit_ratings
                SET 
                    airtable_record_id = %s,
                    uploaded_at = CURRENT_TIMESTAMP,
                    sync_failed = FALSE,
                    sync_error = NULL
                WHERE id = %s;
            """, [(airtable_id, rating_id) for rating_id, airtable_id in rating_airtable_mapping])
            
            return len(rating_airtable_mapping)
    except Exception as e:
        logger.error(f"Error updating rating Airtable IDs: {e}")
        return 0


def mark_ratings_sync_failed(rating_ids: List[int], error_message: str) -> int:
    """
    Mark ratings as failed to sync
    
    Args:
        rating_ids: List of rating IDs
        error_message: Error message
        
    Returns:
        Number of records updated
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE credit_ratings
                SET 
                    sync_failed = TRUE,
                    sync_error = %s
                WHERE id = ANY(%s);
            """, (error_message, rating_ids))
            
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Error marking ratings as failed: {e}")
        return 0


def get_duplicate_stats(job_id: str) -> Dict[str, int]:
    """
    Get duplicate detection statistics for a job
    
    Args:
        job_id: Job ID
        
    Returns:
        Dictionary with statistics
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_ratings,
                    COUNT(*) FILTER (WHERE airtable_record_id IS NOT NULL) as synced_count,
                    COUNT(*) FILTER (WHERE sync_failed = TRUE) as failed_count
                FROM credit_ratings
                WHERE job_id = %s;
            """, (job_id,))
            
            return dict(cursor.fetchone())
    except Exception as e:
        logger.error(f"Error getting duplicate stats: {e}")
        return {'total_ratings': 0, 'synced_count': 0, 'failed_count': 0}


def update_company_cin(
    company_id: int,
    cin: Optional[str],
    status: str
) -> bool:
    """
    Update CIN and lookup status for a company
    
    Args:
        company_id: Company ID
        cin: CIN value (can be None for not_found/error cases)
        status: Lookup status ('found', 'not_found', 'multiple_matches', 'error')
        
    Returns:
        True if successful
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE companies
                SET 
                    cin = %s,
                    cin_lookup_status = %s::cin_lookup_status_enum,
                    cin_updated_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (cin, status, company_id))
            
            logger.info(f"Updated CIN for company {company_id}: status={status}, cin={cin}")
            return True
    except Exception as e:
        logger.error(f"Error updating company CIN: {e}")
        return False


def get_companies_needing_cin_lookup(job_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get companies that need CIN lookup (status = 'pending')
    
    Args:
        job_id: Optional job ID to filter companies from a specific job
        limit: Maximum number of companies to return
        
    Returns:
        List of company dictionaries with id and company_name
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            if job_id:
                # Use subquery to get distinct companies with their earliest created_at
                cursor.execute("""
                    SELECT c.id, c.company_name
                    FROM companies c
                    WHERE c.cin_lookup_status = 'pending'
                      AND EXISTS (
                          SELECT 1 FROM credit_ratings cr 
                          WHERE cr.company_name = c.company_name 
                          AND cr.job_id = %s
                      )
                    ORDER BY c.id
                    LIMIT %s
                """, (job_id, limit))
            else:
                cursor.execute("""
                    SELECT id, company_name
                    FROM companies
                    WHERE cin_lookup_status = 'pending'
                    ORDER BY id
                    LIMIT %s
                """, (limit,))
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting companies needing CIN lookup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def get_company_by_id(company_id: int) -> Optional[Dict[str, Any]]:
    """
    Get company details by ID
    
    Args:
        company_id: Company ID
        
    Returns:
        Company dictionary or None
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    company_name,
                    cin,
                    cin_lookup_status,
                    airtable_record_id,
                    created_at,
                    updated_at
                FROM companies
                WHERE id = %s;
            """, (company_id,))
            
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting company by ID: {e}")
        return None


# ============================================================================
# CONTACTS DATABASE FUNCTIONS
# ============================================================================

def insert_contact_with_deduplication(
    din: Optional[str],
    full_name: str,
    mobile_number: Optional[str],
    email_address: Optional[str],
    addresses: Optional[List[Dict[str, Any]]],
    company_airtable_id: str
) -> Tuple[bool, Optional[int], bool]:
    """
    Insert a contact with automatic deduplication based on phone or email.
    If contact exists (by phone or email), update it.
    
    Args:
        din: Director Identification Number
        full_name: Full name of the contact
        mobile_number: Mobile number
        email_address: Email address
        addresses: List of address dictionaries
        company_airtable_id: Airtable record ID of the company
        
    Returns:
        Tuple of (success, contact_id, is_new_record)
    """
    try:
        import json
        
        # Convert addresses to JSONB
        addresses_json = json.dumps(addresses) if addresses else None
        
        # Find company_id from airtable_record_id
        company_id = None
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id FROM companies WHERE airtable_record_id = %s;
            """, (company_airtable_id,))
            result = cursor.fetchone()
            if result:
                company_id = result[0]
        
        with get_db_cursor() as cursor:
            # Try to insert, on conflict update
            # Conflict can occur on mobile_number or email_address
            cursor.execute("""
                WITH existing_contact AS (
                    SELECT id FROM contacts 
                    WHERE (mobile_number = %s AND mobile_number IS NOT NULL)
                       OR (email_address = %s AND email_address IS NOT NULL)
                    LIMIT 1
                ),
                inserted AS (
                    INSERT INTO contacts 
                    (din, full_name, mobile_number, email_address, addresses, 
                     company_id, company_airtable_id)
                    SELECT %s, %s, %s, %s, %s::jsonb, %s, %s
                    WHERE NOT EXISTS (SELECT 1 FROM existing_contact)
                    RETURNING id, true as is_new
                ),
                updated AS (
                    UPDATE contacts
                    SET 
                        din = COALESCE(%s, din),
                        full_name = %s,
                        mobile_number = COALESCE(%s, mobile_number),
                        email_address = COALESCE(%s, email_address),
                        addresses = COALESCE(%s::jsonb, addresses),
                        company_id = COALESCE(%s, company_id),
                        company_airtable_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT id FROM existing_contact)
                    RETURNING id, false as is_new
                )
                SELECT id, is_new FROM inserted
                UNION ALL
                SELECT id, is_new FROM updated;
            """, (
                mobile_number, email_address,  # Check for existing
                din, full_name, mobile_number, email_address, addresses_json, company_id, company_airtable_id,  # Insert
                din, full_name, mobile_number, email_address, addresses_json, company_id, company_airtable_id  # Update
            ))
            
            result = cursor.fetchone()
            if result:
                contact_id, is_new = result
                return (True, contact_id, is_new)
            else:
                logger.warning("Contact insertion/update returned no result")
                return (False, None, False)
                
    except Exception as e:
        logger.error(f"Error inserting/updating contact: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return (False, None, False)


def get_contact_by_phone_or_email(
    mobile_number: Optional[str],
    email_address: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Check if a contact exists by phone number or email address
    
    Args:
        mobile_number: Mobile number to check
        email_address: Email address to check
        
    Returns:
        Contact dictionary or None
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    din,
                    full_name,
                    mobile_number,
                    email_address,
                    company_airtable_id,
                    airtable_record_id,
                    created_at
                FROM contacts
                WHERE (mobile_number = %s AND mobile_number IS NOT NULL)
                   OR (email_address = %s AND email_address IS NOT NULL)
                LIMIT 1;
            """, (mobile_number, email_address))
            
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error checking contact existence: {e}")
        return None


def get_contacts_by_company(company_airtable_id: str) -> List[Dict[str, Any]]:
    """
    Get all contacts for a specific company
    
    Args:
        company_airtable_id: Airtable record ID of the company
        
    Returns:
        List of contact dictionaries
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    din,
                    full_name,
                    mobile_number,
                    email_address,
                    addresses,
                    company_airtable_id,
                    airtable_record_id,
                    created_at,
                    updated_at
                FROM contacts
                WHERE company_airtable_id = %s
                ORDER BY created_at DESC;
            """, (company_airtable_id,))
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting contacts by company: {e}")
        return []


def get_contacts_without_airtable_id(
    company_airtable_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get contacts that haven't been synced to Airtable yet
    
    Args:
        company_airtable_id: Optional filter by company
        limit: Maximum number of contacts to return
        
    Returns:
        List of contact dictionaries
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            if company_airtable_id:
                cursor.execute("""
                    SELECT 
                        id,
                        din,
                        full_name,
                        mobile_number,
                        email_address,
                        addresses,
                        company_airtable_id,
                        created_at
                    FROM contacts
                    WHERE airtable_record_id IS NULL
                      AND company_airtable_id = %s
                      AND sync_failed = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (company_airtable_id, limit))
            else:
                cursor.execute("""
                    SELECT 
                        id,
                        din,
                        full_name,
                        mobile_number,
                        email_address,
                        addresses,
                        company_airtable_id,
                        created_at
                    FROM contacts
                    WHERE airtable_record_id IS NULL
                      AND sync_failed = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (limit,))
            
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting contacts without Airtable ID: {e}")
        return []


def batch_update_contact_airtable_ids(
    contact_mapping: Dict[int, str]
) -> int:
    """
    Batch update Airtable record IDs for contacts
    
    Args:
        contact_mapping: Dictionary mapping contact_id -> airtable_record_id
        
    Returns:
        Number of contacts updated
    """
    if not contact_mapping:
        return 0
    
    try:
        updated_count = 0
        with get_db_cursor() as cursor:
            for contact_id, airtable_id in contact_mapping.items():
                cursor.execute("""
                    UPDATE contacts
                    SET 
                        airtable_record_id = %s,
                        synced_at = CURRENT_TIMESTAMP,
                        sync_failed = FALSE,
                        sync_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                """, (airtable_id, contact_id))
                updated_count += cursor.rowcount
        
        logger.info(f"Updated {updated_count} contacts with Airtable IDs")
        return updated_count
    except Exception as e:
        logger.error(f"Error batch updating contact Airtable IDs: {e}")
        return 0


def mark_contact_sync_failed(
    contact_id: int,
    error_message: str
) -> bool:
    """
    Mark a contact as failed to sync to Airtable
    
    Args:
        contact_id: Contact ID
        error_message: Error message
        
    Returns:
        True if successful
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE contacts
                SET 
                    sync_failed = TRUE,
                    sync_error = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (error_message, contact_id))
            return True
    except Exception as e:
        logger.error(f"Error marking contact sync as failed: {e}")
        return False

