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
    
    def __init__(self, job_id: str, start_date: str, end_date: str, parent_job_id: Optional[str] = None):
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
        self.parent_job_id = parent_job_id  # ID of parent job if this is a sub-job
        self.sub_jobs: List[str] = []  # List of sub-job IDs if this is a parent job
        self.message: Optional[str] = None  # Optional message for job status
    
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
            "end_date": self.end_date,
            "parent_job_id": self.parent_job_id,
            "sub_jobs": self.sub_jobs,
            "message": self.message
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
        job.parent_job_id = data.get("parent_job_id")
        job.sub_jobs = data.get("sub_jobs", [])
        job.message = data.get("message")
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
    
    def create_job(self, start_date: str, end_date: str, parent_job_id: Optional[str] = None) -> Job:
        """
        Create a new job
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            parent_job_id: Optional parent job ID if this is a sub-job
            
        Returns:
            Created Job instance
        """
        job_id = str(uuid.uuid4())
        job = Job(job_id, start_date, end_date, parent_job_id)
        
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
        
        # If this is a sub-job, add it to parent's sub_jobs list
        if parent_job_id:
            self.add_sub_job(parent_job_id, job_id)
        
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
    
    def add_sub_job(self, parent_job_id: str, sub_job_id: str) -> None:
        """
        Add a sub-job ID to a parent job's sub_jobs list
        
        Args:
            parent_job_id: Parent job ID
            sub_job_id: Sub-job ID to add
        """
        parent_job = self.get_job(parent_job_id)
        if not parent_job:
            logger.warning(f"Parent job {parent_job_id} not found when adding sub-job {sub_job_id}")
            return
        
        if sub_job_id not in parent_job.sub_jobs:
            parent_job.sub_jobs.append(sub_job_id)
            parent_job.updated_at = datetime.now().isoformat()
            
            # Save back to storage
            redis_client = self._get_redis()
            if redis_client:
                try:
                    redis_client.setex(
                        self._get_job_key(parent_job_id),
                        7 * 24 * 60 * 60,
                        json.dumps(parent_job.to_dict())
                    )
                except Exception as e:
                    logger.error(f"Error adding sub-job to parent in Redis: {e}")
            else:
                self._jobs[parent_job_id] = parent_job
    
    def check_and_update_parent_completion(self, parent_job_id: str) -> bool:
        """
        Check if all sub-jobs of a parent are complete and update parent accordingly
        
        Args:
            parent_job_id: Parent job ID to check
            
        Returns:
            True if parent was updated to complete, False otherwise
        """
        parent_job = self.get_job(parent_job_id)
        if not parent_job:
            logger.warning(f"Parent job {parent_job_id} not found when checking completion")
            return False
        
        if not parent_job.sub_jobs:
            logger.debug(f"Parent job {parent_job_id} has no sub-jobs")
            return False
        
        # Get all sub-job statuses
        sub_jobs = []
        for sub_job_id in parent_job.sub_jobs:
            sub_job = self.get_job(sub_job_id)
            if sub_job:
                sub_jobs.append(sub_job)
            else:
                logger.warning(f"Sub-job {sub_job_id} not found for parent {parent_job_id}")
        
        if not sub_jobs:
            logger.warning(f"No sub-jobs found for parent {parent_job_id}")
            return False
        
        # Check if all sub-jobs are completed or failed
        all_completed = all(sj.status == JobStatus.COMPLETED for sj in sub_jobs)
        any_failed = any(sj.status == JobStatus.FAILED for sj in sub_jobs)
        
        if all_completed:
            # Aggregate statistics from all sub-jobs
            total_extracted = sum(sj.total_extracted for sj in sub_jobs)
            total_scraped = sum(sj.total_scraped for sj in sub_jobs)
            new_records = sum(sj.new_records for sj in sub_jobs)
            duplicate_records = sum(sj.duplicate_records_skipped for sj in sub_jobs)
            companies_created = sum(sj.companies_created for sj in sub_jobs)
            ratings_created = sum(sj.ratings_created for sj in sub_jobs)
            uploaded_to_airtable = sum(sj.uploaded_to_airtable for sj in sub_jobs)
            sync_failures = sum(sj.sync_failures for sj in sub_jobs)
            
            # Update parent job
            self.update_job(
                parent_job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                total_extracted=total_extracted,
                total_scraped=total_scraped,
                new_records=new_records,
                duplicate_records_skipped=duplicate_records,
                companies_created=companies_created,
                ratings_created=ratings_created,
                uploaded_to_airtable=uploaded_to_airtable,
                sync_failures=sync_failures,
                completed_at=datetime.now().isoformat(),
                message=f"All {len(sub_jobs)} sub-jobs completed successfully"
            )
            
            logger.info(
                f"Parent job {parent_job_id} completed: "
                f"{companies_created} companies, {ratings_created} ratings "
                f"across {len(sub_jobs)} sub-jobs"
            )
            return True
        
        elif any_failed:
            # Some sub-jobs failed - mark parent as partially failed
            completed_count = sum(1 for sj in sub_jobs if sj.status == JobStatus.COMPLETED)
            failed_count = sum(1 for sj in sub_jobs if sj.status == JobStatus.FAILED)
            
            self.update_job(
                parent_job_id,
                status=JobStatus.FAILED,
                message=f"{completed_count}/{len(sub_jobs)} sub-jobs completed, {failed_count} failed"
            )
            
            logger.warning(
                f"Parent job {parent_job_id} has failures: "
                f"{completed_count} completed, {failed_count} failed"
            )
            return True
        
        else:
            # Still running - update progress
            avg_progress = sum(sj.progress for sj in sub_jobs) // len(sub_jobs)
            completed_count = sum(1 for sj in sub_jobs if sj.status == JobStatus.COMPLETED)
            
            self.update_job(
                parent_job_id,
                progress=avg_progress,
                message=f"{completed_count}/{len(sub_jobs)} sub-jobs completed"
            )
            
            logger.debug(f"Parent job {parent_job_id} progress: {avg_progress}%")
            return False


# Global job manager instance
job_manager = JobManager()

