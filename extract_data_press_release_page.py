#!/usr/bin/env python3
"""
Script to extract company names, instrument categories, ratings, URLs, and dates
from the HTML content in the body field of a JSON file containing credit rating information from Infomerics.
"""

import re
import json
import csv
from typing import List, Dict, Any
from dataclasses import dataclass

# BeautifulSoup import
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("BeautifulSoup not available. Please install with: pip install beautifulsoup4")
    exit(1)

# Optional pandas import
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
    print("Pandas and numpy successfully imported")
except ImportError as e:
    PANDAS_AVAILABLE = False
    print(f"Pandas/numpy import failed: {e}")


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
    """Extract credit rating data from HTML content stored in JSON file using BeautifulSoup"""
    
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.extracted_data: List[InstrumentData] = []
    
    def read_html_from_json(self) -> str:
        """Read the HTML content from the body field of the JSON file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)
                
            # Extract HTML from the body field
            if 'body' not in json_data:
                raise ValueError("JSON file does not contain a 'body' field")
                
            html_content = json_data['body']
            if not html_content:
                raise ValueError("Body field is empty")
                
            return html_content
            
        except FileNotFoundError:
            raise FileNotFoundError(f"JSON file not found: {self.json_file_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            raise Exception(f"Error reading JSON file: {str(e)}")
    
    def extract_company_data(self) -> List[InstrumentData]:
        """Extract all company data from HTML content using BeautifulSoup"""
        html_content = self.read_html_from_json()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        print(f"HTML file size: {len(html_content)} characters")
        
        # The HTML has malformed class attributes with escaped quotes
        # Find all h3 elements that contain company names
        all_h3 = soup.find_all('h3')
        print(f"Found {len(all_h3)} h3 elements total")
        
        # Filter h3 elements that look like company names
        company_headers = []
        for h3 in all_h3:
            text = h3.get_text().strip()
            # Company names typically end with Limited, LLP, Private Limited, etc.
            if any(suffix in text for suffix in ['Limited', 'LLP', 'Private', 'Company']):
                company_headers.append(h3)
        
        print(f"Found {len(company_headers)} company headers")
        
        for i, header in enumerate(company_headers):
            company_name = self._clean_text(header.get_text())
            print(f"\nProcessing company {i+1}: {company_name}")
            
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
        
        print(f"  Found {instrument_count} instruments for {company_name}")
    
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
                    print(f"    Skipping duplicate entry for {category}")
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
                print(f"    ✓ Added: {category}")
                print(f"      Rating: {rating}")
                print(f"      Outlook: {outlook}")
                print(f"      Amount: {amount}")
                print(f"      Date: {date}")
                print(f"      URL: {url[:60]}..." if len(url) > 60 else f"      URL: {url}")
                return True
            
            return False
            
        except Exception as e:
            print(f"    Error extracting instrument data: {str(e)}")
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
    
    def save_to_json(self, output_file: str = 'extracted_html_company_data.json') -> None:
        """Save extracted data to JSON file"""
        data_dict = []
        for item in self.extracted_data:
            data_dict.append({
                'company_name': item.company_name,
                'instrument_category': item.instrument_category,
                'rating': item.rating,
                'outlook': item.outlook,
                'instrument_amount': item.instrument_amount,
                'date': item.date,
                'url': item.url
            })
        
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(data_dict, file, indent=2, ensure_ascii=False)
        
        print(f"Data saved to {output_file}")
    
    def save_to_csv(self, output_file: str = 'extracted_html_company_data.csv') -> None:
        """Save extracted data to CSV file"""
        if not self.extracted_data:
            print("No data to save")
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Write header
            writer.writerow([
                'Company Name',
                'Instrument Category', 
                'Rating',
                'Outlook',
                'Instrument Amount',
                'Date',
                'URL'
            ])
            
            # Write data
            for item in self.extracted_data:
                writer.writerow([
                    item.company_name,
                    item.instrument_category,
                    item.rating,
                    item.outlook,
                    item.instrument_amount,
                    item.date,
                    item.url
                ])
        
        print(f"Data saved to {output_file}")
    
    def save_to_excel(self, output_file: str = 'extracted_html_company_data.xlsx') -> None:
        """Save extracted data to Excel file with additional analysis sheets"""
        if not PANDAS_AVAILABLE:
            print("pandas not available. Skipping Excel export.")
            print("Install with: pip install pandas openpyxl")
            return
            
        try:
            import pandas as pd
            
            # Create main data DataFrame
            data_dict = []
            for item in self.extracted_data:
                data_dict.append({
                    'Company Name': item.company_name,
                    'Instrument Category': item.instrument_category,
                    'Rating': item.rating,
                    'Outlook': item.outlook,
                    'Instrument Amount': item.instrument_amount,
                    'Date': item.date,
                    'URL': item.url
                })
            
            df = pd.DataFrame(data_dict)
            
            # Create analysis DataFrames
            rating_analysis = df['Rating'].value_counts().reset_index()
            rating_analysis.columns = ['Rating', 'Count']
            
            company_analysis = df['Company Name'].value_counts().reset_index()
            company_analysis.columns = ['Company Name', 'Number of Instruments']
            
            outlook_analysis = df['Outlook'].value_counts().reset_index()
            outlook_analysis.columns = ['Outlook', 'Count']
            
            category_analysis = df['Instrument Category'].value_counts().reset_index()
            category_analysis.columns = ['Instrument Category', 'Count']
            
            # Save to Excel with multiple sheets
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='All Data', index=False)
                rating_analysis.to_excel(writer, sheet_name='Rating Analysis', index=False)
                company_analysis.to_excel(writer, sheet_name='Company Analysis', index=False)
                outlook_analysis.to_excel(writer, sheet_name='Outlook Analysis', index=False)
                category_analysis.to_excel(writer, sheet_name='Category Analysis', index=False)
            
            print(f"Data saved to {output_file} with multiple analysis sheets")
            
        except ImportError as e:
            print(f"Excel export failed: {e}")
            print("Install with: pip install pandas openpyxl")
    
    def print_summary(self) -> None:
        """Print summary of extracted data"""
        print(f"\n=== HTML EXTRACTION SUMMARY ===")
        print(f"Total instruments extracted: {len(self.extracted_data)}")
        
        # Count unique companies
        unique_companies = set(item.company_name for item in self.extracted_data)
        print(f"Unique companies: {len(unique_companies)}")
        
        # Count by rating
        rating_counts = {}
        for item in self.extracted_data:
            rating = item.rating
            rating_counts[rating] = rating_counts.get(rating, 0) + 1
        
        print(f"\nRating distribution (top 10):")
        for rating, count in sorted(rating_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {rating}: {count}")
        
        # Count by outlook
        outlook_counts = {}
        for item in self.extracted_data:
            outlook = item.outlook
            outlook_counts[outlook] = outlook_counts.get(outlook, 0) + 1
        
        print(f"\nOutlook distribution:")
        for outlook, count in sorted(outlook_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {outlook}: {count}")
        
        # Count URLs found
        urls_found = sum(1 for item in self.extracted_data if item.url != "Not found")
        print(f"\nURLs found: {urls_found}/{len(self.extracted_data)}")
        
        # Count amounts found
        amounts_found = sum(1 for item in self.extracted_data if item.instrument_amount != "Not found")
        print(f"Amounts found: {amounts_found}/{len(self.extracted_data)}")
        
        # Count dates found
        dates_found = sum(1 for item in self.extracted_data if item.date != "Not found")
        print(f"Dates found: {dates_found}/{len(self.extracted_data)}")
        
        print(f"\nSample data (first 3 records):")
        for i, item in enumerate(self.extracted_data[:3]):
            print(f"\n{i+1}. Company: {item.company_name}")
            print(f"   Category: {item.instrument_category}")
            print(f"   Rating: {item.rating}")
            print(f"   Outlook: {item.outlook}")
            print(f"   Amount: {item.instrument_amount}")
            print(f"   Date: {item.date}")
            print(f"   URL: {item.url[:50]}..." if len(item.url) > 50 else f"   URL: {item.url}")


def main():
    """Main function to run the extraction"""
    try:
        # Initialize extractor with JSON file
        extractor = HTMLCreditRatingExtractor('bright_data_response_json_.json')
        
        # Extract data
        print("Extracting company data from JSON file using BeautifulSoup...")
        data = extractor.extract_company_data()
        
        if not data:
            print("No data extracted. Please check the JSON file format.")
            return
        
        # Print summary
        extractor.print_summary()
        
        # Save to different formats
        extractor.save_to_json()
        extractor.save_to_csv()
        extractor.save_to_excel()
        
        print(f"\n=== EXTRACTION COMPLETE ===")
        print(f"Files created:")
        print(f"- extracted_html_company_data.json")
        print(f"- extracted_html_company_data.csv")
        print(f"- extracted_html_company_data.xlsx (if pandas available)")
        
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
 