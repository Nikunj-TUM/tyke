#!/usr/bin/env python3
"""
Script to extract company names, instrument categories, ratings, URLs, and dates
from the markdown file containing credit rating information.
"""

import re
import json
import csv
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


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


class CreditRatingExtractor:
    """Extract credit rating data from markdown content"""
    
    def __init__(self, markdown_file_path: str):
        self.markdown_file_path = markdown_file_path
        self.extracted_data: List[InstrumentData] = []
    
    def read_markdown_file(self) -> str:
        """Read the markdown file content"""
        try:
            with open(self.markdown_file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Markdown file not found: {self.markdown_file_path}")
        except Exception as e:
            raise Exception(f"Error reading file: {str(e)}")
    
    def extract_company_data(self) -> List[InstrumentData]:
        """Extract all company data from markdown content"""
        content = self.read_markdown_file()
        
        # Split content by company sections (marked with ### and literal \n)
        company_sections = re.split(r'\\n\\n### ', content)
        
        for section in company_sections[1:]:  # Skip first empty section
            self._process_company_section(section)
        
        return self.extracted_data
    
    def _process_company_section(self, section: str) -> None:
        """Process a single company section to extract instrument data"""
        # Extract company name (first part before first \\n\\n)
        company_name_match = re.match(r'^([^\\]+)', section)
        if not company_name_match:
            return
        
        company_name = company_name_match.group(1).strip()
        
        # Find all instrument blocks in this company section
        self._extract_instruments_from_section(company_name, section)
    
    def _extract_instruments_from_section(self, company_name: str, section: str) -> None:
        """Extract all instruments for a company from its section"""
        # Pattern to match instrument blocks more precisely
        # The data uses literal \n instead of actual line breaks
        instrument_pattern = r'Instrument Category\\n\\n(.+?)\\n\\nas on (.+?)\\n\\nRatings\\n\\n(.+?)\\n\\nOutlook\\n\\n(.+?)\\n\\nInstrument Amount\\n\\n(.*?)\\n\\n\[View Instrument\]\((.+?)\)'
        
        matches = re.findall(instrument_pattern, section, re.DOTALL)
        
        for match in matches:
            instrument_category = self._clean_text(match[0])
            date = self._clean_text(match[1])
            rating = self._clean_text(match[2])
            outlook = self._clean_text(match[3])
            # For amount, only take the first part before any additional text
            amount_raw = match[4]
            amount = self._extract_amount_only(amount_raw)
            url = match[5].strip()
            
            instrument_data = InstrumentData(
                company_name=self._clean_text(company_name),
                instrument_category=instrument_category,
                rating=rating,
                outlook=outlook,
                instrument_amount=amount,
                date=date,
                url=url
            )
            
            self.extracted_data.append(instrument_data)
    
    def _extract_amount_only(self, amount_text: str) -> str:
        """Extract only the amount part, stopping at first [View Instrument] or next Instrument Category"""
        if not amount_text:
            return ""
        
        # Clean the text first
        cleaned = self._clean_text(amount_text)
        
        # Stop at first [View Instrument] or [Bank lender
        stop_patterns = [r'\[View Instrument\]', r'\[Bank lender', r'Instrument Category']
        
        for pattern in stop_patterns:
            match = re.search(pattern, cleaned)
            if match:
                cleaned = cleaned[:match.start()].strip()
                break
        
        return cleaned
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing literal newlines and extra whitespace"""
        if not text:
            return ""
        
        # Replace literal \n with spaces and clean up
        cleaned = text.replace('\\n', ' ').strip()
        # Remove multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned
    
    def save_to_json(self, output_file: str = 'extracted_company_data.json') -> None:
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
    
    def save_to_csv(self, output_file: str = 'extracted_company_data.csv') -> None:
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
    
    def save_to_excel(self, output_file: str = 'extracted_company_data.xlsx') -> None:
        """Save extracted data to Excel file with additional analysis sheets"""
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
            
            # Save to Excel with multiple sheets
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='All Data', index=False)
                rating_analysis.to_excel(writer, sheet_name='Rating Analysis', index=False)
                company_analysis.to_excel(writer, sheet_name='Company Analysis', index=False)
                outlook_analysis.to_excel(writer, sheet_name='Outlook Analysis', index=False)
            
            print(f"Data saved to {output_file} with multiple analysis sheets")
            
        except ImportError:
            print("pandas and openpyxl not available. Skipping Excel export.")
            print("Install with: pip install pandas openpyxl")
    
    def print_summary(self) -> None:
        """Print summary of extracted data"""
        print(f"\n=== EXTRACTION SUMMARY ===")
        print(f"Total instruments extracted: {len(self.extracted_data)}")
        
        # Count unique companies
        unique_companies = set(item.company_name for item in self.extracted_data)
        print(f"Unique companies: {len(unique_companies)}")
        
        # Count by rating
        rating_counts = {}
        for item in self.extracted_data:
            rating = item.rating
            rating_counts[rating] = rating_counts.get(rating, 0) + 1
        
        print(f"\nRating distribution:")
        for rating, count in sorted(rating_counts.items()):
            print(f"  {rating}: {count}")
        
        print(f"\nSample data (first 3 records):")
        for i, item in enumerate(self.extracted_data[:3]):
            print(f"\n{i+1}. Company: {item.company_name}")
            print(f"   Category: {item.instrument_category}")
            print(f"   Rating: {item.rating}")
            print(f"   Date: {item.date}")
            print(f"   URL: {item.url}")


def main():
    """Main function to run the extraction"""
    try:
        # Initialize extractor
        extractor = CreditRatingExtractor('body_json_md.md')
        
        # Extract data
        print("Extracting company data from markdown file...")
        data = extractor.extract_company_data()
        
        if not data:
            print("No data extracted. Please check the markdown file format.")
            return
        
        # Print summary
        extractor.print_summary()
        
        # Save to different formats
        extractor.save_to_json()
        extractor.save_to_csv()
        extractor.save_to_excel()
        
        print(f"\n=== EXTRACTION COMPLETE ===")
        print(f"Files created:")
        print(f"- extracted_company_data.json")
        print(f"- extracted_company_data.csv")
        print(f"- extracted_company_data.xlsx (if pandas available)")
        
    except Exception as e:
        print(f"Error during extraction: {str(e)}")


if __name__ == "__main__":
    main()
