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
from urllib.parse import urlencode

from api.config import settings
from api.bright_data_client import BrightDataClient, BrightDataConfig

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
    Scraper for Infomerics press release pages.
    
    Supports two modes:
    1. Bright Data Web Unlocker API (when USE_BRIGHT_DATA=True) - bypasses anti-bot measures
    2. Direct requests (when USE_BRIGHT_DATA=False) - simple direct HTTP requests
    """
    
    def __init__(self):
        self.base_url = "https://www.infomerics.com/latest-press-release_date_wise.php"
        self.use_bright_data = settings.USE_BRIGHT_DATA
        
        if self.use_bright_data:
            # Initialize Bright Data client
            logger.info("Using Bright Data Web Unlocker API for Infomerics scraping")
            bright_data_config = BrightDataConfig(
                api_key=settings.BRIGHT_DATA_API_KEY,
                zone=settings.BRIGHT_DATA_ZONE,
                country=settings.BRIGHT_DATA_COUNTRY,
                max_retries=settings.BRIGHT_DATA_MAX_RETRIES,
                retry_backoff=settings.BRIGHT_DATA_RETRY_BACKOFF,
                timeout=120
            )
            self.bright_data_client = BrightDataClient(bright_data_config)
        else:
            # Use direct requests
            logger.info("Using direct requests for Infomerics scraping")
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
        
        Uses Bright Data API or direct requests based on USE_BRIGHT_DATA setting.
        
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
            logger.info(f"Base URL: {self.base_url}")
            logger.info(f"Parameters: {params}")
            
            if self.use_bright_data:
                # Use Bright Data Web Unlocker API
                # Construct full URL with query parameters
                full_url = f"{self.base_url}?{urlencode(params)}"
                
                logger.info(f"Fetching via Bright Data: {full_url}")
                html_content = self.bright_data_client.fetch_url(
                    url=full_url,
                    method="GET"
                )
                
                logger.info(f"Successfully fetched via Bright Data")
                logger.info(f"Response size: {len(html_content)} characters")
                
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
                logger.info(f"Fetching via direct request")
                response = self.session.get(self.base_url, params=params, timeout=120)
                response.raise_for_status()
                
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response size: {len(response.text)} characters")
                
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
            logger.error(f"Error during scraping: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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


class ZaubaCorpScraper:
    """
    Scraper for ZaubaCorp to fetch CIN (Company Identification Number).
    
    Supports two modes:
    1. Bright Data Web Unlocker API (when USE_BRIGHT_DATA=True) - bypasses anti-bot measures
    2. Direct requests (when USE_BRIGHT_DATA=False) - simple direct HTTP requests
    """
    
    BASE_URL = "https://www.zaubacorp.com/companysearchresults/"
    
    def __init__(self):
        self.timeout = 30  # 30 seconds timeout
        self.use_bright_data = settings.USE_BRIGHT_DATA
        
        if self.use_bright_data:
            # Initialize Bright Data client
            logger.info("Using Bright Data Web Unlocker API for ZaubaCorp scraping")
            bright_data_config = BrightDataConfig(
                api_key=settings.BRIGHT_DATA_API_KEY,
                zone=settings.BRIGHT_DATA_ZONE,
                country=settings.BRIGHT_DATA_COUNTRY,
                max_retries=settings.BRIGHT_DATA_MAX_RETRIES,
                retry_backoff=settings.BRIGHT_DATA_RETRY_BACKOFF,
                timeout=self.timeout
            )
            self.bright_data_client = BrightDataClient(bright_data_config)
        else:
            logger.info("Using direct requests for ZaubaCorp scraping")
    
    def _slugify_company_name(self, company_name: str) -> str:
        """
        Convert company name to URL slug format used by ZaubaCorp.
        
        Aggressively cleans the name by removing suffixes, symbols, etc.
        to increase match probability.
        
        Args:
            company_name: Full company name
            
        Returns:
            Cleaned and slugified name for URL in UPPERCASE with hyphens
        """
        import re
        # Remove ALL content in square brackets (alternate/erstwhile names)
        company_name = re.sub(r'\[.*?\]', '', company_name)
        # Remove ALL content in parentheses (including erstwhile names)
        company_name = re.sub(r'\(.*?\)', '', company_name)
        
        # Convert to uppercase first for consistent processing
        company_name = company_name.upper()
        
        # Remove "and" and "&" and other symbols
        company_name = company_name.replace(' AND ', ' ')
        company_name = company_name.replace(' & ', ' ')
        
        # Remove common company suffixes to get core business name
        # This increases match probability (ZaubaCorp might list with/without these)
        suffixes_to_remove = [
            'PRIVATE LIMITED',
            'PRIVATE LTD',
            'PVT LTD',
            'PVT LTD.',
            'PVT. LTD.',
            'LIMITED',
            'LTD',
            'LTD.',
            'PRIVATE',
            'PVT',
            'PVT.',
            'LLP',
        ]
        
        # Remove all suffixes iteratively (handles nested cases like "PRIVATE LIMITED")
        changed = True
        while changed:
            changed = False
            for suffix in suffixes_to_remove:
                if company_name.endswith(' ' + suffix):
                    company_name = company_name[:-len(suffix)].strip()
                    changed = True
                    break  # Start over with the new name
        
        # Replace spaces with hyphens
        slug = company_name.replace(' ', '-')
        
        # Remove any double hyphens that might have been created
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def extract_erstwhile_name(self, company_name: str) -> Optional[str]:
        """
        Extract the erstwhile/formerly name from brackets if present
        
        Args:
            company_name: Full company name
            
        Returns:
            Erstwhile company name or None if not present
        """
        import re
        # Match parentheses with "Erstwhile" or "Formerly"
        patterns = [
            r'\(Erstwhile\s+([^)]+)\)',
            r'\(erstwhile\s+([^)]+)\)',
            r'\(Formerly\s+([^)]+)\)',
            r'\(formerly\s+([^)]+)\)',
            r'\[Erstwhile\s+([^\]]+)\]',
            r'\[erstwhile\s+([^\]]+)\]',
            r'\[Formerly\s+([^\]]+)\]',
            r'\[formerly\s+([^\]]+)\]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, company_name)
            if match:
                erstwhile_name = match.group(1).strip()
                logger.info(f"Extracted erstwhile name: {erstwhile_name} from {company_name}")
                return erstwhile_name
        
        return None
    
    def scrape_company_search(self, company_name: str) -> Optional[str]:
        """
        Scrape ZaubaCorp search results for a company.
        
        Uses Bright Data API or direct requests based on USE_BRIGHT_DATA setting.
        
        Args:
            company_name: Company name to search for
            
        Returns:
            HTML content or None on error
        """
        try:
            slug = self._slugify_company_name(company_name)
            url = f"{self.BASE_URL}{slug}"
            
            logger.info(f"Scraping ZaubaCorp: {url}")
            
            if self.use_bright_data:
                # Use Bright Data Web Unlocker API
                logger.info(f"Fetching ZaubaCorp via Bright Data for: {company_name}")
                html_text = self.bright_data_client.fetch_url(
                    url=url,
                    method="GET"
                )
                logger.info(f"Successfully scraped ZaubaCorp via Bright Data for {company_name}: {len(html_text)} chars")
                
            else:
                # Use direct requests
                # Set headers to mimic a browser request
                # Note: Don't set Accept-Encoding - let requests handle compression automatically
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                logger.info(f"Fetching ZaubaCorp via direct request for: {company_name}")
                response = requests.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                
                # Use the response's detected encoding (requests auto-detects from Content-Type header)
                html_text = response.text
                logger.info(f"Successfully scraped ZaubaCorp via direct request for {company_name}: {len(html_text)} chars")
            
            return html_text
            
        except Exception as e:
            logger.error(f"Error scraping ZaubaCorp for {company_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None


class ZaubaCorpCINExtractor:
    """
    Extract CIN from ZaubaCorp search results HTML
    """
    
    def extract_cin(self, html_content: str, exact_company_name: str) -> tuple[Optional[str], str]:
        """
        Extract CIN from ZaubaCorp HTML for a specific company name
        
        Args:
            html_content: HTML content from ZaubaCorp
            exact_company_name: The exact company name to match
            
        Returns:
            Tuple of (cin, status) where:
            - cin: CIN string or None
            - status: 'found', 'not_found', or 'multiple_matches'
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the results table
            # Based on sample HTML: <table id="results" class="table table-striped">
            results_table = soup.find('table', {'id': 'results'})
            
            if not results_table:
                logger.warning("No results table found in ZaubaCorp HTML")
                return (None, 'not_found')
            
            # Find all table rows in tbody
            tbody = results_table.find('tbody')
            if not tbody:
                logger.warning("No tbody found in results table")
                return (None, 'not_found')
            
            rows = tbody.find_all('tr')
            if not rows:
                logger.warning("No rows found in results table")
                return (None, 'not_found')
            
            logger.info(f"Found {len(rows)} results in ZaubaCorp table")
            
            # Extract all company matches
            matches = []
            for row in rows:
                tds = row.find_all('td')
                if len(tds) >= 2:
                    # Column 0: CIN with link
                    # Column 1: Company name with link
                    cin_link = tds[0].find('a')
                    name_link = tds[1].find('a')
                    
                    if cin_link and name_link:
                        cin = cin_link.get_text().strip()
                        name = name_link.get_text().strip()
                        
                        matches.append({
                            'cin': cin,
                            'name': name
                        })
            
            if not matches:
                logger.info(f"No matches found for company: {exact_company_name}")
                return (None, 'no_results')  # Special status to trigger fallback
            
            # Normalize names for comparison (remove parentheses, brackets, extra spaces)
            def normalize_name(name: str) -> str:
                """Normalize company name for fuzzy matching"""
                import re
                # Remove square brackets and their contents (alternate/erstwhile names)
                name = re.sub(r'\[.*?\]', '', name)
                # Remove parentheses with "Erstwhile" or similar patterns inside
                name = re.sub(r'\(.*?Erstwhile.*?\)', '', name, flags=re.IGNORECASE)
                name = re.sub(r'\(.*?Formerly.*?\)', '', name, flags=re.IGNORECASE)
                # Remove remaining parentheses but KEEP their contents  
                name = re.sub(r'[()]', '', name)
                # Remove "and" and "&"
                name = name.replace(' and ', ' ').replace(' & ', ' ')
                name = name.replace(' AND ', ' ')
                # Remove extra spaces and convert to uppercase
                name = ' '.join(name.upper().split())
                return name
            
            def normalize_for_contains(name: str) -> str:
                """More aggressive normalization for substring matching"""
                import re
                name = normalize_name(name)
                # Remove common suffixes for better matching
                suffixes = ['PRIVATE LIMITED', 'LIMITED', 'PRIVATE', 'LLP', 'PVT LTD', 'PVT', 'LTD']
                for suffix in suffixes:
                    if name.endswith(' ' + suffix):
                        name = name[:-len(suffix)].strip()
                return name
            
            query_normalized = normalize_name(exact_company_name)
            
            # Try exact case-insensitive match first
            exact_matches = [
                m for m in matches 
                if m['name'].strip().upper() == exact_company_name.strip().upper()
            ]
            
            if len(exact_matches) == 1:
                logger.info(f"Found exact CIN match for {exact_company_name}: {exact_matches[0]['cin']}")
                return (exact_matches[0]['cin'], 'found')
            elif len(exact_matches) > 1:
                logger.warning(f"Multiple exact matches found for {exact_company_name}: {[m['cin'] for m in exact_matches]}")
                return (exact_matches[0]['cin'], 'multiple_matches')
            
            # Try normalized fuzzy match (handles parentheses, extra spaces, etc)
            fuzzy_matches = [
                m for m in matches 
                if normalize_name(m['name']) == query_normalized
            ]
            
            if len(fuzzy_matches) == 1:
                logger.info(f"Found fuzzy CIN match for {exact_company_name}: {fuzzy_matches[0]['cin']} (matched: {fuzzy_matches[0]['name']})")
                return (fuzzy_matches[0]['cin'], 'found')
            elif len(fuzzy_matches) > 1:
                logger.warning(f"Multiple fuzzy matches found for {exact_company_name}: {[m['cin'] for m in fuzzy_matches]}")
                return (fuzzy_matches[0]['cin'], 'multiple_matches')
            
            # Try aggressive normalization for smart matching
            # Remove suffixes like "PRIVATE LIMITED", "LIMITED", etc for core name comparison
            query_smart = normalize_for_contains(exact_company_name)
            smart_matches = [
                m for m in matches 
                if normalize_for_contains(m['name']) == query_smart
            ]
            
            if len(smart_matches) == 1:
                logger.info(f"Found smart match for {exact_company_name}: {smart_matches[0]['cin']} (matched: {smart_matches[0]['name']})")
                return (smart_matches[0]['cin'], 'found')
            elif len(smart_matches) > 1:
                logger.warning(f"Multiple smart matches for {exact_company_name}: {[m['cin'] for m in smart_matches]}")
                return (smart_matches[0]['cin'], 'multiple_matches')
            
            # Try substring/contains matching - check if any result contains our query
            contains_matches = [
                m for m in matches 
                if query_smart in normalize_for_contains(m['name']) or 
                   normalize_for_contains(m['name']) in query_smart
            ]
            
            if len(contains_matches) == 1:
                logger.info(f"Found contains match for {exact_company_name}: {contains_matches[0]['cin']} (matched: {contains_matches[0]['name']})")
                return (contains_matches[0]['cin'], 'found')
            elif len(contains_matches) > 1:
                logger.warning(f"Multiple contains matches for {exact_company_name}: {[m['cin'] for m in contains_matches]}")
                return (contains_matches[0]['cin'], 'multiple_matches')
            else:
                # No match found - log details for debugging
                logger.info(f"No match for {exact_company_name}")
                logger.info(f"  Query normalized: {query_normalized}")
                logger.info(f"  Query smart: {query_smart}")
                logger.info(f"  Found companies: {[m['name'] for m in matches]}")
                return (None, 'not_found')
                
        except Exception as e:
            logger.error(f"Error extracting CIN from ZaubaCorp HTML: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return (None, 'error')

