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
    Sync new records from PostgreSQL to Airtable
    
    This task:
    1. Queries PostgreSQL for unsynced ratings
    2. Groups by company and resolves/creates Airtable company records
    3. Batch uploads ratings to Airtable
    4. Updates PostgreSQL with Airtable record IDs
    
    Args:
        save_result: Result from save_to_postgres_task (for chaining)
        job_id: Job ID
        
    Returns:
        Dictionary with companies_created and ratings_created counts
    """
    try:
        logger.info(f"Task {self.request.id}: Starting Airtable sync for job {job_id}")
        
        # Get unsynced ratings from PostgreSQL
        unsynced_ratings = get_unsynced_ratings(job_id)
        
        if not unsynced_ratings:
            logger.info(f"Task {self.request.id}: No new records to sync")
            return {'companies_created': 0, 'ratings_created': 0}
        
        logger.info(f"Task {self.request.id}: Syncing {len(unsynced_ratings)} ratings to Airtable")
        
        airtable_client = AirtableClient()
        
        # Step 1: Resolve company Airtable IDs
        company_airtable_map = {}
        unique_companies = set(r['company_name'] for r in unsynced_ratings)
        companies_created = 0
        
        for company_name in unique_companies:
            # Check PostgreSQL first
            airtable_id = get_company_airtable_id(company_name)
            
            if airtable_id:
                company_airtable_map[company_name] = airtable_id
                logger.debug(f"  Company '{company_name}' already has Airtable ID: {airtable_id}")
            else:
                # Create/get from Airtable
                try:
                    airtable_id = airtable_client.upsert_company(company_name)
                    company_airtable_map[company_name] = airtable_id
                    
                    # Save to PostgreSQL
                    update_company_airtable_id(company_name, airtable_id)
                    companies_created += 1
                    logger.info(f"  Created/found company in Airtable: {company_name} ({airtable_id})")
                except Exception as e:
                    logger.error(f"  Failed to upsert company '{company_name}': {e}")
                    # Continue with other companies
                    continue
        
        # Step 2: Batch upload ratings to Airtable
        batch_size = 10
        ratings_created = 0
        failed_rating_ids = []
        rating_airtable_mapping = []  # (rating_id, airtable_record_id) tuples
        
        for i in range(0, len(unsynced_ratings), batch_size):
            batch = unsynced_ratings[i:i + batch_size]
            records_to_create = []
            batch_rating_ids = []
            
            for rating in batch:
                company_name = rating['company_name']
                
                # Skip if company couldn't be resolved
                if company_name not in company_airtable_map:
                    failed_rating_ids.append(rating['id'])
                    continue
                
                company_airtable_id = company_airtable_map[company_name]
                
                # Prepare Airtable record
                fields = {
                    "Company": [company_airtable_id],
                    "Instrument": rating['instrument'],
                    "Rating": rating['rating'],
                }
                
                if rating.get('outlook'):
                    fields["Outlook"] = airtable_client._map_outlook(rating['outlook'])
                if rating.get('instrument_amount'):
                    fields["Instrument Amount"] = rating['instrument_amount']
                if rating.get('date'):
                    fields["Date"] = rating['date'].strftime('%Y-%m-%d')
                if rating.get('source_url'):
                    fields["Source URL"] = rating['source_url']
                
                records_to_create.append(fields)
                batch_rating_ids.append(rating['id'])
            
            if not records_to_create:
                continue
            
            # Batch create in Airtable with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    created_records = airtable_client.credit_ratings_table.batch_create(records_to_create)
                    ratings_created += len(created_records)
                    
                    # Map rating IDs to Airtable record IDs
                    for j, airtable_record in enumerate(created_records):
                        if j < len(batch_rating_ids):
                            rating_airtable_mapping.append((
                                batch_rating_ids[j],
                                airtable_record['id']
                            ))
                    
                    logger.info(f"Task {self.request.id}: Synced batch {i//batch_size + 1}: {len(created_records)} ratings")
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    is_rate_limit = '429' in error_msg or 'rate limit' in error_msg
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"  Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"  Failed to sync batch after {max_retries} attempts: {e}")
                        failed_rating_ids.extend(batch_rating_ids)
                        break
        
        # Step 3: Update PostgreSQL with Airtable record IDs
        if rating_airtable_mapping:
            updated_count = update_ratings_airtable_ids(rating_airtable_mapping)
            logger.info(f"Task {self.request.id}: Updated {updated_count} ratings with Airtable IDs")
        
        # Step 4: Mark failed ratings
        if failed_rating_ids:
            mark_ratings_sync_failed(failed_rating_ids, "Failed to sync to Airtable")
            logger.warning(f"Task {self.request.id}: {len(failed_rating_ids)} ratings failed to sync")
        
        logger.info(f"Task {self.request.id}: Airtable sync complete")
        logger.info(f"  - Companies created: {companies_created}")
        logger.info(f"  - Ratings synced: {ratings_created}")
        logger.info(f"  - Sync failures: {len(failed_rating_ids)}")
        
        return {
            'companies_created': companies_created,
            'ratings_created': ratings_created,
            'sync_failures': len(failed_rating_ids)
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
    Process scrape results using PostgreSQL deduplication workflow
    
    This combines extraction, PostgreSQL save, and Airtable sync for chunked scraping
    
    Args:
        scrape_results: List of scrape results from parallel scraping
        job_id: Job ID for tracking
        is_chunked: Whether this came from chunked processing
        
    Returns:
        Processing results
    """
    try:
        logger.info(f"Task {self.request.id}: Processing {len(scrape_results)} scrape results with PostgreSQL")
        
        # Combine all HTML from chunks and extract
        all_instruments = []
        
        for i, result in enumerate(scrape_results):
            if result and result.get('body'):
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
                
                logger.info(f"Task {self.request.id}: Chunk {i+1} extracted {len(extracted_data)} instruments")
        
        logger.info(f"Task {self.request.id}: Total extracted: {len(all_instruments)} instruments")
        
        if not all_instruments:
            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                total_extracted=0
            )
            return {'status': 'completed', 'total_extracted': 0}
        
        # Update progress
        job_manager.update_job(job_id, total_extracted=len(all_instruments), progress=50)
        
        # Save to PostgreSQL
        new_records, duplicate_records = batch_insert_ratings(all_instruments, job_id)
        
        job_manager.update_job(
            job_id,
            total_scraped=new_records + duplicate_records,
            new_records=new_records,
            duplicate_records_skipped=duplicate_records,
            progress=70
        )
        
        # Sync to Airtable
        sync_result = sync_postgres_to_airtable_task(
            {'new_records': new_records, 'duplicate_records': duplicate_records},
            job_id
        )
        
        # Finalize job
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            companies_created=sync_result.get('companies_created', 0),
            ratings_created=sync_result.get('ratings_created', 0),
            uploaded_to_airtable=sync_result.get('ratings_created', 0),
            sync_failures=sync_result.get('sync_failures', 0)
        )
        
        logger.info(f"Task {self.request.id}: Job {job_id} completed successfully")
        
        return {
            'status': 'completed',
            'total_extracted': len(all_instruments),
            'new_records': new_records,
            'duplicate_records': duplicate_records,
            **sync_result
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error processing scrape results: {str(e)}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


@celery_app.task(bind=True, name='api.tasks.upload_batch_to_airtable_task')
def upload_batch_to_airtable_task(
    self,
    batch_data: List[Dict[str, Any]]
) -> Tuple[int, int]:
    """
    Upload a batch of instruments to Airtable
    
    Args:
        batch_data: List of instrument dictionaries
        
    Returns:
        Tuple of (companies_created, ratings_created)
    """
    try:
        logger.info(f"Task {self.request.id}: Uploading {len(batch_data)} instruments to Airtable")
        
        airtable_client = AirtableClient()
        companies_created, ratings_created = airtable_client.batch_create_ratings(batch_data)
        
        logger.info(f"Task {self.request.id}: Created {companies_created} companies, {ratings_created} ratings")
        return companies_created, ratings_created
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in upload_batch_to_airtable_task: {str(e)}")
        raise self.retry(exc=e, countdown=30, max_retries=3)


@celery_app.task(bind=True, name='api.tasks.batch_and_upload_task')
def batch_and_upload_task(self, instruments: List[Dict[str, Any]], job_id: str) -> Dict[str, int]:
    """
    Batch instruments and upload to Airtable using parallel upload tasks
    
    Args:
        instruments: List of extracted instruments
        job_id: Job ID for tracking
        
    Returns:
        Dictionary with upload counts
    """
    try:
        logger.info(f"Task {self.request.id}: Batching and uploading {len(instruments)} instruments")
        
        if not instruments:
            logger.warning(f"Task {self.request.id}: No instruments to upload")
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)
            return {'companies_created': 0, 'ratings_created': 0}
        
        # Update job with extraction count
        job_manager.update_job(job_id, total_extracted=len(instruments), progress=50)
        
        # Split into batches
        batch_size = settings.AIRTABLE_BATCH_SIZE
        batches = [instruments[i:i + batch_size] for i in range(0, len(instruments), batch_size)]
        
        logger.info(f"Task {self.request.id}: Created {len(batches)} upload batches")
        
        # Create a chord: upload all batches in parallel -> aggregate results
        upload_group = group([
            upload_batch_to_airtable_task.s(batch)
            for batch in batches
        ])
        
        # Use chord to aggregate results after all uploads complete
        callback = aggregate_upload_results.s(job_id)
        workflow = chord(upload_group)(callback)
        
        # Wait for the chord to complete (this is allowed in a non-orchestrator task)
        # Actually, we shouldn't wait here either. Let's just return a marker.
        return {'status': 'upload_initiated', 'batch_count': len(batches)}
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in batch_and_upload_task: {str(e)}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


@celery_app.task(bind=True, name='api.tasks.aggregate_upload_results')
def aggregate_upload_results(self, results: List[Tuple[int, int]], job_id: str) -> Dict[str, int]:
    """
    Aggregate results from multiple upload tasks (chord callback)
    
    Args:
        results: List of (companies_created, ratings_created) tuples from upload tasks
        job_id: Job ID to update
        
    Returns:
        Dictionary with aggregated counts
    """
    try:
        total_companies = sum(r[0] for r in results)
        total_ratings = sum(r[1] for r in results)
        
        logger.info(f"Task {self.request.id}: Aggregated {total_companies} companies, {total_ratings} ratings")
        
        # Update job with final counts
        job_manager.update_job(
            job_id,
            companies_created=total_companies,
            ratings_created=total_ratings,
            uploaded_to_airtable=total_ratings,
            progress=100,
            status=JobStatus.COMPLETED
        )
        
        return {
            'companies_created': total_companies,
            'ratings_created': total_ratings
        }
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error in aggregate_upload_results: {str(e)}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


@celery_app.task(bind=True, name='api.tasks.process_scrape_results_task')
def process_scrape_results_task(self, scrape_results: List[Dict[str, Any]], job_id: str, is_chunked: bool = False) -> Dict[str, int]:
    """
    Process results from scraping tasks and dispatch extraction/upload
    
    Args:
        scrape_results: List of scrape results from parallel scraping
        job_id: Job ID for tracking
        is_chunked: Whether this came from chunked processing
        
    Returns:
        Processing results
    """
    try:
        logger.info(f"Task {self.request.id}: Processing {len(scrape_results)} scrape results")
        
        # Combine all HTML from chunks
        all_instruments = []
        
        for i, result in enumerate(scrape_results):
            if result and result.get('body'):
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
                
                logger.info(f"Task {self.request.id}: Chunk {i+1} extracted {len(extracted_data)} instruments")
        
        logger.info(f"Task {self.request.id}: Total extracted: {len(all_instruments)} instruments")
        
        # Now batch and upload
        if not all_instruments:
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)
            return {'companies_created': 0, 'ratings_created': 0}
        
        # Update progress and dispatch upload workflow
        job_manager.update_job(job_id, total_extracted=len(all_instruments), progress=50)
        
        # Create upload workflow
        batch_size = settings.AIRTABLE_BATCH_SIZE
        batches = [all_instruments[i:i + batch_size] for i in range(0, len(all_instruments), batch_size)]
        
        upload_group = group([
            upload_batch_to_airtable_task.s(batch)
            for batch in batches
        ])
        
        callback = aggregate_upload_results.s(job_id)
        chord(upload_group)(callback)
        
        return {'status': 'upload_initiated', 'total_extracted': len(all_instruments)}
        
    except Exception as e:
        logger.error(f"Task {self.request.id}: Error processing scrape results: {str(e)}")
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


@celery_app.task(bind=True, name='api.tasks.process_scrape_job_orchestrator')
def process_scrape_job_orchestrator(self, job_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Orchestrator task for the entire scraping pipeline using Celery canvas
    
    This creates a workflow chain: scrape -> extract -> upload
    Uses Celery's chain and chord primitives to avoid blocking .get() calls
    
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
        
        # Build the workflow using Celery canvas primitives
        # This avoids blocking .get() calls within tasks
        
        # Choose workflow based on PostgreSQL deduplication flag
        use_postgres = settings.USE_POSTGRES_DEDUPLICATION
        
        if date_range_days > settings.MAX_DATE_CHUNK_DAYS:
            logger.info(f"Task {self.request.id}: Splitting date range into chunks")
            chunks = split_date_range(start_date, end_date, settings.MAX_DATE_CHUNK_DAYS)
            
            # Create a group of scraping tasks for parallel execution
            scrape_tasks = group([
                scrape_date_range_task.s(chunk_start, chunk_end)
                for chunk_start, chunk_end in chunks
            ])
            
            # Chain: scrape (parallel) -> process results -> extract -> save/upload
            if use_postgres:
                workflow = chain(
                    scrape_tasks,
                    process_scrape_results_with_postgres_task.s(job_id, is_chunked=True)
                )
            else:
                workflow = chain(
                    scrape_tasks,
                    process_scrape_results_task.s(job_id, is_chunked=True)
                )
        else:
            logger.info(f"Task {self.request.id}: Processing single date range")
            
            if use_postgres:
                # NEW PostgreSQL workflow: scrape -> extract -> save to postgres -> sync to airtable
                logger.info(f"Task {self.request.id}: Using PostgreSQL deduplication")
                workflow = chain(
                    scrape_date_range_task.s(start_date, end_date),
                    extract_instruments_task.s(),
                    save_to_postgres_task.s(job_id),
                    sync_postgres_to_airtable_task.s(job_id),
                    finalize_postgres_job_task.s(job_id)
                )
            else:
                # OLD workflow: scrape -> extract -> batch upload to airtable
                logger.info(f"Task {self.request.id}: Using legacy Airtable deduplication")
                workflow = chain(
                    scrape_date_range_task.s(start_date, end_date),
                    extract_instruments_task.s(),
                    batch_and_upload_task.s(job_id)
                )
        
        # Execute the workflow asynchronously
        workflow.apply_async()
        
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


def _process_scrape_job_single_DEPRECATED(job_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Process a single scraping job using distributed Celery tasks
    
    This creates a workflow: scrape -> extract -> upload (batched)
    Each step runs on its specialized worker queue
    
    Args:
        job_id: Job ID for tracking
        start_date: Start date
        end_date: End date
        
    Returns:
        Job results
    """
    try:
        # Step 1: Dispatch scraping task to scraping queue
        logger.info(f"Job {job_id}: Dispatching scraping task...")
        job_manager.update_job(job_id, progress=10)
        
        scrape_result = scrape_date_range_task.apply_async(
            args=[start_date, end_date],
            queue='scraping'
        )
        
        # Wait for scraping to complete
        response_data = scrape_result.get(timeout=300)  # 5 min timeout
        
        if not response_data:
            raise Exception("Failed to scrape data")
        
        job_manager.update_job(job_id, progress=30)
        
        # Step 2: Dispatch extraction task to extraction queue
        logger.info(f"Job {job_id}: Dispatching extraction task...")
        html_content = response_data.get('body', '')
        
        if not html_content:
            logger.warning(f"Job {job_id}: No HTML content")
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)
            return {'total_extracted': 0, 'companies_created': 0, 'ratings_created': 0}
        
        extract_result = extract_instruments_task.apply_async(
            args=[html_content],
            queue='extraction'
        )
        
        # Wait for extraction to complete
        data_dicts = extract_result.get(timeout=120)  # 2 min timeout
        
        total_extracted = len(data_dicts)
        logger.info(f"Job {job_id}: Extracted {total_extracted} instruments")
        job_manager.update_job(job_id, total_extracted=total_extracted, progress=50)
        
        if not data_dicts:
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)
            return {'total_extracted': 0, 'companies_created': 0, 'ratings_created': 0}
        
        # Step 3: Dispatch upload tasks to uploading queue (batched)
        logger.info(f"Job {job_id}: Dispatching upload tasks...")
        batch_size = settings.AIRTABLE_BATCH_SIZE
        batches = [data_dicts[i:i + batch_size] for i in range(0, len(data_dicts), batch_size)]
        
        logger.info(f"Job {job_id}: Dispatching {len(batches)} upload batches")
        
        # Create upload tasks and wait for them
        upload_tasks = []
        for batch in batches:
            task = upload_batch_to_airtable_task.apply_async(
                args=[batch],
                queue='uploading'
            )
            upload_tasks.append(task)
        
        # Wait for all uploads and aggregate results
        total_companies = 0
        total_ratings = 0
        
        for i, task in enumerate(upload_tasks):
            companies_created, ratings_created = task.get(timeout=120)  # 2 min per batch
            total_companies += companies_created
            total_ratings += ratings_created
            
            # Update progress
            progress = 50 + int(((i + 1) / len(upload_tasks)) * 50)
            job_manager.update_job(job_id, progress=progress)
            logger.info(f"Job {job_id}: Batch {i+1}/{len(upload_tasks)} complete")
        
        logger.info(f"Job {job_id}: Upload complete - {total_companies} companies, {total_ratings} ratings")
        
        # Update job with final status
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            uploaded_to_airtable=total_extracted,
            companies_created=total_companies,
            ratings_created=total_ratings
        )
        
        return {
            'total_extracted': total_extracted,
            'companies_created': total_companies,
            'ratings_created': total_ratings
        }
        
    except Exception as e:
        error_msg = f"Job failed: {str(e)}"
        logger.error(f"Job {job_id}: {error_msg}")
        logger.error(traceback.format_exc())
        
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise


def _process_scrape_job_with_chunking_DEPRECATED(job_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Process a scraping job by splitting into chunks using distributed tasks
    
    Dispatches scraping and extraction tasks to specialized workers for each chunk,
    then aggregates and uploads results.
    
    Args:
        job_id: Job ID for tracking
        start_date: Start date
        end_date: End date
        
    Returns:
        Job results
    """
    try:
        # Split date range into chunks
        chunks = split_date_range(start_date, end_date, settings.MAX_DATE_CHUNK_DAYS)
        logger.info(f"Job {job_id}: Split into {len(chunks)} chunks")
        
        job_manager.update_job(job_id, progress=10)
        
        # Dispatch scraping tasks for all chunks in parallel
        scrape_tasks = []
        for chunk_start, chunk_end in chunks:
            task = scrape_date_range_task.apply_async(
                args=[chunk_start, chunk_end],
                queue='scraping'
            )
            scrape_tasks.append(task)
        
        logger.info(f"Job {job_id}: Dispatched {len(scrape_tasks)} scraping tasks")
        
        # Wait for all scraping to complete and dispatch extraction
        extraction_tasks = []
        for i, scrape_task in enumerate(scrape_tasks):
            response_data = scrape_task.get(timeout=300)  # 5 min timeout
            
            if response_data and response_data.get('body'):
                # Dispatch extraction for this chunk
                extract_task = extract_instruments_task.apply_async(
                    args=[response_data['body']],
                    queue='extraction'
                )
                extraction_tasks.append(extract_task)
            
            # Update progress (10-40% for scraping)
            progress = 10 + int(((i + 1) / len(scrape_tasks)) * 30)
            job_manager.update_job(job_id, progress=progress)
        
        # Wait for all extraction to complete
        all_instruments = []
        for i, extract_task in enumerate(extraction_tasks):
            extracted_data = extract_task.get(timeout=120)  # 2 min timeout
            all_instruments.extend(extracted_data)
            
            # Update progress (40-50% for extraction)
            progress = 40 + int(((i + 1) / len(extraction_tasks)) * 10)
            job_manager.update_job(job_id, progress=progress)
            logger.info(f"Job {job_id}: Extracted {len(extracted_data)} instruments from chunk {i+1}")
        
        total_extracted = len(all_instruments)
        logger.info(f"Job {job_id}: Extracted {total_extracted} instruments from all chunks")
        job_manager.update_job(job_id, total_extracted=total_extracted, progress=50)
        
        if not all_instruments:
            job_manager.update_job(job_id, status=JobStatus.COMPLETED, progress=100)
            return {'total_extracted': 0, 'companies_created': 0, 'ratings_created': 0}
        
        # Dispatch upload tasks in batches
        batch_size = settings.AIRTABLE_BATCH_SIZE
        batches = [all_instruments[i:i + batch_size] for i in range(0, len(all_instruments), batch_size)]
        
        logger.info(f"Job {job_id}: Dispatching {len(batches)} upload batches")
        
        upload_tasks = []
        for batch in batches:
            task = upload_batch_to_airtable_task.apply_async(
                args=[batch],
                queue='uploading'
            )
            upload_tasks.append(task)
        
        # Wait for all uploads and aggregate results
        total_companies = 0
        total_ratings = 0
        
        for i, upload_task in enumerate(upload_tasks):
            companies_created, ratings_created = upload_task.get(timeout=120)  # 2 min per batch
            total_companies += companies_created
            total_ratings += ratings_created
            
            # Update progress (50-100% for uploading)
            progress = 50 + int(((i + 1) / len(upload_tasks)) * 50)
            job_manager.update_job(job_id, progress=progress)
            logger.info(f"Job {job_id}: Upload batch {i+1}/{len(upload_tasks)} complete")
        
        logger.info(f"Job {job_id}: Complete - {total_companies} companies, {total_ratings} ratings")
        
        job_manager.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            uploaded_to_airtable=total_extracted,
            companies_created=total_companies,
            ratings_created=total_ratings
        )
        
        return {
            'total_extracted': total_extracted,
            'companies_created': total_companies,
            'ratings_created': total_ratings
        }
        
    except Exception as e:
        error_msg = f"Chunked job failed: {str(e)}"
        logger.error(f"Job {job_id}: {error_msg}")
        logger.error(traceback.format_exc())
        
        job_manager.update_job(job_id, status=JobStatus.FAILED)
        raise

