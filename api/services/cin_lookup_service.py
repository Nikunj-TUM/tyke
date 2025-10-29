"""
CIN Lookup Service

Handles business logic for scraping, extracting, and updating CIN 
(Company Identification Number) from ZaubaCorp.
"""
import logging
import base64
from typing import Dict, Any, Optional, List, Tuple
from celery import chain

logger = logging.getLogger(__name__)


class CinLookupService:
    """
    Service for managing CIN lookup operations.
    
    Responsibilities:
    - Scrape CIN from ZaubaCorp
    - Extract CIN from HTML
    - Update CIN in Postgres and Airtable
    """
    
    def scrape_cin_html(self, company_id: int, company_name: str) -> Dict[str, Any]:
        """
        Scrape ZaubaCorp to fetch CIN HTML for a company.
        
        Args:
            company_id: Company ID in database
            company_name: Company name to search
            
        Returns:
            Dictionary with company_id, company_name, and base64-encoded html or error status
        """
        try:
            from ..scraper_service import ZaubaCorpScraper
            
            scraper = ZaubaCorpScraper()
            html_content = scraper.scrape_company_search(company_name)
            
            if html_content:
                # Base64 encode HTML to preserve it through JSON serialization
                html_encoded = base64.b64encode(html_content.encode('utf-8')).decode('ascii')
                logger.info(f"Successfully scraped ZaubaCorp for {company_name}")
                return {
                    'company_id': company_id,
                    'company_name': company_name,
                    'html': html_encoded,
                    'status': 'success'
                }
            else:
                logger.warning(f"Failed to scrape ZaubaCorp for {company_name}")
                return {
                    'company_id': company_id,
                    'company_name': company_name,
                    'status': 'error'
                }
                
        except Exception as e:
            logger.error(f"Error scraping ZaubaCorp for {company_name}: {str(e)}")
            return {
                'company_id': company_id,
                'company_name': company_name,
                'status': 'error'
            }
    
    def extract_cin_from_html(self, scrape_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract CIN from ZaubaCorp HTML.
        
        If no results found and company has erstwhile name, marks for fallback scraping.
        
        Args:
            scrape_result: Result from scrape_cin_html containing base64-encoded HTML
            
        Returns:
            Dictionary with company_id, cin, status, and optional erstwhile_name for fallback
        """
        try:
            company_id = scrape_result.get('company_id')
            company_name = scrape_result.get('company_name')
            
            logger.info(f"Extracting CIN for company {company_id}: {company_name}")
            
            # Check if scraping was successful
            if scrape_result.get('status') == 'error':
                logger.warning(f"Skipping extraction due to scrape error for {company_name}")
                return {
                    'company_id': company_id,
                    'cin': None,
                    'status': 'error'
                }
            
            html_encoded = scrape_result.get('html')
            if not html_encoded:
                logger.warning(f"No HTML content to extract from for {company_name}")
                return {
                    'company_id': company_id,
                    'cin': None,
                    'status': 'error'
                }
            
            # Decode base64-encoded HTML
            try:
                html_content = base64.b64decode(html_encoded).decode('utf-8')
            except Exception as decode_error:
                logger.error(f"Error decoding HTML for {company_name}: {str(decode_error)}")
                return {
                    'company_id': company_id,
                    'cin': None,
                    'status': 'error'
                }
            
            # Extract CIN using the extractor
            from ..scraper_service import ZaubaCorpCINExtractor, ZaubaCorpScraper
            extractor = ZaubaCorpCINExtractor()
            cin, status = extractor.extract_cin(html_content, company_name)
            
            logger.info(f"Extraction complete for {company_name}: CIN={cin}, status={status}")
            
            result = {
                'company_id': company_id,
                'company_name': company_name,
                'cin': cin,
                'status': status
            }
            
            # If no results found or no match, check for erstwhile name for fallback
            if status in ('no_results', 'not_found'):
                scraper = ZaubaCorpScraper()
                erstwhile_name = scraper.extract_erstwhile_name(company_name)
                if erstwhile_name:
                    logger.info(f"Will trigger fallback search with erstwhile name: {erstwhile_name}")
                    result['erstwhile_name'] = erstwhile_name
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting CIN: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'company_id': scrape_result.get('company_id'),
                'cin': None,
                'status': 'error'
            }
    
    def update_company_cin(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update company CIN in Postgres and Airtable.
        
        If no results found and erstwhile name exists, triggers fallback scrape.
        
        Args:
            extraction_result: Result from extract_cin_from_html
            
        Returns:
            Dictionary with update results and fallback_triggered flag
        """
        try:
            company_id = extraction_result.get('company_id')
            cin = extraction_result.get('cin')
            status = extraction_result.get('status')
            erstwhile_name = extraction_result.get('erstwhile_name')
            
            logger.info(f"Updating CIN for company {company_id}: cin={cin}, status={status}")
            
            # If no match found but erstwhile name exists, trigger fallback scrape
            if status in ('no_results', 'not_found') and erstwhile_name:
                logger.info(f"Triggering fallback scrape for company {company_id} with erstwhile name: {erstwhile_name}")
                
                # Import tasks for fallback scraping
                import api.tasks as tasks
                
                # Trigger fallback chain with erstwhile name
                fallback_chain = chain(
                    tasks.scrape_zaubacorp_task.s(company_id, erstwhile_name),
                    tasks.extract_cin_task.s(),
                    tasks.update_company_cin_task.s()
                )
                fallback_chain.apply_async()
                
                logger.info(f"Fallback CIN lookup triggered for company {company_id}")
                
                return {
                    'company_id': company_id,
                    'postgres_updated': False,
                    'airtable_updated': False,
                    'fallback_triggered': True
                }
            
            # Update Postgres
            from ..database import update_company_cin, get_company_by_id
            
            postgres_updated = update_company_cin(company_id, cin, status)
            
            if not postgres_updated:
                logger.error(f"Failed to update Postgres for company {company_id}")
                return {
                    'company_id': company_id,
                    'postgres_updated': False,
                    'airtable_updated': False,
                    'fallback_triggered': False
                }
            
            logger.info(f"Postgres updated successfully for company {company_id}")
            
            # Update Airtable if CIN was found (includes 'found' and 'multiple_matches')
            airtable_updated = False
            if cin and status in ('found', 'multiple_matches'):
                company = get_company_by_id(company_id)
                if company and company.get('airtable_record_id'):
                    try:
                        from . import CompanyService
                        from ..airtable_client import AirtableClient
                        
                        airtable_client = AirtableClient()
                        company_service = CompanyService(airtable_client)
                        
                        airtable_updated = company_service.update_company_cin_in_airtable(
                            company['company_name'],
                            cin
                        )
                        
                        if airtable_updated:
                            logger.info(f"Airtable updated successfully for company {company_id}")
                        else:
                            logger.warning(f"Failed to update Airtable for company {company_id}")
                            
                    except Exception as e:
                        logger.error(f"Error updating Airtable for company {company_id}: {str(e)}")
                else:
                    logger.info(f"Skipping Airtable update - no Airtable ID for company {company_id}")
            
            return {
                'company_id': company_id,
                'postgres_updated': postgres_updated,
                'airtable_updated': airtable_updated,
                'fallback_triggered': False
            }
            
        except Exception as e:
            logger.error(f"Error updating company CIN: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'company_id': extraction_result.get('company_id'),
                'postgres_updated': False,
                'airtable_updated': False,
                'fallback_triggered': False
            }


class CinOrchestrationService:
    """
    Service for orchestrating CIN lookup workflows.
    
    Responsibilities:
    - Trigger CIN lookup task chains for jobs
    - Manage batch CIN lookup operations
    """
    
    def trigger_cin_lookups_for_job(self, job_id: str, limit: int = 1000) -> int:
        """
        Trigger CIN lookup task chains for all pending companies in a job.
        
        Args:
            job_id: Job ID to trigger CIN lookups for
            limit: Maximum number of companies to process
            
        Returns:
            Number of CIN lookup chains triggered
        """
        try:
            from ..database import get_companies_needing_cin_lookup
            # Import tasks at runtime to avoid circular dependency
            import api.tasks as tasks
            
            companies_needing_cin = get_companies_needing_cin_lookup(job_id=job_id, limit=limit)
            
            if not companies_needing_cin:
                logger.info(f"No companies need CIN lookup for job {job_id}")
                return 0
            
            logger.info(f"Triggering CIN lookup for {len(companies_needing_cin)} companies in job {job_id}")
            
            # Trigger async task chains for each company
            triggered_count = 0
            for company in companies_needing_cin:
                company_id = company['id']
                company_name = company['company_name']
                
                # Create task chain: scrape -> extract -> update
                cin_lookup_chain = chain(
                    tasks.scrape_zaubacorp_task.s(company_id, company_name),
                    tasks.extract_cin_task.s(),
                    tasks.update_company_cin_task.s()
                )
                
                # Execute asynchronously (non-blocking)
                cin_lookup_chain.apply_async()
                triggered_count += 1
            
            logger.info(f"CIN lookup chains initiated for {triggered_count} companies in job {job_id}")
            return triggered_count
            
        except Exception as e:
            logger.error(f"Error triggering CIN lookups for job {job_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

