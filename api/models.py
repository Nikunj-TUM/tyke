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
    airtable_record_id: Optional[str] = Field(None, description="Airtable record ID in Infomerics Scraper table")
    
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
    parent_job_id: Optional[str] = None
    sub_jobs: List[str] = []
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    timestamp: str
    environment: str


class ContactAddress(BaseModel):
    """Model for contact address information"""
    line1: Optional[str] = None
    line2: Optional[str] = None
    line3: Optional[str] = None
    line4: Optional[str] = None
    locality: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    fullAddress: Optional[str] = None


class ContactInfo(BaseModel):
    """Model for individual contact data"""
    indexId: Optional[str] = Field(None, description="DIN number of the director")
    fullName: str = Field(..., description="Full name of the director")
    mobileNumber: Optional[str] = Field(None, description="Mobile number")
    emailAddress: Optional[str] = Field(None, description="Email address")
    addresses: List[ContactAddress] = Field(default_factory=list, description="List of addresses")


class ContactFetchRequest(BaseModel):
    """Request model for fetching contacts from Attestr API"""
    cin: str = Field(..., description="Company Identification Number (CIN)")
    company_airtable_id: str = Field(..., description="Airtable record ID of the company")
    max_contacts: Optional[int] = Field(None, description="Maximum number of contacts to fetch (1-100)")
    force_refresh: bool = Field(False, description="Force refresh from Attestr API even if contacts exist in database")
    
    @field_validator('cin')
    @classmethod
    def validate_cin(cls, v: str) -> str:
        """Validate CIN format"""
        if not v or len(v.strip()) == 0:
            raise ValueError("CIN cannot be empty")
        return v.strip()
    
    @field_validator('max_contacts')
    @classmethod
    def validate_max_contacts(cls, v: Optional[int]) -> Optional[int]:
        """Validate max_contacts is within range"""
        if v is not None:
            if v < 1 or v > 100:
                raise ValueError("max_contacts must be between 1 and 100")
        return v


class ContactFetchResponse(BaseModel):
    """Response model for contact fetch endpoint"""
    success: bool
    message: str
    cin: str
    business_name: Optional[str] = None
    total_contacts_fetched: int = 0
    new_contacts: int = 0
    updated_contacts: int = 0
    synced_to_airtable: int = 0
    failed_syncs: int = 0
    contacts: List[ContactInfo] = Field(default_factory=list)


# WhatsApp Service Models

class WhatsAppConnectionStatus(BaseModel):
    """Response model for WhatsApp connection status"""
    connected: bool = Field(..., description="Whether WhatsApp is connected and ready")
    qr_pending: bool = Field(False, description="Whether a QR code is pending scan")
    qr_code: Optional[str] = Field(None, description="QR code text (if pending)")
    qr_image: Optional[str] = Field(None, description="QR code as data URL image")
    client_info: Optional[dict] = Field(None, description="Connected WhatsApp client info")
    error: Optional[str] = Field(None, description="Error message if any")
    rabbitmq_connected: bool = Field(True, description="Whether RabbitMQ connection is active")
    queue_stats: Optional[dict] = Field(None, description="Message queue statistics")


class WhatsAppSendMessageRequest(BaseModel):
    """Request model for sending a single WhatsApp message"""
    phone_number: str = Field(..., description="Phone number with country code (e.g., +919876543210 or 919876543210)")
    message: str = Field(..., description="Message text to send")
    contact_name: Optional[str] = Field(None, description="Optional contact name for logging")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate and format phone number"""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, v))
        
        if len(cleaned) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        
        return cleaned
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message is not empty"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Message cannot be empty")
        
        if len(v) > 4096:
            raise ValueError("Message cannot exceed 4096 characters")
        
        return v.strip()


class WhatsAppBulkContact(BaseModel):
    """Model for a single contact in bulk send"""
    phone_number: str = Field(..., description="Phone number with country code")
    message: str = Field(..., description="Message text to send")
    name: Optional[str] = Field(None, description="Contact name")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate and format phone number"""
        cleaned = ''.join(filter(str.isdigit, v))
        
        if len(cleaned) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        
        return cleaned


class WhatsAppBulkSendRequest(BaseModel):
    """Request model for sending bulk WhatsApp messages"""
    contacts: List[WhatsAppBulkContact] = Field(..., description="List of contacts with messages")
    
    @field_validator('contacts')
    @classmethod
    def validate_contacts(cls, v: List[WhatsAppBulkContact]) -> List[WhatsAppBulkContact]:
        """Validate contacts list"""
        if not v or len(v) == 0:
            raise ValueError("Contacts list cannot be empty")
        
        if len(v) > 100:
            raise ValueError("Cannot send more than 100 messages in one request")
        
        return v


class WhatsAppMessageResult(BaseModel):
    """Result for a single queued message"""
    message_id: str
    phone_number: str
    contact_name: Optional[str] = None


class WhatsAppSendResponse(BaseModel):
    """Response model for WhatsApp send message endpoint"""
    success: bool
    message: str
    message_id: Optional[str] = Field(None, description="Message ID for tracking")
    status: str = Field("queued", description="Message status (queued, sent, failed)")
    phone_number: Optional[str] = None
    contact_name: Optional[str] = None
    error: Optional[str] = Field(None, description="Error message if failed")


class WhatsAppBulkSendResponse(BaseModel):
    """Response model for bulk WhatsApp send endpoint"""
    success: bool
    message: str
    total: int = Field(..., description="Total messages in request")
    queued: int = Field(0, description="Successfully queued messages")
    failed: int = Field(0, description="Failed to queue messages")
    message_ids: List[WhatsAppMessageResult] = Field(default_factory=list, description="List of queued message IDs")
    errors: List[dict] = Field(default_factory=list, description="List of errors for failed messages")

