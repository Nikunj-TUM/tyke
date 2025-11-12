"""
Configuration management for the Infomerics Scraper API
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_KEY: str = "your-api-key-here"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Airtable Configuration
    AIRTABLE_API_KEY: str
    AIRTABLE_BASE_ID: str = "appYourBaseId"  # Will be set from env
    
    # Airtable Table IDs (from schema)
    # These can be overridden via environment variables if your schema changes
    COMPANIES_TABLE_ID: str = os.getenv("COMPANIES_TABLE_ID", "tblMsZnCUfG783lWI")
    CREDIT_RATINGS_TABLE_ID: str = os.getenv("CREDIT_RATINGS_TABLE_ID", "tblRlxbOYMW8Rag7f")
    INFOMERICS_SCRAPER_TABLE_ID: str = os.getenv("INFOMERICS_SCRAPER_TABLE_ID", "tbliVxZjw5Uzpfxc5")
    CONTACTS_TABLE_ID: str = os.getenv("CONTACTS_TABLE_ID", "tbljbYRWsRBb85X5y")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 50
    RATE_LIMIT_PERIOD: int = 3600  # 1 hour in seconds
    
    # Job Configuration
    MAX_DATE_RANGE_DAYS: int = 90
    AIRTABLE_BATCH_SIZE: int = 10
    
    # Airtable Batching Configuration
    COMPANY_BATCH_SIZE: int = 10  # Airtable batch limit
    RATING_BATCH_SIZE: int = 10   # Airtable batch limit
    AIRTABLE_MAX_RETRIES: int = 3
    AIRTABLE_RETRY_BACKOFF: int = 2  # Exponential backoff base
    
    # CORS Configuration
    CORS_ORIGINS: str = "*"  # Configure for production (comma-separated or "*")
    
    # RabbitMQ Configuration
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")
    
    # Redis Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "infomerics")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "infomerics_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "change_this_password")
    
    # Celery Configuration
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 hour max per task
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3000  # 50 min warning
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 4
    CELERY_RESULT_EXPIRES: int = 86400  # 24 hours
    
    # Worker Pools
    SCRAPER_WORKER_CONCURRENCY: int = 5
    UPLOAD_WORKER_CONCURRENCY: int = 10
    MAX_DATE_CHUNK_DAYS: int = 30
    
    # Attestr API Configuration
    ATTESTR_API_KEY: str = ""
    ATTESTR_API_URL: str = "https://api.attestr.com/api/v2/public/leadx/mca-cin-contact"
    ATTESTR_MAX_CONTACTS: int = 100  # Default max contacts to fetch
    
    # Bright Data Web Unlocker Configuration
    USE_BRIGHT_DATA: bool = False  # Toggle between Bright Data API and direct requests
    BRIGHT_DATA_API_KEY: str = ""  # Required when USE_BRIGHT_DATA=True
    BRIGHT_DATA_ZONE: str = "web_unlocker1"  # Zone identifier from Bright Data dashboard
    BRIGHT_DATA_MAX_RETRIES: int = 3  # Maximum retry attempts on failure
    BRIGHT_DATA_RETRY_BACKOFF: int = 2  # Exponential backoff base in seconds
    
    # Feature Flags
    USE_CELERY: bool = True
    USE_POSTGRES_DEDUPLICATION: bool = True
    
    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def celery_broker_url(self) -> str:
        """Construct Celery broker URL"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
    
    @property
    def celery_result_backend(self) -> str:
        """Construct Celery result backend URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

