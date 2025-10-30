"""
Airtable API integration for Companies and Credit Ratings tables

Simplified client that only handles API calls. No caching - Postgres is source of truth.
"""
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
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
    """
    Simplified Airtable API client.
    
    This client only handles API calls. No caching or business logic.
    Postgres is the single source of truth for data and mappings.
    """
    
    def __init__(self):
        """Initialize Airtable client with API credentials"""
        self.api = Api(settings.AIRTABLE_API_KEY)
        self.base = self.api.base(settings.AIRTABLE_BASE_ID)
        
        # Get table references
        self.companies_table = self.base.table(settings.COMPANIES_TABLE_ID)
        self.credit_ratings_table = self.base.table(settings.CREDIT_RATINGS_TABLE_ID)
        self.infomerics_scraper_table = self.base.table(settings.INFOMERICS_SCRAPER_TABLE_ID)
        self.contacts_table = self.base.table(settings.CONTACTS_TABLE_ID)
        
        logger.info("AirtableClient initialized")
    
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
    
    def create_company(self, company_name: str) -> str:
        """
        Create a new company in Airtable.
        
        No search/cache - caller (service layer) is responsible for checking
        if company already exists in Postgres before calling this.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Airtable record ID of the created company
            
        Raises:
            Exception: If creation fails
        """
        try:
            new_record = self.companies_table.create({
                "Company Name": company_name
            })
            record_id = new_record['id']
            logger.info(f"Created company in Airtable: {company_name} (ID: {record_id})")
            return record_id
        except Exception as e:
            logger.error(f"Error creating company '{company_name}' in Airtable: {str(e)}")
            raise
    
    def batch_create_companies(self, company_names: List[str]) -> List[Dict[str, Any]]:
        """
        Batch create companies in Airtable.
        
        Args:
            company_names: List of company names to create
            
        Returns:
            List of created records with 'id' and 'fields'
            
        Raises:
            Exception: If batch creation fails
        """
        if not company_names:
            return []
        
        try:
            records_to_create = [{"Company Name": name} for name in company_names]
            created_records = self.companies_table.batch_create(records_to_create)
            logger.info(f"Batch created {len(created_records)} companies in Airtable")
            return created_records
        except Exception as e:
            logger.error(f"Error batch creating companies in Airtable: {str(e)}")
            raise
    
    def update_company_cin(self, airtable_record_id: str, cin: str) -> bool:
        """
        Update CIN field for a company in Airtable
        
        Args:
            airtable_record_id: Airtable record ID of the company
            cin: CIN value to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.companies_table.update(airtable_record_id, {"CIN": cin})
            logger.info(f"Updated CIN for company {airtable_record_id}: {cin}")
            return True
        except Exception as e:
            logger.error(f"Error updating CIN for company {airtable_record_id}: {str(e)}")
            return False
    
    def batch_create_ratings(
        self,
        ratings_data: List[Dict[str, Any]],
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Batch create credit ratings in Airtable with retry logic.
        
        Args:
            ratings_data: List of rating dictionaries with keys:
                - company_airtable_id: Airtable ID of the company
                - instrument: Instrument category
                - rating: Credit rating
                - outlook: Rating outlook (optional)
                - instrument_amount: Instrument amount (optional)
                - date: Date string (optional)
                - source_url: Source URL (optional)
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of created records with 'id' and 'fields'
            
        Raises:
            Exception: If batch creation fails after retries
        """
        if not ratings_data:
            return []
        
        # Prepare records for batch creation
        records_to_create = []
        for rating in ratings_data:
            fields = {
                "Company": [rating['company_airtable_id']],
                "Instrument": rating.get('instrument', ''),
                "Rating": rating.get('rating', ''),
            }
            
            # Add optional fields
            if rating.get('outlook'):
                mapped_outlook = self._map_outlook(rating['outlook'])
                if mapped_outlook:
                    fields["Outlook"] = mapped_outlook
            
            if rating.get('instrument_amount'):
                fields["Instrument Amount"] = rating['instrument_amount']
            
            if rating.get('date'):
                parsed_date = self._parse_date(rating['date'])
                if parsed_date:
                    fields["Date"] = parsed_date
            
            if rating.get('source_url'):
                fields["Source URL"] = rating['source_url']
            
            records_to_create.append(fields)
        
        # Batch create with retry logic for rate limits
        for attempt in range(max_retries):
            try:
                created_records = self.credit_ratings_table.batch_create(records_to_create)
                logger.info(f"Batch created {len(created_records)} ratings in Airtable")
                return created_records
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = '429' in error_msg or 'rate limit' in error_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error batch creating ratings: {str(e)}")
                    raise
        
        raise Exception(f"Failed to batch create ratings after {max_retries} retries")
    
    def update_scraper_status(
        self,
        record_id: str,
        status: str
    ) -> bool:
        """
        Update the status of a scraper record in the Infomerics Scraper table.
        
        Args:
            record_id: Airtable record ID in Infomerics Scraper table
            status: Status to set - one of: "Todo", "In progress", "Done", "Error"
            
        Returns:
            True if successful, False otherwise
        """
        if not record_id:
            logger.warning("Cannot update scraper status: record_id is empty")
            return False
        
        # Validate status value matches Airtable schema
        valid_statuses = ["Todo", "In progress", "Done", "Error"]
        if status not in valid_statuses:
            logger.warning(f"Invalid status '{status}', must be one of {valid_statuses}")
            return False
        
        try:
            self.infomerics_scraper_table.update(record_id, {"Status": status})
            logger.info(f"Updated Infomerics Scraper record {record_id} status to '{status}'")
            return True
        except Exception as e:
            logger.error(f"Error updating scraper status for record {record_id}: {str(e)}")
            return False
    
    def batch_create_contacts(
        self,
        contacts_data: List[Dict[str, Any]],
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Batch create contacts in Airtable with retry logic.
        
        Args:
            contacts_data: List of contact dictionaries with keys:
                - name: Full name of the contact
                - phone_number: Mobile number (optional)
                - email: Email address (optional)
                - address: Full address string (optional)
                - company_airtable_id: Airtable ID of the company to link
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of created records with 'id' and 'fields'
            
        Raises:
            Exception: If batch creation fails after retries
        """
        if not contacts_data:
            return []
        
        # Prepare records for batch creation
        records_to_create = []
        for contact in contacts_data:
            fields = {
                "Name": contact.get('name', ''),
            }
            
            # Add optional fields
            if contact.get('phone_number'):
                fields["Phone Number"] = contact['phone_number']
            
            if contact.get('email'):
                fields["Email"] = contact['email']
            
            if contact.get('address'):
                fields["Address"] = contact['address']
            
            # Link to company
            if contact.get('company_airtable_id'):
                fields["Company Name"] = [contact['company_airtable_id']]
            
            records_to_create.append(fields)
        
        # Batch create with retry logic for rate limits
        for attempt in range(max_retries):
            try:
                created_records = self.contacts_table.batch_create(records_to_create)
                logger.info(f"Batch created {len(created_records)} contacts in Airtable")
                return created_records
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = '429' in error_msg or 'rate limit' in error_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error batch creating contacts: {str(e)}")
                    raise
        
        raise Exception(f"Failed to batch create contacts after {max_retries} retries")
    
    def update_contact(
        self,
        airtable_record_id: str,
        fields: Dict[str, Any]
    ) -> bool:
        """
        Update a contact record in Airtable
        
        Args:
            airtable_record_id: Airtable record ID of the contact
            fields: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.contacts_table.update(airtable_record_id, fields)
            logger.info(f"Updated contact {airtable_record_id} in Airtable")
            return True
        except Exception as e:
            logger.error(f"Error updating contact {airtable_record_id}: {str(e)}")
            return False

