"""
Service layer for business logic

This module contains service classes that encapsulate business logic
and coordinate between database and external APIs (Airtable).
"""
from .company_service import CompanyService
from .rating_service import RatingService
from .scrape_processing_service import ScrapeProcessingService

__all__ = ['CompanyService', 'RatingService', 'ScrapeProcessingService']

