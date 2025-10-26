"""
FastAPI application for Infomerics scraper API
"""
import logging
import asyncio
import traceback
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .models import (
    ScrapeRequest,
    ScrapeResponse,
    JobStatusResponse,
    HealthResponse,
    JobStatus
)
from .auth import verify_api_key
from .jobs import job_manager, Job
from .airtable_client import AirtableClient
from .scraper_service import ScraperService

# Import Celery tasks if enabled
if settings.USE_CELERY:
    from .tasks import process_scrape_job_orchestrator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    logger.info("Starting Infomerics Scraper API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize PostgreSQL database if enabled
    if settings.USE_POSTGRES_DEDUPLICATION:
        try:
            from .database import init_database, close_connection_pool
            logger.info("Initializing PostgreSQL database...")
            init_database()
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            logger.warning("Continuing without PostgreSQL deduplication")
    
    yield
    
    # Cleanup on shutdown
    if settings.USE_POSTGRES_DEDUPLICATION:
        try:
            from .database import close_connection_pool
            close_connection_pool()
        except Exception as e:
            logger.error(f"Error closing PostgreSQL connection pool: {e}")
    
    logger.info("Shutting down Infomerics Scraper API")


# Create FastAPI app
app = FastAPI(
    title="Infomerics Scraper API",
    description="API for scraping Infomerics press releases and storing in Airtable",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def process_scrape_job(job: Job) -> None:
    """
    Background task to process a scraping job
    
    Args:
        job: Job object to process
    """
    try:
        logger.info(f"Starting job {job.job_id}: {job.start_date} to {job.end_date}")
        
        # Update job status to running
        job.update_status(JobStatus.RUNNING)
        job.update_progress(5)
        
        # Initialize services
        scraper_service = ScraperService()
        airtable_client = AirtableClient()
        
        # Step 1: Scrape and extract data (50% of progress)
        logger.info(f"Job {job.job_id}: Scraping and extracting data...")
        extracted_data = await scraper_service.scrape_and_extract(
            job.start_date,
            job.end_date
        )
        
        if extracted_data is None:
            raise Exception("Failed to scrape and extract data")
        
        if not extracted_data:
            logger.warning(f"Job {job.job_id}: No data extracted")
            job.total_extracted = 0
            job.update_progress(100)
            job.update_status(JobStatus.COMPLETED)
            return
        
        job.total_extracted = len(extracted_data)
        job.update_progress(50)
        logger.info(f"Job {job.job_id}: Extracted {len(extracted_data)} instruments")
        
        # Step 2: Upload to Airtable in batches (50% of remaining progress)
        logger.info(f"Job {job.job_id}: Uploading to Airtable...")
        batch_size = settings.AIRTABLE_BATCH_SIZE
        total_batches = (len(extracted_data) + batch_size - 1) // batch_size
        
        total_companies_created = 0
        total_ratings_created = 0
        
        for i in range(0, len(extracted_data), batch_size):
            batch = extracted_data[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            logger.info(f"Job {job.job_id}: Processing batch {batch_num}/{total_batches}")
            
            try:
                companies_created, ratings_created = airtable_client.batch_create_ratings(batch)
                total_companies_created += companies_created
                total_ratings_created += ratings_created
                
                # Update progress
                progress = 50 + int((batch_num / total_batches) * 50)
                job.update_progress(progress)
                job.uploaded_to_airtable = i + len(batch)
                job.companies_created = total_companies_created
                job.ratings_created = total_ratings_created
                
            except Exception as e:
                error_msg = f"Error processing batch {batch_num}: {str(e)}"
                logger.error(f"Job {job.job_id}: {error_msg}")
                job.add_error(error_msg, traceback.format_exc())
                # Continue with next batch
        
        # Mark job as completed
        job.update_progress(100)
        job.update_status(JobStatus.COMPLETED)
        
        logger.info(f"Job {job.job_id} completed successfully")
        logger.info(f"  - Total extracted: {job.total_extracted}")
        logger.info(f"  - Companies created: {job.companies_created}")
        logger.info(f"  - Ratings created: {job.ratings_created}")
        logger.info(f"  - Errors: {len(job.errors)}")
        
    except Exception as e:
        error_msg = f"Job failed: {str(e)}"
        logger.error(f"Job {job.job_id}: {error_msg}")
        logger.error(traceback.format_exc())
        
        job.add_error(error_msg, traceback.format_exc())
        job.update_status(JobStatus.FAILED)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint (no authentication required)
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        environment=settings.ENVIRONMENT
    )


@app.post("/infomerics/scrape", response_model=ScrapeResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second")
async def scrape_infomerics(
    request: Request,
    scrape_request: ScrapeRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Start a scraping job for the given date range
    
    Args:
        request: HTTP request object (required for rate limiting)
        scrape_request: Scrape request with start_date and end_date
        api_key: API key for authentication
        
    Returns:
        Response with job_id and status
    """
    try:
        # Validate date range
        scrape_request.validate_date_range(settings.MAX_DATE_RANGE_DAYS)
        
        # Create a new job
        job = job_manager.create_job(scrape_request.start_date, scrape_request.end_date)
        
        logger.info(f"Created job {job.job_id} for date range {scrape_request.start_date} to {scrape_request.end_date}")
        
        # Dispatch task based on configuration
        if settings.USE_CELERY:
            # Use Celery for distributed task processing
            logger.info(f"Dispatching Celery task for job {job.job_id}")
            process_scrape_job_orchestrator.apply_async(
                args=[job.job_id, scrape_request.start_date, scrape_request.end_date],
                task_id=job.job_id
            )
        else:
            # Fallback to asyncio background task
            logger.info(f"Using asyncio for job {job.job_id}")
            asyncio.create_task(process_scrape_job(job))
        
        return ScrapeResponse(
            job_id=job.job_id,
            status=JobStatus.QUEUED,
            message=f"Scraping job queued for {scrape_request.start_date} to {scrape_request.end_date}",
            created_at=job.created_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating scrape job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scraping job: {str(e)}"
        )


@app.get("/infomerics/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get the status of a scraping job
    
    Args:
        job_id: UUID of the job
        api_key: API key for authentication
        
    Returns:
        Job status and details
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return JobStatusResponse(**job.to_dict())


@app.get("/infomerics/jobs", response_model=Dict[str, list])
async def list_jobs(
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """
    List all jobs (for debugging/monitoring)
    
    Args:
        limit: Maximum number of jobs to return
        api_key: API key for authentication
        
    Returns:
        List of jobs
    """
    jobs = job_manager.list_jobs(limit)
    return {
        "jobs": [job.to_dict() for job in jobs]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

