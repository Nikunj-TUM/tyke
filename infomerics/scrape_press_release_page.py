#!/usr/bin/env python3
"""
Script to scrape Infomerics press release pages and extract company data.
Makes GET requests to the Infomerics website and processes the HTML using extract_data_press_release_page.py
"""

import requests
import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
import time

# Import the extraction module
from extract_data_press_release_page import HTMLCreditRatingExtractor


class InfomericsPressScraper:
    """Scraper for Infomerics press release pages"""
    
    def __init__(self):
        self.base_url = "https://www.infomerics.com/latest-press-release_date_wise.php"
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
        Scrape press releases for a given date range
        
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
            print(f"URL: {self.base_url}")
            print(f"Parameters: {params}")
            
            # Make the request
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            print(f"Response status: {response.status_code}")
            print(f"Response size: {len(response.text)} characters")
            
            # Create response data structure similar to bright_data format
            response_data = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'body': response.text,
                'url': response.url,
                'from_date': from_date,
                'to_date': to_date,
                'scraped_at': datetime.now().isoformat()
            }
            
            return response_data
            
        except requests.RequestException as e:
            print(f"Error making request: {str(e)}")
            return None
        except Exception as e:
            print(f"Error during scraping: {str(e)}")
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
    Main function to scrape and extract data for given date range
    
    Args:
        from_date: Start date in format YYYY-MM-DD
        to_date: End date in format YYYY-MM-DD
    """
    try:
        # Initialize scraper
        scraper = InfomericsPressScraper()
        
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
