#!/usr/bin/env python3
"""
Script to scrape Infomerics press release pages and extract company data.
Supports both Bright Data Web Unlocker API and direct requests.
"""

import requests
import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlencode

# Import parent directory modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.bright_data_client import BrightDataClient, BrightDataConfig

# Import the extraction module
from extract_data_press_release_page import HTMLCreditRatingExtractor


class InfomericsPressScraper:
    """
    Scraper for Infomerics press release pages.
    
    Supports two modes:
    1. Bright Data Web Unlocker API - set use_bright_data=True and provide API credentials
    2. Direct requests - set use_bright_data=False for simple HTTP requests
    """
    
    def __init__(
        self, 
        use_bright_data: bool = False,
        bright_data_api_key: Optional[str] = None,
        bright_data_zone: str = "web_unlocker1"
    ):
        """
        Initialize the scraper.
        
        Args:
            use_bright_data: If True, use Bright Data API; if False, use direct requests
            bright_data_api_key: API key for Bright Data (required if use_bright_data=True)
            bright_data_zone: Zone identifier for Bright Data
        """
        self.base_url = "https://www.infomerics.com/latest-press-release_date_wise.php"
        self.use_bright_data = use_bright_data
        
        if self.use_bright_data:
            # Initialize Bright Data client
            if not bright_data_api_key:
                raise ValueError("bright_data_api_key is required when use_bright_data=True")
            
            print("Using Bright Data Web Unlocker API")
            bright_data_config = BrightDataConfig(
                api_key=bright_data_api_key,
                zone=bright_data_zone,
                max_retries=3,
                retry_backoff=2,
                timeout=120
            )
            self.bright_data_client = BrightDataClient(bright_data_config)
        else:
            # Use direct requests
            print("Using direct requests")
            self.session = requests.Session()
            # Set user agent to avoid blocking
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            # Disable SSL verification for this specific site if needed
            self.session.verify = False
            # Suppress SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def scrape_date_range(self, from_date: str, to_date: str) -> Optional[Dict[str, Any]]:
        """
        Scrape press releases for a given date range.
        
        Uses Bright Data API or direct requests based on initialization.
        
        Args:
            from_date: Start date in format YYYY-MM-DD
            to_date: End date in format YYYY-MM-DD
            
        Returns:
            Dictionary containing response data or None if failed
        """
        try:
            # Validate date format
            self._validate_date_format(from_date)
            self._validate_date_format(to_date)
            
            # Construct URL with parameters
            params = {
                'fromdate': from_date,
                'todate': to_date
            }
            
            print(f"Scraping Infomerics data from {from_date} to {to_date}...")
            print(f"Base URL: {self.base_url}")
            print(f"Parameters: {params}")
            
            if self.use_bright_data:
                # Use Bright Data Web Unlocker API
                full_url = f"{self.base_url}?{urlencode(params)}"
                
                print(f"Fetching via Bright Data: {full_url}")
                html_content = self.bright_data_client.fetch_url(
                    url=full_url,
                    method="GET"
                )
                
                print(f"Successfully fetched via Bright Data")
                print(f"Response size: {len(html_content)} characters")
                
                # Create response data structure for compatibility
                response_data = {
                    'status_code': 200,
                    'headers': {},
                    'body': html_content,
                    'url': full_url,
                    'from_date': from_date,
                    'to_date': to_date,
                    'scraped_at': datetime.now().isoformat(),
                    'method': 'bright_data'
                }
                
            else:
                # Use direct requests
                print(f"Fetching via direct request")
                response = self.session.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                
                print(f"Response status: {response.status_code}")
                print(f"Response size: {len(response.text)} characters")
                
                # Create response data structure
                response_data = {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'body': response.text,
                    'url': response.url,
                    'from_date': from_date,
                    'to_date': to_date,
                    'scraped_at': datetime.now().isoformat(),
                    'method': 'direct'
                }
            
            return response_data
            
        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _validate_date_format(self, date_str: str) -> None:
        """Validate date format is YYYY-MM-DD"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD")
    
    def save_response_data(self, response_data: Dict[str, Any], from_date: str, to_date: str) -> str:
        """Save response data to JSON file"""
        filename = f"infomerics_{from_date}_{to_date}.json"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)
        
        print(f"Response data saved to: {filename}")
        return filepath
    
    def extract_data_from_response(self, response_data: Dict[str, Any]) -> Optional[list]:
        """Extract company data from response using the extraction module"""
        try:
            # Create a temporary JSON file for the extractor
            temp_filename = "temp_response.json"
            temp_filepath = os.path.join(os.path.dirname(__file__), temp_filename)
            
            # Save response data temporarily
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            # Use the extractor
            extractor = HTMLCreditRatingExtractor(temp_filename)
            extracted_data = extractor.extract_company_data()
            
            # Clean up temp file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            
            return extracted_data
            
        except Exception as e:
            print(f"Error extracting data: {str(e)}")
            # Clean up temp file even if error occurs
            temp_filepath = os.path.join(os.path.dirname(__file__), "temp_response.json")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return None
    
    def save_extracted_data(self, extractor: HTMLCreditRatingExtractor, from_date: str, to_date: str) -> None:
        """Save extracted data in multiple formats with date-specific filenames"""
        base_filename = f"infomerics_{from_date}_{to_date}"
        
        # Save to JSON
        json_filename = f"{base_filename}.json"
        extractor.save_to_json(json_filename)
        
        # Save to CSV
        csv_filename = f"{base_filename}.csv"
        extractor.save_to_csv(csv_filename)
        
        # Save to Excel (if pandas available)
        excel_filename = f"{base_filename}.xlsx"
        extractor.save_to_excel(excel_filename)
        
        print(f"\nExtracted data saved as:")
        print(f"- {json_filename}")
        print(f"- {csv_filename}")
        print(f"- {excel_filename} (if pandas available)")


def main(from_date: str, to_date: str):
    """
    Main function to scrape and extract data for given date range.
    
    Reads configuration from environment variables:
    - USE_BRIGHT_DATA: Set to 'true' to use Bright Data API
    - BRIGHT_DATA_API_KEY: Your Bright Data API key
    - BRIGHT_DATA_ZONE: Zone identifier (default: web_unlocker1)
    
    Args:
        from_date: Start date in format YYYY-MM-DD
        to_date: End date in format YYYY-MM-DD
    """
    try:
        # Read configuration from environment variables
        use_bright_data = os.getenv('USE_BRIGHT_DATA', 'false').lower() == 'true'
        bright_data_api_key = os.getenv('BRIGHT_DATA_API_KEY', '')
        bright_data_zone = os.getenv('BRIGHT_DATA_ZONE', 'web_unlocker1')
        
        # Initialize scraper with appropriate mode
        scraper = InfomericsPressScraper(
            use_bright_data=use_bright_data,
            bright_data_api_key=bright_data_api_key if use_bright_data else None,
            bright_data_zone=bright_data_zone
        )
        
        # Scrape the data
        response_data = scraper.scrape_date_range(from_date, to_date)
        
        if not response_data:
            print("Failed to scrape data")
            return
        
        # Save raw response data
        response_filepath = scraper.save_response_data(response_data, from_date, to_date)
        
        # Extract company data using the extraction module
        print("\nExtracting company data...")
        
        # Create extractor with a temporary JSON file
        temp_filename = "temp_response.json"
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=2, ensure_ascii=False)
        
        try:
            extractor = HTMLCreditRatingExtractor(temp_filename)
            extracted_data = extractor.extract_company_data()
            
            if extracted_data:
                # Print summary
                extractor.print_summary()
                
                # Save extracted data with date-specific filenames
                scraper.save_extracted_data(extractor, from_date, to_date)
                
                print(f"\n=== SCRAPING AND EXTRACTION COMPLETE ===")
                print(f"Date range: {from_date} to {to_date}")
                print(f"Total instruments extracted: {len(extracted_data)}")
                
            else:
                print("No data extracted from the scraped content")
                
        finally:
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scrape_press_release_page.py <from_date> <to_date>")
        print("Date format: YYYY-MM-DD")
        print("Example: python scrape_press_release_page.py 2025-10-09 2025-10-12")
        sys.exit(1)
    
    from_date = sys.argv[1]
    to_date = sys.argv[2]
    
    main(from_date, to_date)
