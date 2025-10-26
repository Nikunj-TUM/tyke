"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeRequest(BaseModel):
    """Request model for scraping endpoint"""
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date format is YYYY-MM-DD"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f"Invalid date format: {v}. Expected format: YYYY-MM-DD")
    
    def validate_date_range(self, max_days: int = 90) -> None:
        """Validate date range is not too large"""
        start = datetime.strptime(self.start_date, '%Y-%m-%d')
        end = datetime.strptime(self.end_date, '%Y-%m-%d')
        
        if start > end:
            raise ValueError("start_date must be before or equal to end_date")
        
        delta = (end - start).days
        if delta > max_days:
            raise ValueError(f"Date range cannot exceed {max_days} days. Requested: {delta} days")


class ScrapeResponse(BaseModel):
    """Response model for scraping endpoint"""
    job_id: str
    status: JobStatus
    message: str
    created_at: str


class JobError(BaseModel):
    """Error information"""
    timestamp: str
    error: str
    traceback: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response model for job status endpoint"""
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100, description="Progress percentage")
    total_extracted: int = 0
    uploaded_to_airtable: int = 0
    companies_created: int = 0
    ratings_created: int = 0
    total_scraped: int = 0
    new_records: int = 0
    duplicate_records_skipped: int = 0
    sync_failures: int = 0
    errors: List[JobError] = []
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    timestamp: str
    environment: str

