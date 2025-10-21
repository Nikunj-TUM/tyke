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
    COMPANIES_TABLE_ID: str = "tblMsZnCUfG783lWI"
    CREDIT_RATINGS_TABLE_ID: str = "tblRlxbOYMW8Rag7f"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 50
    RATE_LIMIT_PERIOD: int = 3600  # 1 hour in seconds
    
    # Job Configuration
    MAX_DATE_RANGE_DAYS: int = 90
    AIRTABLE_BATCH_SIZE: int = 10
    
    # CORS Configuration
    CORS_ORIGINS: str = "*"  # Configure for production (comma-separated or "*")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

