"""
Scraping service that duplicates logic from infomerics scraper modules
This file contains the exact HTML parsing logic from the original scraper
"""
import re
import requests
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class InstrumentData:
    """Data class to hold instrument information"""
    company_name: str
    instrument_category: str
    rating: str
    outlook: str
    instrument_amount: str
    date: str
    url: str


class HTMLCreditRatingExtractor:
    """
    Extract credit rating data from HTML content using BeautifulSoup
    DUPLICATED FROM extract_data_press_release_page.py - DO NOT MODIFY PARSING LOGIC
    """
    
    def __init__(self, html_content: str):
        self.html_content = html_content
        self.extracted_data: List[InstrumentData] = []
    
    def extract_company_data(self) -> List[InstrumentData]:
        """Extract all company data from HTML content using BeautifulSoup"""
        soup = BeautifulSoup(self.html_content, 'html.parser')
        
        logger.info(f"HTML file size: {len(self.html_content)} characters")
        
        # The HTML has malformed class attributes with escaped quotes
        # Find all h3 elements that contain company names
        all_h3 = soup.find_all('h3')
        logger.info(f"Found {len(all_h3)} h3 elements total")
        
        # Filter h3 elements that look like company names
        company_headers = []
        for h3 in all_h3:
            text = h3.get_text().strip()
            # Company names typically end with Limited, LLP, Private Limited, etc.
            if any(suffix in text for suffix in ['Limited', 'LLP', 'Private', 'Company']):
                company_headers.append(h3)
        
        logger.info(f"Found {len(company_headers)} company headers")
        
        for i, header in enumerate(company_headers):
            company_name = self._clean_text(header.get_text())
            logger.info(f"Processing company {i+1}: {company_name}")
            
            # Instead of looking for parent container, look for the next sibling elements
            # that contain the rating data
            current_element = header
            
            # Look for rating data in the following elements
            self._extract_instruments_after_header(company_name, current_element)
        
        return self.extracted_data
    
    def _extract_instruments_after_header(self, company_name: str, header_element) -> None:
        """Extract instruments from elements following the company header"""
        # Start from the header and look at subsequent elements
        current = header_element.next_sibling
        instrument_count = 0
        
        # Look through the next several elements for rating data
        elements_checked = 0
        max_elements = 50  # Limit how far we search
        
        while current and elements_checked < max_elements:
            elements_checked += 1
            
            # Skip text nodes and look for div elements
            if hasattr(current, 'name') and current.name:
                # Look for rating data in this element and its children
                rating_blocks = self._find_rating_blocks_in_element(current)
                
                for block in rating_blocks:
                    if self._extract_instrument_from_block(company_name, block):
                        instrument_count += 1
                
                # Stop if we hit another company (h3 element)
                if current.name == 'h3' and any(suffix in current.get_text() 
                                               for suffix in ['Limited', 'LLP', 'Private', 'Company']):
                    break
                    
                # Stop if we hit an hr tag (company separator)
                if current.name == 'hr':
                    break
            
            current = current.next_sibling
        
        logger.info(f"  Found {instrument_count} instruments for {company_name}")
    
    def _find_rating_blocks_in_element(self, element) -> list:
        """Find all rating data blocks within an element"""
        rating_blocks = []
        
        # Look for elements that contain instrument categories
        category_divs = element.find_all('div', string=lambda text: text and 'Instrument Category' in text)
        
        for category_div in category_divs:
            # Find the parent structure that contains all the rating info
            rating_block = category_div
            for _ in range(10):  # Go up max 10 levels
                parent = rating_block.parent
                if not parent:
                    break
                # Look for a parent that contains all the rating info
                if (parent.find(string=lambda text: text and 'Ratings' in text) and
                    parent.find(string=lambda text: text and 'Outlook' in text) and
                    parent.find(string=lambda text: text and 'Instrument Amount' in text)):
                    rating_block = parent
                    break
                rating_block = parent
            
            rating_blocks.append(rating_block)
        
        return rating_blocks
    
    def _extract_instrument_from_block(self, company_name: str, block) -> bool:
        """Extract instrument data from a block, return True if successful"""
        try:
            # Extract instrument category
            category = "Not found"
            category_div = block.find('div', string=lambda text: text and 'Instrument Category' in text)
            if category_div:
                # Look for the next div that contains the category name
                next_div = category_div.find_next_sibling('div')
                if next_div:
                    category = self._clean_text(next_div.get_text())
            
            # Extract date (look for "as on" text)
            date = "Not found"
            date_text = block.find(string=lambda text: text and 'as on' in text)
            if date_text:
                date_match = re.search(r'as on\s+([^\n\t]+)', str(date_text))
                if date_match:
                    date = self._clean_text(date_match.group(1))
            
            # Extract rating
            rating = "Not found"
            rating_div = block.find('div', string=lambda text: text and 'Ratings' in text)
            if rating_div:
                next_div = rating_div.find_next_sibling('div')
                if next_div:
                    rating_text = next_div.get_text()
                    # Clean up rating text
                    rating = self._clean_text(rating_text)
            
            # Extract outlook
            outlook = "Not found"
            outlook_div = block.find('div', string=lambda text: text and 'Outlook' in text)
            if outlook_div:
                next_div = outlook_div.find_next_sibling('div')
                if next_div:
                    outlook = self._clean_text(next_div.get_text())
            
            # Extract instrument amount
            amount = "Not found"
            amount_div = block.find('div', string=lambda text: text and 'Instrument Amount' in text)
            if amount_div:
                next_div = amount_div.find_next_sibling('div')
                if next_div:
                    amount = self._clean_text(next_div.get_text())
            
            # Extract URL - try multiple approaches
            url = "Not found"
            
            # Method 1: Look for "View Instrument" text in links
            view_link = block.find('a', string=lambda text: text and 'View Instrument' in text)
            if view_link and view_link.get('href'):
                url = view_link.get('href')
            
            # Method 2: Look for links with specific classes
            if url == "Not found":
                view_link = block.find('a', class_=lambda x: x and 'view-rating' in ' '.join(x) if x else False)
                if view_link and view_link.get('href'):
                    url = view_link.get('href')
            
            # Method 3: Look for any link containing 'admin/uploads' in href
            if url == "Not found":
                view_link = block.find('a', href=lambda href: href and 'admin/uploads' in href)
                if view_link:
                    url = view_link.get('href')
            
            # Method 4: Look for any PDF link
            if url == "Not found":
                view_link = block.find('a', href=lambda href: href and '.pdf' in href)
                if view_link:
                    url = view_link.get('href')
            
            # Clean the URL if found
            if url != "Not found":
                url = self._clean_url(url)
            
            # Check if this is a duplicate entry by comparing key fields
            for existing_item in self.extracted_data:
                if (existing_item.company_name == company_name and 
                    existing_item.instrument_category == category and
                    existing_item.rating == rating and
                    existing_item.instrument_amount == amount):
                    # This is a duplicate, skip it
                    logger.debug(f"    Skipping duplicate entry for {category}")
                    return False
            
            # Only add if we found at least category or rating
            if category != "Not found" or rating != "Not found":
                instrument_data = InstrumentData(
                    company_name=company_name,
                    instrument_category=category,
                    rating=rating,
                    outlook=outlook,
                    instrument_amount=amount,
                    date=date,
                    url=url
                )
                
                self.extracted_data.append(instrument_data)
                logger.debug(f"    ✓ Added: {category}")
                logger.debug(f"      Rating: {rating}")
                logger.debug(f"      Outlook: {outlook}")
                logger.debug(f"      Amount: {amount}")
                logger.debug(f"      Date: {date}")
                logger.debug(f"      URL: {url[:60]}..." if len(url) > 60 else f"      URL: {url}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"    Error extracting instrument data: {str(e)}")
            return False
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and HTML entities"""
        if not text:
            return ""
        
        # Remove HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        
        # Remove extra whitespace and newlines
        cleaned = re.sub(r'\s+', ' ', text.strip())
        # Remove any remaining tabs or newlines
        cleaned = re.sub(r'[\t\n\r]', ' ', cleaned)
        return cleaned.strip()
    
    def _clean_url(self, url: str) -> str:
        """Clean URL by removing quotes and extra characters"""
        if not url:
            return "Not found"
        
        # Remove surrounding quotes and backslashes
        cleaned = url.strip()
        if cleaned.startswith('"') and cleaned.endswith('"'):
            cleaned = cleaned[1:-1]
        if cleaned.startswith('\\"') and cleaned.endswith('\\"'):
            cleaned = cleaned[2:-2]
        
        # Remove any remaining escape characters
        cleaned = cleaned.replace('\\"', '"').replace('\\', '')
        
        return cleaned.strip()


class InfomericsPressScraper:
    """
    Scraper for Infomerics press release pages
    DUPLICATED FROM scrape_press_release_page.py - DO NOT MODIFY
    """
    
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
            
            logger.info(f"Scraping Infomerics data from {from_date} to {to_date}...")
            logger.info(f"URL: {self.base_url}")
            logger.info(f"Parameters: {params}")
            
            # Make the request
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response size: {len(response.text)} characters")
            
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
            logger.error(f"Error making request: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            return None
    
    def _validate_date_format(self, date_str: str) -> None:
        """Validate date format is YYYY-MM-DD"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD")


class ScraperService:
    """
    Async wrapper service for scraping and extracting Infomerics data
    """
    
    def __init__(self):
        self.scraper = InfomericsPressScraper()
    
    async def scrape_and_extract(
        self,
        start_date: str,
        end_date: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Scrape press releases and extract company data
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of extracted instrument data as dictionaries
        """
        try:
            # Scrape the data
            response_data = self.scraper.scrape_date_range(start_date, end_date)
            
            if not response_data:
                logger.error("Failed to scrape data")
                return None
            
            # Extract HTML content
            html_content = response_data.get('body', '')
            if not html_content:
                logger.error("No HTML content in response")
                return None
            
            # Extract company data
            logger.info("Extracting company data from HTML...")
            extractor = HTMLCreditRatingExtractor(html_content)
            extracted_data = extractor.extract_company_data()
            
            if not extracted_data:
                logger.warning("No data extracted from HTML content")
                return []
            
            # Convert to dictionaries
            data_dicts = []
            for item in extracted_data:
                data_dicts.append({
                    'company_name': item.company_name,
                    'instrument_category': item.instrument_category,
                    'rating': item.rating,
                    'outlook': item.outlook,
                    'instrument_amount': item.instrument_amount,
                    'date': item.date,
                    'url': item.url
                })
            
            logger.info(f"Extracted {len(data_dicts)} instruments from {len(set(d['company_name'] for d in data_dicts))} companies")
            return data_dicts
            
        except Exception as e:
            logger.error(f"Error in scrape_and_extract: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

