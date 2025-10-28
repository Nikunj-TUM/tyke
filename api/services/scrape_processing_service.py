"""
Scrape Processing Service

Handles business logic for processing scraped data through the full pipeline.
"""
import logging
from typing import Dict, List, Any
from ..scraper_service import HTMLCreditRatingExtractor
from ..database import batch_insert_ratings
from ..airtable_client import AirtableClient
from .company_service import CompanyService
from .rating_service import RatingService

logger = logging.getLogger(__name__)


class ScrapeProcessingService:
    """
    Service for processing scraped data through the full pipeline.
    
    Responsibilities:
    - Extract data from HTML
    - Transform to standardized format
    - Save to Postgres with deduplication
    - Sync to Airtable
    - Track metrics and errors
    """
    
    def __init__(
        self,
        company_service: CompanyService = None,
        rating_service: RatingService = None
    ):
        """
        Initialize scrape processing service.
        
        Args:
            company_service: Optional CompanyService instance
            rating_service: Optional RatingService instance
        """
        airtable_client = AirtableClient()
        self.company_service = company_service or CompanyService(airtable_client)
        self.rating_service = rating_service or RatingService(airtable_client)
    
    def process_scrape_results(
        self,
        scrape_results: List[Dict[str, Any]],
        job_id: str
    ) -> Dict[str, Any]:
        """
        Process multiple scrape results through the full pipeline.
        
        This is the main entry point for processing scraped data.
        
        Args:
            scrape_results: List of scrape result dictionaries with 'body' HTML
            job_id: Job ID for tracking
            
        Returns:
            Dictionary with processing statistics:
            - total_extracted: Total instruments extracted
            - new_records: New records inserted to Postgres
            - duplicate_records: Duplicate records skipped
            - companies_synced: Companies synced to Airtable
            - ratings_synced: Ratings synced to Airtable
            - sync_failures: Total sync failures
        """
        logger.info(f"Processing {len(scrape_results)} scrape results for job {job_id}")
        
        # Step 1: Extract and transform data
        all_instruments = self._extract_instruments_from_results(scrape_results)
        
        if not all_instruments:
            logger.warning(f"No instruments extracted for job {job_id}")
            return {
                'total_extracted': 0,
                'new_records': 0,
                'duplicate_records': 0,
                'companies_synced': 0,
                'ratings_synced': 0,
                'sync_failures': 0
            }
        
        logger.info(f"Extracted {len(all_instruments)} total instruments")
        
        # Step 2: Save to Postgres with deduplication
        new_records, duplicate_records = self._save_to_postgres(
            all_instruments,
            job_id
        )
        
        logger.info(
            f"Postgres save complete: {new_records} new, "
            f"{duplicate_records} duplicates"
        )
        
        # Step 3: Sync to Airtable
        sync_stats = self._sync_to_airtable(job_id)
        
        logger.info(
            f"Airtable sync complete: {sync_stats['companies_synced']} companies, "
            f"{sync_stats['ratings_synced']} ratings"
        )
        
        # Return comprehensive stats
        return {
            'total_extracted': len(all_instruments),
            'new_records': new_records,
            'duplicate_records': duplicate_records,
            'companies_synced': sync_stats['companies_synced'],
            'ratings_synced': sync_stats['ratings_synced'],
            'sync_failures': sync_stats['sync_failures']
        }
    
    def _extract_instruments_from_results(
        self,
        scrape_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract instruments from multiple scrape results.
        
        Args:
            scrape_results: List of scrape result dictionaries
            
        Returns:
            List of extracted instrument dictionaries
        """
        all_instruments = []
        
        for i, result in enumerate(scrape_results):
            if not result or not result.get('body'):
                logger.warning(f"Scrape result {i+1} has no body, skipping")
                continue
            
            try:
                html_content = result['body']
                extractor = HTMLCreditRatingExtractor(html_content)
                extracted_data = extractor.extract_company_data()
                
                # Convert to dictionaries
                for item in extracted_data:
                    all_instruments.append({
                        'company_name': item.company_name,
                        'instrument_category': item.instrument_category,
                        'rating': item.rating,
                        'outlook': item.outlook,
                        'instrument_amount': item.instrument_amount,
                        'date': item.date,
                        'url': item.url
                    })
                
                logger.info(
                    f"Chunk {i+1}/{len(scrape_results)}: "
                    f"Extracted {len(extracted_data)} instruments"
                )
                
            except Exception as e:
                logger.error(f"Error extracting from chunk {i+1}: {str(e)}")
                continue
        
        return all_instruments
    
    def _save_to_postgres(
        self,
        instruments: List[Dict[str, Any]],
        job_id: str
    ) -> tuple[int, int]:
        """
        Save instruments to Postgres with deduplication.
        
        Args:
            instruments: List of instrument dictionaries
            job_id: Job ID for tracking
            
        Returns:
            Tuple of (new_records, duplicate_records)
        """
        try:
            new_records, duplicate_records = batch_insert_ratings(
                instruments,
                job_id
            )
            return (new_records, duplicate_records)
        except Exception as e:
            logger.error(f"Error saving to Postgres: {str(e)}")
            raise
    
    def _sync_to_airtable(self, job_id: str) -> Dict[str, int]:
        """
        Sync data to Airtable using company and rating services.
        
        Args:
            job_id: Job ID for tracking
            
        Returns:
            Dictionary with sync statistics
        """
        # Sync companies first
        company_result = self.company_service.sync_companies_for_job(job_id)
        
        # Then sync ratings
        rating_result = self.rating_service.sync_ratings_for_job(job_id)
        
        return {
            'companies_synced': company_result['companies_synced'],
            'ratings_synced': rating_result['ratings_synced'],
            'sync_failures': (
                company_result['companies_failed'] +
                rating_result['ratings_failed']
            )
        }

