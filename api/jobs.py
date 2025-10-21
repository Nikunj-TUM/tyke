"""
Background job management system with in-memory storage
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from .models import JobStatus, JobError


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
            "errors": [error.model_dump() for error in self.errors],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "start_date": self.start_date,
            "end_date": self.end_date
        }


class JobManager:
    """In-memory job management system"""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
    
    def create_job(self, start_date: str, end_date: str) -> Job:
        """Create a new job"""
        job_id = str(uuid.uuid4())
        job = Job(job_id, start_date, end_date)
        self._jobs[job_id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID"""
        return self._jobs.get(job_id)
    
    async def update_job(self, job_id: str, **kwargs) -> None:
        """Update job attributes"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                job.updated_at = datetime.now().isoformat()
    
    def list_jobs(self, limit: int = 100) -> List[Job]:
        """List all jobs"""
        jobs = list(self._jobs.values())
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs[:limit]


# Global job manager instance
job_manager = JobManager()

