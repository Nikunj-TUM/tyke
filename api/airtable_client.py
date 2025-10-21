"""
Airtable API integration for Companies and Credit Ratings tables
"""
import logging
from typing import Optional, Dict, Any, List
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
    
    def __init__(self):
        """Initialize Airtable client"""
        self.api = Api(settings.AIRTABLE_API_KEY)
        self.base = self.api.base(settings.AIRTABLE_BASE_ID)
        
        # Get table references
        self.companies_table = self.base.table(settings.COMPANIES_TABLE_ID)
        self.credit_ratings_table = self.base.table(settings.CREDIT_RATINGS_TABLE_ID)
        
        # Cache for company records to avoid duplicate lookups
        self._company_cache: Dict[str, str] = {}  # company_name -> record_id
    
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
    
    def upsert_company(self, company_name: str) -> str:
        """
        Create or get existing company record
        
        Args:
            company_name: Name of the company
            
        Returns:
            Airtable record ID of the company
        """
        # Check cache first
        if company_name in self._company_cache:
            return self._company_cache[company_name]
        
        try:
            # Search for existing company
            formula = f"{{Company Name}} = '{company_name}'"
            existing_records = self.companies_table.all(formula=formula)
            
            if existing_records:
                record_id = existing_records[0]['id']
                self._company_cache[company_name] = record_id
                logger.info(f"Found existing company: {company_name} (ID: {record_id})")
                return record_id
            
            # Create new company
            new_record = self.companies_table.create({
                "Company Name": company_name
            })
            record_id = new_record['id']
            self._company_cache[company_name] = record_id
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
        source_url: Optional[str]
    ) -> str:
        """
        Create a credit rating record
        
        Args:
            company_record_id: Airtable record ID of the company
            instrument: Instrument category
            rating: Credit rating
            outlook: Rating outlook
            instrument_amount: Instrument amount
            date: Date in YYYY-MM-DD format
            source_url: Source URL
            
        Returns:
            Airtable record ID of the created rating
        """
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
            logger.error(f"Error creating credit rating: {str(e)}")
            raise
    
    def check_duplicate_rating(
        self,
        company_name: str,
        instrument: str,
        rating: str,
        date: str
    ) -> bool:
        """
        Check if a rating already exists to prevent duplicates
        
        Args:
            company_name: Company name
            instrument: Instrument category
            rating: Credit rating
            date: Date string
            
        Returns:
            True if duplicate exists, False otherwise
        """
        try:
            # Parse the date for comparison
            parsed_date = self._parse_date(date)
            if not parsed_date:
                # If we can't parse the date, we can't reliably check for duplicates
                return False
            
            # Build a formula to find matching records
            # Note: This is a simple check. For production, you might want more sophisticated logic
            formula = f"AND({{Rating}} = '{rating}', {{Instrument}} = '{instrument}', {{Date}} = '{parsed_date}')"
            
            existing_records = self.credit_ratings_table.all(formula=formula, max_records=1)
            
            if existing_records:
                logger.info(f"Duplicate rating found for {company_name} - {instrument} - {rating}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for duplicate: {str(e)}")
            # If we can't check, assume it's not a duplicate to avoid losing data
            return False
    
    def batch_create_ratings(
        self,
        ratings_data: List[Dict[str, Any]]
    ) -> tuple[int, int]:
        """
        Create multiple credit ratings in batch
        
        Args:
            ratings_data: List of rating data dictionaries with keys:
                - company_name
                - instrument_category
                - rating
                - outlook
                - instrument_amount
                - date
                - url
        
        Returns:
            Tuple of (companies_created, ratings_created)
        """
        companies_created = 0
        ratings_created = 0
        
        for rating_data in ratings_data:
            try:
                company_name = rating_data.get('company_name')
                if not company_name:
                    logger.warning("Skipping rating with no company name")
                    continue
                
                # Check if this is a duplicate
                if self.check_duplicate_rating(
                    company_name,
                    rating_data.get('instrument_category', ''),
                    rating_data.get('rating', ''),
                    rating_data.get('date', '')
                ):
                    logger.info(f"Skipping duplicate rating for {company_name}")
                    continue
                
                # Upsert company
                company_was_cached = company_name in self._company_cache
                company_record_id = self.upsert_company(company_name)
                if not company_was_cached:
                    companies_created += 1
                
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
                raise
        
        return companies_created, ratings_created
    
    def clear_cache(self) -> None:
        """Clear the company cache"""
        self._company_cache.clear()

