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
    JobStatus,
    ContactFetchRequest,
    ContactFetchResponse,
    WhatsAppConnectionStatus,
    WhatsAppSendMessageRequest,
    WhatsAppSendResponse,
    WhatsAppBulkSendRequest,
    WhatsAppBulkSendResponse
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
            
            # Update Airtable status to "Done"
            if job.airtable_record_id:
                try:
                    airtable_client.update_scraper_status(job.airtable_record_id, "Done")
                    logger.info(f"Updated Airtable record {job.airtable_record_id} to 'Done'")
                except Exception as e:
                    logger.warning(f"Failed to update Airtable status to 'Done': {str(e)}")
            
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
        
        # Update Airtable status to "Done"
        if job.airtable_record_id:
            try:
                airtable_client.update_scraper_status(job.airtable_record_id, "Done")
                logger.info(f"Updated Airtable record {job.airtable_record_id} to 'Done'")
            except Exception as e:
                logger.warning(f"Failed to update Airtable status to 'Done': {str(e)}")
        
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
        
        # Update Airtable status to "Error"
        if job.airtable_record_id:
            try:
                airtable_client = AirtableClient()
                airtable_client.update_scraper_status(job.airtable_record_id, "Error")
                logger.info(f"Updated Airtable record {job.airtable_record_id} to 'Error'")
            except Exception as ae:
                logger.warning(f"Failed to update Airtable status to 'Error': {str(ae)}")


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
        
        # Update Airtable status to "In progress" if record_id is provided
        if scrape_request.airtable_record_id:
            try:
                airtable_client = AirtableClient()
                airtable_client.update_scraper_status(
                    scrape_request.airtable_record_id,
                    "In progress"
                )
                logger.info(f"Updated Airtable record {scrape_request.airtable_record_id} to 'In progress'")
            except Exception as e:
                logger.warning(f"Failed to update Airtable status to 'In progress': {str(e)}")
        
        # Create a new job
        job = job_manager.create_job(
            scrape_request.start_date,
            scrape_request.end_date,
            airtable_record_id=scrape_request.airtable_record_id
        )
        
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


@app.post("/contacts/fetch", response_model=ContactFetchResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second")
async def fetch_contacts(
    request: Request,
    contact_request: ContactFetchRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Fetch director contacts from Attestr API and sync to Airtable
    
    Args:
        request: HTTP request object (required for rate limiting)
        contact_request: Request with CIN and company Airtable ID
        api_key: API key for authentication
        
    Returns:
        Response with contact fetch results
    """
    try:
        from .services.contact_service import ContactService
        
        logger.info(f"Fetching contacts for CIN: {contact_request.cin}, Company: {contact_request.company_airtable_id}")
        
        # Initialize contact service
        contact_service = ContactService()
        
        # Fetch and store contacts
        result = contact_service.fetch_and_store_contacts(
            cin=contact_request.cin,
            company_airtable_id=contact_request.company_airtable_id,
            max_contacts=contact_request.max_contacts,
            force_refresh=contact_request.force_refresh
        )
        
        return ContactFetchResponse(**result)
        
    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch contacts: {str(e)}"
        )


# ============================================================================
# WhatsApp Endpoints
# ============================================================================

@app.get("/whatsapp/status", response_model=WhatsAppConnectionStatus)
async def get_whatsapp_status(
    api_key: str = Depends(verify_api_key)
):
    """
    Get WhatsApp connection status
    
    Returns the current WhatsApp connection status including:
    - Whether WhatsApp is connected and ready
    - QR code if authentication is pending
    - Client information if connected
    - Queue statistics
    
    Args:
        api_key: API key for authentication
        
    Returns:
        WhatsApp connection status
    """
    try:
        import requests
        from .services.whatsapp_service import WhatsAppService
        
        # Try to get status from Node.js service
        try:
            response = requests.get(
                "http://whatsapp-service:3000/status",
                timeout=5
            )
            node_status = response.json()
        except Exception as e:
            logger.warning(f"Could not reach WhatsApp service: {e}")
            node_status = {
                'connected': False,
                'error': f"WhatsApp service unreachable: {str(e)}"
            }
        
        # Get RabbitMQ and queue statistics
        whatsapp_service = WhatsAppService()
        rabbitmq_status = whatsapp_service.get_connection_status()
        queue_stats = whatsapp_service.get_queue_stats()
        whatsapp_service.close()
        
        # Try to get QR code if available
        qr_code = None
        qr_image = None
        if not node_status.get('connected') and node_status.get('qr_pending'):
            try:
                qr_response = requests.get(
                    "http://whatsapp-service:3000/qr",
                    timeout=5
                )
                qr_data = qr_response.json()
                qr_code = qr_data.get('qr_code')
                qr_image = qr_data.get('qr_image')
            except:
                pass
        
        return WhatsAppConnectionStatus(
            connected=node_status.get('connected', False),
            qr_pending=node_status.get('qr_pending', False),
            qr_code=qr_code,
            qr_image=qr_image,
            client_info=node_status.get('client_info'),
            error=node_status.get('error'),
            rabbitmq_connected=rabbitmq_status.get('rabbitmq_connected', False),
            queue_stats=queue_stats
        )
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get WhatsApp status: {str(e)}"
        )


@app.post("/whatsapp/send", response_model=WhatsAppSendResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second")
async def send_whatsapp_message(
    request: Request,
    message_request: WhatsAppSendMessageRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Send a single WhatsApp message
    
    Queues a message to be sent via WhatsApp. The message is processed
    asynchronously by the Node.js WhatsApp service.
    
    Args:
        request: HTTP request object (required for rate limiting)
        message_request: Message details (phone number, message text)
        api_key: API key for authentication
        
    Returns:
        Response with message ID and status
    """
    try:
        from .services.whatsapp_service import WhatsAppService
        
        logger.info(
            f"Sending WhatsApp message to {message_request.contact_name or message_request.phone_number}"
        )
        
        # Initialize WhatsApp service
        whatsapp_service = WhatsAppService()
        
        # Queue the message
        result = whatsapp_service.send_message(
            phone_number=message_request.phone_number,
            message=message_request.message,
            contact_name=message_request.contact_name
        )
        
        whatsapp_service.close()
        
        if result.get('success'):
            return WhatsAppSendResponse(
                success=True,
                message="Message queued successfully",
                message_id=result['message_id'],
                status="queued",
                phone_number=result['phone_number'],
                contact_name=result.get('contact_name')
            )
        else:
            return WhatsAppSendResponse(
                success=False,
                message="Failed to queue message",
                error=result.get('error'),
                phone_number=message_request.phone_number,
                contact_name=message_request.contact_name,
                status="failed"
            )
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send WhatsApp message: {str(e)}"
        )


@app.post("/whatsapp/send/bulk", response_model=WhatsAppBulkSendResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second")
async def send_bulk_whatsapp_messages(
    request: Request,
    bulk_request: WhatsAppBulkSendRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Send multiple WhatsApp messages in bulk
    
    Queues multiple messages to be sent via WhatsApp. Messages are processed
    asynchronously by the Node.js WhatsApp service with rate limiting.
    
    Args:
        request: HTTP request object (required for rate limiting)
        bulk_request: List of contacts with messages
        api_key: API key for authentication
        
    Returns:
        Response with statistics and message IDs
    """
    try:
        from .services.whatsapp_service import WhatsAppService
        
        logger.info(f"Sending bulk WhatsApp messages to {len(bulk_request.contacts)} contacts")
        
        # Initialize WhatsApp service
        whatsapp_service = WhatsAppService()
        
        # Convert request to format expected by service
        contacts = [
            {
                'phone_number': contact.phone_number,
                'message': contact.message,
                'name': contact.name
            }
            for contact in bulk_request.contacts
        ]
        
        # Queue all messages
        result = whatsapp_service.send_bulk_messages(contacts)
        
        whatsapp_service.close()
        
        return WhatsAppBulkSendResponse(
            success=result['success'] > 0,
            message=f"Queued {result['success']} messages, {result['failed']} failed",
            total=result['total'],
            queued=result['success'],
            failed=result['failed'],
            message_ids=result.get('message_ids', []),
            errors=result.get('errors', [])
        )
        
    except Exception as e:
        logger.error(f"Error sending bulk WhatsApp messages: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send bulk WhatsApp messages: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    import os
    
    # Allow host and port to be configured via environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)

