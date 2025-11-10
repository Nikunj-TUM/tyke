"""
Bright Data Web Unlocker API Client

This module provides a production-ready client for Bright Data's Web Unlocker API.
It handles proxy management, anti-bot measures, CAPTCHA solving, and automatic retries.

Documentation: https://docs.brightdata.com/api-reference/web-unlocker/overview
"""

import requests
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BrightDataConfig:
    """Configuration for Bright Data Web Unlocker API"""
    api_key: str
    zone: str = "web_unlocker1"
    country: str = "in"
    max_retries: int = 3
    retry_backoff: int = 2
    timeout: int = 120


class BrightDataError(Exception):
    """Base exception for Bright Data client errors"""
    pass


class BrightDataAuthError(BrightDataError):
    """Raised when authentication fails"""
    pass


class BrightDataRateLimitError(BrightDataError):
    """Raised when rate limit is exceeded"""
    pass


class BrightDataClient:
    """
    Production-ready client for Bright Data Web Unlocker API.
    
    Features:
    - Automatic retry with exponential backoff
    - Comprehensive error handling
    - Request/response logging
    - Support for all Bright Data Web Unlocker parameters
    
    Example:
        config = BrightDataConfig(api_key="your_api_key")
        client = BrightDataClient(config)
        html = client.fetch_url("https://example.com")
    """
    
    API_ENDPOINT = "https://api.brightdata.com/request"
    
    def __init__(self, config: BrightDataConfig):
        """
        Initialize Bright Data client with configuration.
        
        Args:
            config: BrightDataConfig instance with API credentials and settings
        """
        if not config.api_key:
            raise BrightDataAuthError("Bright Data API key is required")
        
        self.config = config
        self.session = requests.Session()
        
        # Set up authentication header
        self.session.headers.update({
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"Initialized Bright Data client with zone: {config.zone}, country: {config.country}")
    
    def fetch_url(
        self,
        url: str,
        method: str = "GET",
        country: Optional[str] = None,
        format: str = "raw",
        data_format: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None
    ) -> str:
        """
        Fetch URL content through Bright Data Web Unlocker API.
        
        This method handles automatic retries, error handling, and returns the raw HTML content.
        
        Args:
            url: Target URL to fetch (must include protocol: http/https)
            method: HTTP method (GET, POST, etc.). Default: GET
            country: Two-letter ISO country code for proxy location. Default: from config
            format: Response format - 'raw' returns HTML string, 'json' returns structured data. Default: raw
            data_format: Additional format transformation ('markdown', 'screenshot', None). Default: None
            headers: Optional custom headers to send with the request
            body: Optional request body for POST requests
            
        Returns:
            str: HTML content of the fetched page
            
        Raises:
            BrightDataAuthError: If authentication fails
            BrightDataRateLimitError: If rate limit is exceeded
            BrightDataError: For other API errors
            
        Example:
            html = client.fetch_url("https://example.com/page?param=value")
        """
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"URL must include protocol (http:// or https://): {url}")
        
        country = country or self.config.country
        
        # Build request payload according to Bright Data API spec
        payload: Dict[str, Any] = {
            "zone": self.config.zone,
            "url": url,
            "format": format,
            "method": method.upper(),
            "country": country
        }
        
        # Add optional parameters
        if data_format:
            payload["data_format"] = data_format
        
        if headers:
            payload["headers"] = headers
        
        if body:
            payload["body"] = body
        
        # Implement retry logic with exponential backoff
        last_exception = None
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(
                    f"Fetching URL via Bright Data (attempt {attempt}/{self.config.max_retries}): {url[:100]}"
                )
                logger.debug(f"Bright Data request payload: {payload}")
                
                # Make API request
                response = self.session.post(
                    self.API_ENDPOINT,
                    json=payload,
                    timeout=self.config.timeout
                )
                
                # Handle different HTTP status codes
                if response.status_code == 200:
                    logger.info(f"Successfully fetched URL via Bright Data: {url[:100]}")
                    logger.debug(f"Response size: {len(response.text)} characters")
                    return response.text
                
                elif response.status_code == 401:
                    error_msg = f"Bright Data authentication failed. Check API key and zone configuration."
                    logger.error(error_msg)
                    raise BrightDataAuthError(error_msg)
                
                elif response.status_code == 429:
                    error_msg = f"Bright Data rate limit exceeded. Status: {response.status_code}"
                    logger.warning(error_msg)
                    
                    # Don't retry on rate limit for the last attempt
                    if attempt == self.config.max_retries:
                        raise BrightDataRateLimitError(error_msg)
                    
                    # Wait longer for rate limits
                    wait_time = self.config.retry_backoff ** attempt * 2
                    logger.info(f"Rate limited. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                
                elif response.status_code == 400:
                    error_msg = f"Bad request to Bright Data API. Check URL and parameters. Response: {response.text[:500]}"
                    logger.error(error_msg)
                    raise BrightDataError(error_msg)
                
                else:
                    error_msg = f"Bright Data API error. Status: {response.status_code}, Response: {response.text[:500]}"
                    logger.error(error_msg)
                    
                    # Retry on 5xx errors
                    if 500 <= response.status_code < 600:
                        last_exception = BrightDataError(error_msg)
                        if attempt < self.config.max_retries:
                            wait_time = self.config.retry_backoff ** attempt
                            logger.info(f"Server error. Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                            continue
                    
                    raise BrightDataError(error_msg)
            
            except requests.exceptions.Timeout as e:
                error_msg = f"Timeout fetching URL via Bright Data (attempt {attempt}/{self.config.max_retries}): {url[:100]}"
                logger.warning(error_msg)
                last_exception = BrightDataError(f"Request timeout: {str(e)}")
                
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
            
            except requests.exceptions.RequestException as e:
                error_msg = f"Request error via Bright Data (attempt {attempt}/{self.config.max_retries}): {str(e)}"
                logger.warning(error_msg)
                last_exception = BrightDataError(f"Request failed: {str(e)}")
                
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
            
            except BrightDataAuthError:
                # Don't retry authentication errors
                raise
            
            except Exception as e:
                error_msg = f"Unexpected error via Bright Data: {str(e)}"
                logger.error(error_msg)
                last_exception = BrightDataError(error_msg)
                
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
        
        # All retries exhausted
        error_msg = f"Failed to fetch URL after {self.config.max_retries} attempts: {url[:100]}"
        logger.error(error_msg)
        
        if last_exception:
            raise last_exception
        
        raise BrightDataError(error_msg)
    
    def close(self):
        """Close the session and cleanup resources."""
        self.session.close()
        logger.debug("Bright Data client session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.close()
        return False

