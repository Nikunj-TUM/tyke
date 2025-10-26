"""
Airtable API integration for Companies and Credit Ratings tables
"""
import logging
import time
import redis
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from pyairtable import Api
from .config import settings

logger = logging.getLogger(__name__)


# Outlook mapping to match Airtable predefined choices
OUTLOOK_MAPPING = {
    "Nil": "Nil",
    "nil": "Nil",
    "Positive": "Positive",
    "positive": "Positive",
    "Stable": "Stable",
    "stable": "Stable",
    "Negative": "Negative",
    "negative": "Negative",
    "Stable/-": "Stable/-",
    "Positive/-": "Positive/-",
    "Negative/-": "Negative/-",
    "Not Available": "Not Available",
    "not available": "Not Available",
    "Rating Watch with Developing Implications": "Rating Watch with Developing Implications",
    "Rating Watch with Negative Implications": "Rating Watch with Negative Implications",
}


class AirtableClient:
    """Client for interacting with Airtable API"""
    
    def __init__(self, use_redis_cache: bool = True):
        """
        Initialize Airtable client with optional Redis caching
        
        Args:
            use_redis_cache: Whether to use Redis for distributed caching (default: True)
        """
        self.api = Api(settings.AIRTABLE_API_KEY)
        self.base = self.api.base(settings.AIRTABLE_BASE_ID)
        
        # Get table references
        self.companies_table = self.base.table(settings.COMPANIES_TABLE_ID)
        self.credit_ratings_table = self.base.table(settings.CREDIT_RATINGS_TABLE_ID)
        
        # Local cache for company records (per-instance, fast)
        self._company_cache: Dict[str, str] = {}  # company_name -> record_id
        
        # Redis cache for distributed caching across workers
        self.use_redis_cache = use_redis_cache
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 3600  # 1 hour TTL for cached company IDs
        
        if use_redis_cache:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}. Falling back to local cache only.")
                self.redis_client = None
                self.use_redis_cache = False
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date string to YYYY-MM-DD format for Airtable
        
        Args:
            date_str: Date string in various formats (e.g., "Oct 10, 2025")
            
        Returns:
            Date in YYYY-MM-DD format or None if parsing fails
        """
        if not date_str or date_str == "Not found":
            return None
        
        # Common date formats to try
        date_formats = [
            '%b %d, %Y',      # Oct 10, 2025
            '%B %d, %Y',      # October 10, 2025
            '%d-%b-%Y',       # 10-Oct-2025
            '%d/%m/%Y',       # 10/10/2025
            '%Y-%m-%d',       # 2025-10-10 (already correct)
            '%d %b %Y',       # 10 Oct 2025
            '%d %B %Y',       # 10 October 2025
        ]
        
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), date_format)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _map_outlook(self, outlook: str) -> Optional[str]:
        """
        Map outlook value to Airtable predefined choice
        
        Args:
            outlook: Outlook string from extracted data
            
        Returns:
            Mapped outlook value or None
        """
        if not outlook or outlook == "Not found":
            return None
        
        # Try exact match first
        mapped = OUTLOOK_MAPPING.get(outlook)
        if mapped:
            return mapped
        
        # Try case-insensitive match
        for key, value in OUTLOOK_MAPPING.items():
            if key.lower() == outlook.lower():
                return value
        
        logger.warning(f"Unknown outlook value: {outlook}, defaulting to 'Not Available'")
        return "Not Available"
    
    def _get_cached_company_id(self, company_name: str) -> Optional[str]:
        """
        Get company ID from cache (local memory + Redis)
        
        This implements a two-tier caching strategy:
        1. Check local in-memory cache first (fastest, per-worker)
        2. Check Redis cache if not in local cache (shared across all workers)
        
        Args:
            company_name: Name of the company
            
        Returns:
            Airtable record ID if found in cache, None otherwise
        """
        # Tier 1: Check local in-memory cache (fastest)
        if company_name in self._company_cache:
            logger.debug(f"Company '{company_name}' found in local cache")
            return self._company_cache[company_name]
        
        # Tier 2: Check Redis cache (shared across workers)
        if self.use_redis_cache and self.redis_client:
            try:
                cache_key = f"company:{company_name}"
                cached_id = self.redis_client.get(cache_key)
                
                if cached_id:
                    logger.debug(f"Company '{company_name}' found in Redis cache")
                    # Populate local cache for subsequent lookups
                    self._company_cache[company_name] = cached_id
                    return cached_id
            except Exception as e:
                logger.warning(f"Redis cache read error for '{company_name}': {e}")
        
        return None
    
    def _set_cached_company_id(self, company_name: str, record_id: str) -> None:
        """
        Set company ID in cache (local memory + Redis)
        
        Updates both cache tiers to ensure consistency:
        1. Update local in-memory cache
        2. Update Redis cache with TTL
        
        Args:
            company_name: Name of the company
            record_id: Airtable record ID
        """
        # Update local cache
        self._company_cache[company_name] = record_id
        
        # Update Redis cache with TTL
        if self.use_redis_cache and self.redis_client:
            try:
                cache_key = f"company:{company_name}"
                self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,  # Expire after 1 hour
                    record_id
                )
                logger.debug(f"Company '{company_name}' cached in Redis (TTL: {self.cache_ttl}s)")
            except Exception as e:
                logger.warning(f"Redis cache write error for '{company_name}': {e}")
    
    def upsert_company(self, company_name: str) -> str:
        """
        Create or get existing company record with two-tier caching
        
        Uses local + Redis cache to minimize API calls across distributed workers.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Airtable record ID of the company
        """
        # Check cache first (local + Redis)
        cached_id = self._get_cached_company_id(company_name)
        if cached_id:
            return cached_id
        
        try:
            # Search for existing company in Airtable
            formula = f"{{Company Name}} = '{company_name}'"
            existing_records = self.companies_table.all(formula=formula)
            
            if existing_records:
                record_id = existing_records[0]['id']
                self._set_cached_company_id(company_name, record_id)
                logger.info(f"Found existing company: {company_name} (ID: {record_id})")
                return record_id
            
            # Create new company
            new_record = self.companies_table.create({
                "Company Name": company_name
            })
            record_id = new_record['id']
            self._set_cached_company_id(company_name, record_id)
            logger.info(f"Created new company: {company_name} (ID: {record_id})")
            return record_id
            
        except Exception as e:
            logger.error(f"Error upserting company '{company_name}': {str(e)}")
            raise
    
    def create_credit_rating(
        self,
        company_record_id: str,
        instrument: str,
        rating: str,
        outlook: Optional[str],
        instrument_amount: Optional[str],
        date: Optional[str],
        source_url: Optional[str],
        max_retries: int = 3
    ) -> str:
        """
        Create a credit rating record with automatic retry on rate limits
        
        Implements exponential backoff when hitting Airtable rate limits (429 errors).
        
        Args:
            company_record_id: Airtable record ID of the company
            instrument: Instrument category
            rating: Credit rating
            outlook: Rating outlook
            instrument_amount: Instrument amount
            date: Date in YYYY-MM-DD format
            source_url: Source URL
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Airtable record ID of the created rating
        """
        for attempt in range(max_retries):
            try:
                # Prepare fields
                fields = {
                    "Company": [company_record_id],  # Link to company record
                    "Instrument": instrument if instrument and instrument != "Not found" else None,
                    "Rating": rating if rating and rating != "Not found" else None,
                }
                
                # Add optional fields
                if outlook and outlook != "Not found":
                    mapped_outlook = self._map_outlook(outlook)
                    if mapped_outlook:
                        fields["Outlook"] = mapped_outlook
                
                if instrument_amount and instrument_amount != "Not found":
                    fields["Instrument Amount"] = instrument_amount
                
                if date and date != "Not found":
                    parsed_date = self._parse_date(date)
                    if parsed_date:
                        fields["Date"] = parsed_date
                
                if source_url and source_url != "Not found":
                    fields["Source URL"] = source_url
                
                # Create the record
                new_record = self.credit_ratings_table.create(fields)
                logger.info(f"Created credit rating (ID: {new_record['id']}) for company {company_record_id}")
                return new_record['id']
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error (429 or explicit rate limit message)
                is_rate_limit = '429' in error_msg or 'rate limit' in error_msg or 'too many requests' in error_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit hit when creating rating, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                elif is_rate_limit:
                    logger.error(f"Rate limit exceeded after {max_retries} attempts")
                    raise Exception(f"Airtable rate limit exceeded after {max_retries} retries")
                else:
                    # Not a rate limit error, raise immediately
                    logger.error(f"Error creating credit rating: {str(e)}")
                    raise
        
        raise Exception(f"Failed to create rating after {max_retries} retries")
    
    def check_duplicate_rating(
        self,
        company_record_id: str,
        instrument: str,
        rating: str,
        date: str,
        seen_in_batch: Optional[Set[tuple]] = None
    ) -> bool:
        """
        Check if a rating already exists to prevent duplicates
        
        CRITICAL: This now properly checks by company_record_id to avoid false positives
        when different companies have the same instrument/rating/date combination.
        Also checks against a local set for duplicates within the current batch.
        
        Args:
            company_record_id: Airtable record ID of the company (NOT the name)
            instrument: Instrument category
            rating: Credit rating
            date: Date string
            seen_in_batch: Optional set of tuples (company_id, instrument, rating, date) 
                          to track duplicates within the current batch
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Parse the date for comparison
            parsed_date = self._parse_date(date)
            if not parsed_date:
                # If we can't parse the date, we can't reliably check for duplicates
                return False
            
            # Create a unique key for this rating
            rating_key = (company_record_id, instrument, rating, parsed_date)
            
            # FIRST check: query Airtable for existing records
            # This catches duplicates from previous jobs/requests
            # Escape single quotes in values to prevent formula injection
            safe_rating = rating.replace("'", "\\'")
            safe_instrument = instrument.replace("'", "\\'")
            
            # Build a formula that includes the company link
            # This ensures we only find duplicates for THIS specific company
            # Note: Company is a linked record field (array), so we use FIND to check if the ID is in the array
            formula = (
                f"AND("
                f"FIND('{company_record_id}', ARRAYJOIN({{Company}})), "
                f"{{Rating}} = '{safe_rating}', "
                f"{{Instrument}} = '{safe_instrument}', "
                f"{{Date}} = '{parsed_date}'"
                f")"
            )
            
            existing_records = self.credit_ratings_table.all(formula=formula, max_records=1)
            
            if existing_records:
                logger.info(f"Duplicate rating found in Airtable: {instrument} - {rating} on {parsed_date} for company {company_record_id}")
                return True
            
            # SECOND check: is this a duplicate within the current batch?
            # This prevents creating duplicates within the same batch before they're written to Airtable
            if seen_in_batch is not None:
                if rating_key in seen_in_batch:
                    logger.info(f"Duplicate rating found in current batch: {instrument} - {rating} on {parsed_date} for company {company_record_id}")
                    return True
                # Not a duplicate - add to seen set for future checks in this batch
                seen_in_batch.add(rating_key)
            
            # Not a duplicate - safe to create
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for duplicate: {str(e)}")
            # If we can't check, assume it's not a duplicate to avoid losing data
            return False
    
    def batch_create_ratings(
        self,
        ratings_data: List[Dict[str, Any]],
        use_batch_api: bool = True
    ) -> tuple[int, int]:
        """
        Create multiple credit ratings with optimized batch operations
        
        Improvements:
        1. Uses corrected duplicate check with company_record_id
        2. Batches company upserts first to maximize cache hits
        3. Uses Airtable's batch API to reduce API calls by ~75%
        4. Continues on error instead of failing entire batch
        5. Tracks seen ratings within batch to prevent duplicate creation
        
        Args:
            ratings_data: List of rating data dictionaries with keys:
                - company_name
                - instrument_category
                - rating
                - outlook
                - instrument_amount
                - date
                - url
            use_batch_api: Whether to use Airtable's batch create API (default: True)
        
        Returns:
            Tuple of (companies_created, ratings_created)
        """
        companies_created = 0
        ratings_created = 0
        
        if not ratings_data:
            return (0, 0)
        
        # Step 1: Collect all unique companies and upsert them first
        # This maximizes cache hits for subsequent ratings
        unique_companies = {r.get('company_name') for r in ratings_data if r.get('company_name')}
        company_id_map = {}
        companies_already_existed = set()  # Track which companies already existed in Airtable
        
        logger.info(f"Processing {len(unique_companies)} unique companies for {len(ratings_data)} ratings")
        
        for company_name in unique_companies:
            try:
                # Check if company exists in Airtable (not just cache)
                formula = f"{{Company Name}} = '{company_name}'"
                existing_records = self.companies_table.all(formula=formula)
                
                if existing_records:
                    # Company already exists
                    company_id = existing_records[0]['id']
                    companies_already_existed.add(company_name)
                    self._set_cached_company_id(company_name, company_id)
                    logger.info(f"Found existing company: {company_name} (ID: {company_id})")
                else:
                    # Create new company
                    new_record = self.companies_table.create({
                        "Company Name": company_name
                    })
                    company_id = new_record['id']
                    self._set_cached_company_id(company_name, company_id)
                    companies_created += 1
                    logger.info(f"Created new company: {company_name} (ID: {company_id})")
                
                company_id_map[company_name] = company_id
                
            except Exception as e:
                logger.error(f"Error upserting company '{company_name}': {e}")
                # Continue processing other companies
                continue
        
        if use_batch_api:
            # Step 2: Prepare records for batch creation (after deduplication)
            records_to_create = []
            seen_in_batch = set()  # Track ratings we've seen in this batch
            
            for rating_data in ratings_data:
                company_name = rating_data.get('company_name')
                if not company_name or company_name not in company_id_map:
                    continue
                
                company_record_id = company_id_map[company_name]
                
                # Check for duplicates using the CORRECTED method with company_record_id
                # AND track within-batch duplicates using seen_in_batch
                if self.check_duplicate_rating(
                    company_record_id,  # FIX: Now passing record ID, not name
                    rating_data.get('instrument_category', ''),
                    rating_data.get('rating', ''),
                    rating_data.get('date', ''),
                    seen_in_batch=seen_in_batch  # NEW: Track within-batch duplicates
                ):
                    logger.info(f"Skipping duplicate rating for {company_name}: {rating_data.get('instrument_category')} - {rating_data.get('rating')}")
                    continue
                
                # Prepare record fields
                fields = {
                    "Company": [company_record_id],
                    "Instrument": rating_data.get('instrument_category', ''),
                    "Rating": rating_data.get('rating', ''),
                }
                
                # Add optional fields
                if rating_data.get('outlook'):
                    mapped_outlook = self._map_outlook(rating_data['outlook'])
                    if mapped_outlook:
                        fields["Outlook"] = mapped_outlook
                
                if rating_data.get('instrument_amount'):
                    fields["Instrument Amount"] = rating_data['instrument_amount']
                
                if rating_data.get('date'):
                    parsed_date = self._parse_date(rating_data['date'])
                    if parsed_date:
                        fields["Date"] = parsed_date
                
                if rating_data.get('url'):
                    fields["Source URL"] = rating_data['url']
                
                records_to_create.append(fields)
            
            # Step 3: Batch create all ratings (up to 10 at a time per Airtable limit)
            batch_size = 10
            
            for i in range(0, len(records_to_create), batch_size):
                batch = records_to_create[i:i + batch_size]
                try:
                    # Use Airtable's batch_create method (creates up to 10 records in 1 API call)
                    created_records = self.credit_ratings_table.batch_create(batch)
                    ratings_created += len(created_records)
                    logger.info(f"Batch created {len(created_records)} ratings ({i+1}-{i+len(batch)} of {len(records_to_create)})")
                except Exception as e:
                    logger.error(f"Error in batch create: {str(e)}")
                    # Fallback: Try creating records individually for this batch
                    logger.warning("Falling back to individual creates for this batch")
                    for record_fields in batch:
                        try:
                            self.credit_ratings_table.create(record_fields)
                            ratings_created += 1
                        except Exception as create_error:
                            logger.error(f"Failed to create individual rating: {create_error}")
                            # Continue with next record
                            continue
        else:
            # Fallback: Create ratings one by one (old method)
            seen_in_batch = set()  # Track ratings we've seen in this batch
            
            for rating_data in ratings_data:
                try:
                    company_name = rating_data.get('company_name')
                    if not company_name or company_name not in company_id_map:
                        continue
                    
                    company_record_id = company_id_map[company_name]
                    
                    # Check for duplicates (CORRECTED + tracking within-batch duplicates)
                    if self.check_duplicate_rating(
                        company_record_id,  # FIX: Now passing record ID
                        rating_data.get('instrument_category', ''),
                        rating_data.get('rating', ''),
                        rating_data.get('date', ''),
                        seen_in_batch=seen_in_batch  # NEW: Track within-batch duplicates
                    ):
                        logger.info(f"Skipping duplicate rating for {company_name}: {rating_data.get('instrument_category')} - {rating_data.get('rating')}")
                        continue
                    
                    # Create credit rating
                    self.create_credit_rating(
                        company_record_id=company_record_id,
                        instrument=rating_data.get('instrument_category', ''),
                        rating=rating_data.get('rating', ''),
                        outlook=rating_data.get('outlook'),
                        instrument_amount=rating_data.get('instrument_amount'),
                        date=rating_data.get('date'),
                        source_url=rating_data.get('url')
                    )
                    ratings_created += 1
                    
                except Exception as e:
                    logger.error(f"Error creating rating for {rating_data.get('company_name')}: {str(e)}")
                    # Continue with next rating instead of failing entire batch
                    continue
        
        logger.info(f"Batch complete: {companies_created} companies created, {ratings_created} ratings created")
        return companies_created, ratings_created
    
    def clear_cache(self) -> None:
        """Clear the company cache"""
        self._company_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the company cache
        
        Returns:
            Dictionary with cache statistics including:
            - local_cache_size: Number of companies in local cache
            - redis_cache_size: Number of companies in Redis cache (if enabled)
            - redis_enabled: Whether Redis caching is enabled
        """
        stats = {
            "local_cache_size": len(self._company_cache),
            "redis_enabled": self.use_redis_cache,
            "redis_cache_size": 0
        }
        
        if self.use_redis_cache and self.redis_client:
            try:
                # Count keys matching the company cache pattern
                cache_keys = self.redis_client.keys("company:*")
                stats["redis_cache_size"] = len(cache_keys) if cache_keys else 0
            except Exception as e:
                logger.warning(f"Error getting Redis cache stats: {e}")
                stats["redis_cache_size"] = -1  # Indicate error
        
        return stats

