"""
Celery application configuration for distributed task processing
"""
import logging
from celery import Celery
from kombu import Exchange, Queue

from .config import settings

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "infomerics_scraper",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['api.tasks']
)

# Celery Configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    
    # Result backend settings
    result_expires=settings.CELERY_RESULT_EXPIRES,
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Worker settings
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Define task queues with routing
celery_app.conf.task_queues = (
    Queue('celery', Exchange('celery'), routing_key='celery'),
    Queue('scraping', Exchange('scraping'), routing_key='scraping'),
    Queue('extraction', Exchange('extraction'), routing_key='extraction'),
    Queue('uploading', Exchange('uploading'), routing_key='uploading'),
)

# Task routing rules
celery_app.conf.task_routes = {
    'api.tasks.scrape_date_range_task': {'queue': 'scraping'},
    'api.tasks.extract_instruments_task': {'queue': 'extraction'},
    'api.tasks.upload_batch_to_airtable_task': {'queue': 'uploading'},
    'api.tasks.batch_and_upload_task': {'queue': 'celery'},
    'api.tasks.aggregate_upload_results': {'queue': 'celery'},
    'api.tasks.process_scrape_results_task': {'queue': 'celery'},
    'api.tasks.process_scrape_job_orchestrator': {'queue': 'celery'},
}

# Task annotations for rate limiting and retries
celery_app.conf.task_annotations = {
    'api.tasks.upload_batch_to_airtable_task': {
        'rate_limit': '5/s',  # Max 5 concurrent Airtable uploads per second
        'max_retries': 3,
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True,
    },
    'api.tasks.scrape_date_range_task': {
        'max_retries': 3,
        'retry_backoff': True,
        'retry_backoff_max': 300,
    },
}

logger.info(f"Celery app configured with broker: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
logger.info(f"Result backend: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

