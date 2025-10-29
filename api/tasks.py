"""
Celery task definitions for distributed scraping and processing
"""
import logging
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from celery import group, chord, chain

from .celery_app import celery_app
from .scraper_service import ScraperService, InfomericsPressScraper, HTMLCreditRatingExtractor
from .airtable_client import AirtableClient
from .jobs import job_manager
from .models import JobStatus
from .config import settings

logger = logging.getLogger(__name__)

# Import database functions if PostgreSQL is enabled
if settings.USE_POSTGRES_DEDUPLICATION:
    from .database import (
        batch_insert_ratings,
        get_unsynced_ratings,
        get_company_airtable_id,
        update_company_airtable_id,
        update_ratings_airtable_ids,
        mark_ratings_sync_failed
    )


def split_date_range(start_date: str, end_date: str, chunk_days: int = 30) -> List[Tuple[str, str]]:
    """
    Split a date range into smaller chunks
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        chunk_days: Maximum days per chunk
        
    Returns:
        List of (start, end) date tuples
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    chunks = []
    current_start = start
    
    while current_start <= end:
        current_end = min(current_start + timedelta(days=chunk_days - 1), end)
        chunks.append((
            current_start.strftime('%Y-%m-%d'),
            current_end.strftime('%Y-%m-%d')
        ))
        current_start = current_end + timedelta(days=1)
    
    return chunks


@celery_app.task(bind=True, name='api.tasks.scrape_date_range_task')
def scrape_date_range_task(self, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    """
    Scrape HTML content for a given date range
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary containing HTML content and metadata
    """
    try:
        logger.info(f"Task {self.request.id}: Scraping {start_date} to {end_date}")
        
        scraper = InfomericsPressScraper()
        response_data = scraper.scrape_date_range(start_date, end_date)
        
        if not response_data:
            logger.error(f"Task {self.request.id}: Failed to scrape data")
            raise Exception("Failed to scrape data from Infomerics")
        
        logger.info(f"Task {self.request.id}: Scraped {len(response_data.get('body', ''))} characters")
        return response_data
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in scrape_date_range_task: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name='api.tasks.extract_instruments_task')
def extract_instruments_task(self, scrape_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract instrument data from HTML content
    
    Args:
        scrape_result: Result from scrape_date_range_task containing HTML
        
    Returns:
        List of extracted instrument dictionaries
    """
    try:
        logger.info(f"Task {self.request.id}: Extracting instruments from HTML")
        
        # Handle the scrape result
        if not scrape_result:
            logger.warning(f"Task {self.request.id}: Empty scrape result")
            return []
        
        html_content = scrape_result.get('body', '') if isinstance(scrape_result, dict) else ''
        
        if not html_content:
            logger.warning(f"Task {self.request.id}: Empty HTML content")
            return []
        
        # Extract company data
        extractor = HTMLCreditRatingExtractor(html_content)
        extracted_data = extractor.extract_company_data()
        
        # Convert to dictionaries
        data_dicts = []
        for item in extracted_data:
            data_dicts.append({
                'company_name': item.company_name,
                'instrument_category': item.instrument_category,
                'rating': item.rating,
                'outlook': item.outlook,
                'instrument_amount': item.instrument_amount,
                'date': item.date,
                'url': item.url
            })
        
        logger.info(f"Task {self.request.id}: Extracted {len(data_dicts)} instruments")
        return data_dicts
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in extract_instruments_task: {str(e)}")
        raise


@celery_app.task(bind=True, name='api.tasks.save_to_postgres_task')
def save_to_postgres_task(
    self,
    instruments_data: List[Dict[str, Any]],
    job_id: str
) -> Dict[str, int]:
    """
    Save scraped instruments to PostgreSQL with automatic deduplication
    
    Uses INSERT ... ON CONFLICT DO NOTHING for atomic duplicate detection.
    This is the core of the new deduplication strategy.
    
    After saving, triggers CIN lookup for newly created companies.
    
    Args:
        instruments_data: List of instrument dictionaries from extraction
        job_id: Job ID for tracking
        
    Returns:
        Dictionary with new_records and duplicate_records counts
    """
    try:
        logger.info(f"Task {self.request.id}: Saving {len(instruments_data)} instruments to PostgreSQL")
        
        if not instruments_data:
            logger.warning(f"Task {self.request.id}: No instruments to save")
            return {'new_records': 0, 'duplicate_records': 0}
        
        # Batch insert with deduplication
        new_records, duplicate_records = batch_insert_ratings(instruments_data, job_id)
        
        logger.info(f"Task {self.request.id}: PostgreSQL save complete")
        logger.info(f"  - New records: {new_records}")
        logger.info(f"  - Duplicates skipped: {duplicate_records}")
        
        return {
            'new_records': new_records,
            'duplicate_records': duplicate_records
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in save_to_postgres_task: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise self.retry(exc=e, countdown=30, max_retries=3)


@celery_app.task(bind=True, name='api.tasks.sync_postgres_to_airtable_task')
def sync_postgres_to_airtable_task(
    self,
    save_result: Dict[str, int],
    job_id: str
) -> Dict[str, int]:
    """
    Sync new records from PostgreSQL to Airtable using service layer.
    
    Clean orchestration layer - business logic is in services.
    
    Args:
        save_result: Result from save_to_postgres_task (for chaining)
        job_id: Job ID
        
    Returns:
        Dictionary with companies_synced, ratings_synced, and failures
    """
    try:
        logger.info(f"Task {self.request.id}: Starting Airtable sync for job {job_id}")
        
        # Import services
        from .services import CompanyService, RatingService
        
        # Initialize services with shared Airtable client
        from .airtable_client import AirtableClient
        airtable_client = AirtableClient()
        company_service = CompanyService(airtable_client)
        rating_service = RatingService(airtable_client)
        
        # Step 1: Sync companies first
        logger.info(f"Task {self.request.id}: Syncing companies...")
        company_result = company_service.sync_companies_for_job(job_id)
        companies_synced = company_result['companies_synced']
        companies_failed = company_result['companies_failed']
        
        logger.info(
            f"Task {self.request.id}: Company sync complete - "
            f"{companies_synced} synced, {companies_failed} failed"
        )
        
        # Step 2: Sync ratings (requires companies to be synced first)
        logger.info(f"Task {self.request.id}: Syncing ratings...")
        rating_result = rating_service.sync_ratings_for_job(job_id)
        ratings_synced = rating_result['ratings_synced']
        ratings_failed = rating_result['ratings_failed']
        
        logger.info(
            f"Task {self.request.id}: Rating sync complete - "
            f"{ratings_synced} synced, {ratings_failed} failed"
        )
        
        # Step 3: Return aggregated results
        total_failures = companies_failed + ratings_failed
        
        logger.info(f"Task {self.request.id}: Airtable sync complete")
        logger.info(f"  - Companies synced: {companies_synced}")
        logger.info(f"  - Ratings synced: {ratings_synced}")
        logger.info(f"  - Total failures: {total_failures}")
        
        # Step 4: Trigger CIN lookups AFTER companies have Airtable IDs
        try:
            from .services import CinOrchestrationService
            
            cin_orchestration = CinOrchestrationService()
            triggered_count = cin_orchestration.trigger_cin_lookups_for_job(job_id, limit=1000)
            
            logger.info(f"Task {self.request.id}: Triggered {triggered_count} CIN lookup chains")
                
        except Exception as e:
            # Don't fail the main task if CIN lookup triggering fails
            logger.error(f"Task {self.request.id}: Error triggering CIN lookups: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return {
            'companies_created': companies_synced,  # For backward compatibility
            'ratings_created': ratings_synced,      # For backward compatibility
            'companies_synced': companies_synced,
            'ratings_synced': ratings_synced,
            'sync_failures': total_failures
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in sync_postgres_to_airtable_task: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name='api.tasks.finalize_postgres_job_task')
def finalize_postgres_job_task(
    self,
    sync_result: Dict[str, int],
    job_id: str
) -> Dict[str, Any]:
    """
    Finalize job by updating job status with PostgreSQL metrics
    
    Args:
        sync_result: Result from sync_postgres_to_airtable_task
        job_id: Job ID
        
    Returns:
        Final job statistics
    """
    try:
        logger.info(f"Task {self.request.id}: Finalizing job {job_id}")
        
        # Update job with final statistics
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            companies_created=sync_result.get('companies_created', 0),
            ratings_created=sync_result.get('ratings_created', 0),
            uploaded_to_airtable=sync_result.get('ratings_created', 0),
            sync_failures=sync_result.get('sync_failures', 0)
        )
        
        logger.info(f"Task {self.request.id}: Job {job_id} finalized successfully")
        
        return {
            'status': 'completed',
            'job_id': job_id,
            **sync_result
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error finalizing job: {e}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


@celery_app.task(bind=True, name='api.tasks.process_scrape_results_with_postgres_task')
def process_scrape_results_with_postgres_task(
    self,
    scrape_results: List[Dict[str, Any]],
    job_id: str,
    is_chunked: bool = False
) -> Dict[str, int]:
    """
    Process scrape results using service layer - thin orchestration.
    
    Delegates all business logic to ScrapeProcessingService.
    
    Args:
        scrape_results: List of scrape results from parallel scraping
        job_id: Job ID for tracking
        is_chunked: Whether this came from chunked processing
        
    Returns:
        Processing results
    """
    try:
        logger.info(
            f"Task {self.request.id}: Starting processing for job {job_id} "
            f"({len(scrape_results)} scrape results)"
        )
        
        # Import service
        from .services import ScrapeProcessingService
        
        # Initialize service
        processing_service = ScrapeProcessingService()
        
        # Update job progress
        job_manager.update_job(job_id, progress=30)
        
        # Delegate all processing to service
        result = processing_service.process_scrape_results(scrape_results, job_id)
        
        # Check if any data was extracted
        if result['total_extracted'] == 0:
            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                total_extracted=0
            )
            return {'status': 'completed', 'total_extracted': 0}
        
        # Update job with intermediate progress
        job_manager.update_job(
            job_id,
            total_extracted=result['total_extracted'],
            total_scraped=result['new_records'] + result['duplicate_records'],
            new_records=result['new_records'],
            duplicate_records_skipped=result['duplicate_records'],
            progress=70
        )
        
        # Update job with final results
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            companies_created=result['companies_synced'],
            ratings_created=result['ratings_synced'],
            uploaded_to_airtable=result['ratings_synced'],
            sync_failures=result['sync_failures']
        )
        
        logger.info(
            f"Task {self.request.id}: Job {job_id} completed successfully - "
            f"{result['total_extracted']} extracted, {result['new_records']} new, "
            f"{result['ratings_synced']} synced"
        )
        
        return {
            'status': 'completed',
            **result
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error processing scrape results: {str(e)}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


# Legacy tasks removed - using PostgreSQL workflow exclusively


@celery_app.task(bind=True, name='api.tasks.process_scrape_job_orchestrator')
def process_scrape_job_orchestrator(self, job_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Orchestrator task for the scraping pipeline using PostgreSQL deduplication.
    
    Workflow: scrape -> extract -> save to postgres -> sync to airtable -> finalize
    Uses Celery's chain and group primitives for non-blocking execution.
    
    Args:
        job_id: Job ID for tracking
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with job results
    """
    try:
        logger.info(f"Task {self.request.id}: Starting orchestrator for job {job_id}")
        
        # Update job status
        job_manager.update_job(job_id, status=JobStatus.RUNNING, progress=5)
        
        # Calculate date range in days
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        date_range_days = (end - start).days
        
        # Build workflow using Celery canvas primitives
        if date_range_days > settings.MAX_DATE_CHUNK_DAYS:
            # Large date range: split into chunks and process in parallel
            logger.info(f"Task {self.request.id}: Splitting date range into chunks")
            chunks = split_date_range(start_date, end_date, settings.MAX_DATE_CHUNK_DAYS)
            
            # Parallel scraping of chunks
            scrape_tasks = group([
                scrape_date_range_task.s(chunk_start, chunk_end)
                for chunk_start, chunk_end in chunks
            ])
            
            # Chain: scrape (parallel) -> process and sync
            workflow = chain(
                    scrape_tasks,
                    process_scrape_results_with_postgres_task.s(job_id, is_chunked=True)
                )
        else:
            # Small date range: single chain workflow
            logger.info(f"Task {self.request.id}: Processing single date range")
            workflow = chain(
                    scrape_date_range_task.s(start_date, end_date),
                    extract_instruments_task.s(),
                    save_to_postgres_task.s(job_id),
                    sync_postgres_to_airtable_task.s(job_id),
                    finalize_postgres_job_task.s(job_id)
                )
        
        # Execute the workflow asynchronously
        workflow.apply_async()
        
        logger.info(f"Task {self.request.id}: Workflow initiated for job {job_id}")
        return {'status': 'workflow_initiated', 'job_id': job_id}
        
    except Exception as e:
        error_msg = f"Orchestrator failed: {str(e)}"
        logger.error(f"Task {self.request.id}: {error_msg}")
        logger.error(traceback.format_exc())
        
        job_manager.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=0
        )
        raise


# Deprecated functions removed - using canvas-based workflows exclusively


# ============================================================================
# ZaubaCorp CIN Lookup Tasks
# ============================================================================

@celery_app.task(bind=True, name='api.tasks.scrape_zaubacorp_task')
def scrape_zaubacorp_task(self, company_id: int, company_name: str) -> Dict[str, Any]:
    """
    Thin orchestration task for scraping ZaubaCorp CIN.
    
    Delegates business logic to CinLookupService.
    
    Args:
        company_id: Company ID in database
        company_name: Company name to search
        
    Returns:
        Dictionary with company_id, company_name, and html or error status
    """
    try:
        logger.info(f"Task {self.request.id}: Scraping ZaubaCorp for company {company_id}: {company_name}")
        
        from .services import CinLookupService
        service = CinLookupService()
        
        result = service.scrape_cin_html(company_id, company_name)
        
        logger.info(f"Task {self.request.id}: Scraping complete with status: {result.get('status')}")
        return result
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in scrape_zaubacorp_task: {str(e)}")
        return {
            'company_id': company_id,
            'company_name': company_name,
            'status': 'error'
        }


@celery_app.task(bind=True, name='api.tasks.extract_cin_task')
def extract_cin_task(self, scrape_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thin orchestration task for extracting CIN from ZaubaCorp HTML.
    
    Delegates business logic to CinLookupService.
    
    Args:
        scrape_result: Result from scrape_zaubacorp_task
        
    Returns:
        Dictionary with company_id, cin, and status
    """
    try:
        company_id = scrape_result.get('company_id')
        company_name = scrape_result.get('company_name')
        
        logger.info(f"Task {self.request.id}: Extracting CIN for company {company_id}: {company_name}")
        
        from .services import CinLookupService
        service = CinLookupService()
        
        result = service.extract_cin_from_html(scrape_result)
        
        logger.info(f"Task {self.request.id}: Extraction complete with status: {result.get('status')}")
        return result
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in extract_cin_task: {str(e)}")
        return {
            'company_id': scrape_result.get('company_id'),
            'cin': None,
            'status': 'error'
        }


@celery_app.task(bind=True, name='api.tasks.update_company_cin_task')
def update_company_cin_task(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thin orchestration task for updating company CIN.
    
    Delegates business logic to CinLookupService.
    
    Args:
        extraction_result: Result from extract_cin_task
        
    Returns:
        Dictionary with update results
    """
    try:
        company_id = extraction_result.get('company_id')
        cin = extraction_result.get('cin')
        status = extraction_result.get('status')
        
        logger.info(f"Task {self.request.id}: Updating CIN for company {company_id}: cin={cin}, status={status}")
        
        from .services import CinLookupService
        service = CinLookupService()
        
        result = service.update_company_cin(extraction_result)
        
        logger.info(
            f"Task {self.request.id}: Update complete - "
            f"Postgres: {result['postgres_updated']}, "
            f"Airtable: {result['airtable_updated']}"
        )
        return result
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in update_company_cin_task: {str(e)}")
        return {
            'company_id': extraction_result.get('company_id'),
            'postgres_updated': False,
            'airtable_updated': False
        }

