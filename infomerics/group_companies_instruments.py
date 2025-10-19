#!/usr/bin/env python3
"""
Script to group companies with their instruments from Infomerics JSON data files.
This script reads a JSON file containing company rating data and groups all instruments
by company name, providing a structured view of each company's financial instruments.
"""

import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Load JSON data from file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        List of dictionaries containing company and instrument data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


def group_by_company(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Group instruments by company name.
    
    Args:
        data: List of dictionaries containing company and instrument data
        
    Returns:
        Dictionary with company names as keys and company info with instruments as values
    """
    grouped = defaultdict(lambda: {
        'company_name': '',
        'instruments': [],
        'total_instruments': 0,
        'dates': set(),
        'urls': set()
    })
    
    for entry in data:
        company_name = entry.get('company_name', 'Unknown Company')
        
        # Set company name if not already set
        if not grouped[company_name]['company_name']:
            grouped[company_name]['company_name'] = company_name
        
        # Add instrument details
        instrument = {
            'instrument_category': entry.get('instrument_category', 'N/A'),
            'rating': entry.get('rating', 'N/A'),
            'outlook': entry.get('outlook', 'N/A'),
            'instrument_amount': entry.get('instrument_amount', 'N/A'),
            'date': entry.get('date', 'N/A')
        }
        
        grouped[company_name]['instruments'].append(instrument)
        grouped[company_name]['dates'].add(entry.get('date', 'N/A'))
        
        if entry.get('url'):
            grouped[company_name]['urls'].add(entry.get('url'))
    
    # Convert sets to lists and count instruments
    for company in grouped.values():
        company['dates'] = sorted(list(company['dates']))
        company['urls'] = list(company['urls'])
        company['total_instruments'] = len(company['instruments'])
    
    return dict(grouped)


def save_grouped_data(grouped_data: Dict[str, Any], output_file: str, format_type: str = 'json'):
    """
    Save grouped data to file.
    
    Args:
        grouped_data: Dictionary of grouped company data
        output_file: Path to output file
        format_type: Output format ('json' or 'pretty')
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            if format_type == 'json':
                json.dump(grouped_data, f, indent=2, ensure_ascii=False)
            elif format_type == 'pretty':
                # Pretty text format
                for company_name, company_data in sorted(grouped_data.items()):
                    f.write(f"\n{'='*80}\n")
                    f.write(f"COMPANY: {company_name}\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"Total Instruments: {company_data['total_instruments']}\n")
                    f.write(f"Dates: {', '.join(company_data['dates'])}\n")
                    f.write(f"\nInstruments:\n")
                    f.write(f"{'-'*80}\n")
                    
                    for idx, instrument in enumerate(company_data['instruments'], 1):
                        f.write(f"\n  {idx}. {instrument['instrument_category']}\n")
                        f.write(f"     Rating: {instrument['rating']}\n")
                        f.write(f"     Outlook: {instrument['outlook']}\n")
                        f.write(f"     Amount: {instrument['instrument_amount']}\n")
                        f.write(f"     Date: {instrument['date']}\n")
                    
                    if company_data['urls']:
                        f.write(f"\nReferences:\n")
                        for url in company_data['urls']:
                            f.write(f"  - {url}\n")
                    
                    f.write(f"\n")
        
        print(f"Successfully saved grouped data to '{output_file}'")
    except Exception as e:
        print(f"Error saving file: {e}", file=sys.stderr)
        sys.exit(1)


def print_summary(grouped_data: Dict[str, Any]):
    """
    Print a summary of the grouped data.
    
    Args:
        grouped_data: Dictionary of grouped company data
    """
    total_companies = len(grouped_data)
    total_instruments = sum(company['total_instruments'] for company in grouped_data.values())
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total Companies: {total_companies}")
    print(f"Total Instruments: {total_instruments}")
    print(f"Average Instruments per Company: {total_instruments/total_companies:.2f}")
    
    # Top 10 companies by number of instruments
    sorted_companies = sorted(
        grouped_data.items(), 
        key=lambda x: x[1]['total_instruments'], 
        reverse=True
    )
    
    print(f"\nTop 10 Companies by Number of Instruments:")
    print(f"{'-'*80}")
    for idx, (company_name, company_data) in enumerate(sorted_companies[:10], 1):
        print(f"{idx:2}. {company_name}: {company_data['total_instruments']} instruments")
    print(f"{'='*80}\n")


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(
        description='Group companies with their instruments from Infomerics JSON data files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Group data and save as JSON
  python group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json
  
  # Save with custom output filename
  python group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -o grouped_output.json
  
  # Save in pretty text format
  python group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json -f pretty -o output.txt
  
  # Show summary without saving
  python group_companies_instruments.py json_data/infomerics_2024-10-01_2024-10-15.json --no-save
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Path to the input JSON file containing Infomerics data'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file path (default: <input_file>_grouped.json or .txt depending on format)',
        default=None
    )
    
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'pretty'],
        default='json',
        help='Output format: json (structured JSON) or pretty (human-readable text) (default: json)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Only print summary without saving output file'
    )
    
    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Skip printing summary'
    )
    
    args = parser.parse_args()
    
    # Load data
    print(f"Loading data from '{args.input_file}'...")
    data = load_json_data(args.input_file)
    print(f"Loaded {len(data)} records")
    
    # Group data
    print("Grouping companies with their instruments...")
    grouped_data = group_by_company(data)
    
    # Print summary
    if not args.no_summary:
        print_summary(grouped_data)
    
    # Save output
    if not args.no_save:
        if args.output:
            output_file = args.output
        else:
            # Generate default output filename
            input_path = Path(args.input_file)
            extension = '.json' if args.format == 'json' else '.txt'
            output_file = str(input_path.parent / f"{input_path.stem}_grouped{extension}")
        
        print(f"Saving grouped data...")
        save_grouped_data(grouped_data, output_file, args.format)


if __name__ == '__main__':
    main()

