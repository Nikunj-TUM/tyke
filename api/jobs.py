"""
Job management system with Redis-backed storage for distributed access
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
import redis
from .models import JobStatus, JobError
from .config import settings
import logging

logger = logging.getLogger(__name__)


class Job:
    """Job data structure"""
    
    def __init__(self, job_id: str, start_date: str, end_date: str):
        self.job_id = job_id
        self.status = JobStatus.QUEUED
        self.progress = 0
        self.total_extracted = 0
        self.uploaded_to_airtable = 0
        self.companies_created = 0
        self.ratings_created = 0
        self.total_scraped = 0
        self.new_records = 0
        self.duplicate_records_skipped = 0
        self.sync_failures = 0
        self.errors: List[JobError] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.start_date = start_date
        self.end_date = end_date
    
    def update_status(self, status: JobStatus) -> None:
        """Update job status"""
        self.status = status
        self.updated_at = datetime.now().isoformat()
        if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            self.completed_at = datetime.now().isoformat()
    
    def update_progress(self, progress: int) -> None:
        """Update progress percentage"""
        self.progress = min(100, max(0, progress))
        self.updated_at = datetime.now().isoformat()
    
    def add_error(self, error: str, traceback: Optional[str] = None) -> None:
        """Add an error to the job"""
        self.errors.append(JobError(
            timestamp=datetime.now().isoformat(),
            error=error,
            traceback=traceback
        ))
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Convert job to dictionary"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "total_extracted": self.total_extracted,
            "uploaded_to_airtable": self.uploaded_to_airtable,
            "companies_created": self.companies_created,
            "ratings_created": self.ratings_created,
            "total_scraped": self.total_scraped,
            "new_records": self.new_records,
            "duplicate_records_skipped": self.duplicate_records_skipped,
            "sync_failures": self.sync_failures,
            "errors": [error.model_dump() for error in self.errors],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "start_date": self.start_date,
            "end_date": self.end_date
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create Job instance from dictionary"""
        job = cls.__new__(cls)
        job.job_id = data["job_id"]
        job.status = data["status"]
        job.progress = data["progress"]
        job.total_extracted = data.get("total_extracted", 0)
        job.uploaded_to_airtable = data.get("uploaded_to_airtable", 0)
        job.companies_created = data.get("companies_created", 0)
        job.ratings_created = data.get("ratings_created", 0)
        job.total_scraped = data.get("total_scraped", 0)
        job.new_records = data.get("new_records", 0)
        job.duplicate_records_skipped = data.get("duplicate_records_skipped", 0)
        job.sync_failures = data.get("sync_failures", 0)
        job.errors = [JobError(**err) for err in data.get("errors", [])]
        job.created_at = data["created_at"]
        job.updated_at = data["updated_at"]
        job.completed_at = data.get("completed_at")
        job.start_date = data["start_date"]
        job.end_date = data["end_date"]
        return job


class JobManager:
    """Redis-backed job management system for distributed access"""
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        self._use_redis = settings.USE_CELERY
    
    def _get_redis(self) -> redis.Redis:
        """Get or create Redis client"""
        if not self._use_redis:
            # Fallback to in-memory storage when Celery is disabled
            if not hasattr(self, '_jobs'):
                self._jobs: Dict[str, Job] = {}
            return None
        
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                # Test connection
                self._redis_client.ping()
                logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory storage.")
                self._use_redis = False
                self._jobs: Dict[str, Job] = {}
                return None
        return self._redis_client
    
    def _get_job_key(self, job_id: str) -> str:
        """Get Redis key for job"""
        return f"job:{job_id}"
    
    def create_job(self, start_date: str, end_date: str) -> Job:
        """Create a new job"""
        job_id = str(uuid.uuid4())
        job = Job(job_id, start_date, end_date)
        
        redis_client = self._get_redis()
        if redis_client:
            try:
                # Store in Redis with 7-day expiration
                redis_client.setex(
                    self._get_job_key(job_id),
                    7 * 24 * 60 * 60,  # 7 days
                    json.dumps(job.to_dict())
                )
                # Add to sorted set for listing (score = timestamp)
                redis_client.zadd('jobs:sorted', {job_id: datetime.now().timestamp()})
            except Exception as e:
                logger.error(f"Error storing job in Redis: {e}")
        else:
            # Fallback to in-memory
            self._jobs[job_id] = job
        
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        redis_client = self._get_redis()
        if redis_client:
            try:
                job_data = redis_client.get(self._get_job_key(job_id))
                if job_data:
                    return Job.from_dict(json.loads(job_data))
            except Exception as e:
                logger.error(f"Error retrieving job from Redis: {e}")
                return None
        else:
            # Fallback to in-memory
            return self._jobs.get(job_id)
        
        return None
    
    def update_job(self, job_id: str, **kwargs) -> None:
        """Update job attributes"""
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found for update")
            return
        
        # Update job attributes
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        job.updated_at = datetime.now().isoformat()
        
        # Save back to storage
        redis_client = self._get_redis()
        if redis_client:
            try:
                redis_client.setex(
                    self._get_job_key(job_id),
                    7 * 24 * 60 * 60,
                    json.dumps(job.to_dict())
                )
            except Exception as e:
                logger.error(f"Error updating job in Redis: {e}")
        else:
            # In-memory update already done
            self._jobs[job_id] = job
    
    def list_jobs(self, limit: int = 100) -> List[Job]:
        """List all jobs"""
        redis_client = self._get_redis()
        if redis_client:
            try:
                # Get job IDs from sorted set (most recent first)
                job_ids = redis_client.zrevrange('jobs:sorted', 0, limit - 1)
                jobs = []
                for job_id in job_ids:
                    job = self.get_job(job_id)
                    if job:
                        jobs.append(job)
                return jobs
            except Exception as e:
                logger.error(f"Error listing jobs from Redis: {e}")
                return []
        else:
            # Fallback to in-memory
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            return jobs[:limit]


# Global job manager instance
job_manager = JobManager()

