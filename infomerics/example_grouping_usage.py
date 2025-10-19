#!/usr/bin/env python3
"""
Example usage of the group_companies_instruments module.
Demonstrates how to programmatically use the grouping functionality.
"""

import json
from group_companies_instruments import load_json_data, group_by_company


def main():
    """Example usage of grouping functionality."""
    
    # Example 1: Load and group data
    print("Example 1: Basic grouping")
    print("-" * 80)
    
    input_file = "json_data/infomerics_2024-10-01_2024-10-15.json"
    data = load_json_data(input_file)
    grouped_data = group_by_company(data)
    
    print(f"Total companies: {len(grouped_data)}")
    print(f"Total records: {len(data)}")
    print()
    
    # Example 2: Get specific company data
    print("Example 2: Access specific company")
    print("-" * 80)
    
    # Get the first company as an example
    first_company_name = list(grouped_data.keys())[0]
    company_info = grouped_data[first_company_name]
    
    print(f"Company: {company_info['company_name']}")
    print(f"Number of instruments: {company_info['total_instruments']}")
    print(f"Dates: {', '.join(company_info['dates'])}")
    print(f"\nInstruments:")
    for idx, instrument in enumerate(company_info['instruments'], 1):
        print(f"  {idx}. {instrument['instrument_category']}")
        print(f"     Rating: {instrument['rating']}, Amount: {instrument['instrument_amount']}")
    print()
    
    # Example 3: Filter companies by number of instruments
    print("Example 3: Companies with multiple instruments")
    print("-" * 80)
    
    companies_with_multiple = {
        name: info for name, info in grouped_data.items()
        if info['total_instruments'] > 1
    }
    
    print(f"Companies with more than 1 instrument: {len(companies_with_multiple)}")
    for company_name, info in list(companies_with_multiple.items())[:5]:
        print(f"  - {company_name}: {info['total_instruments']} instruments")
    print()
    
    # Example 4: Group by instrument type
    print("Example 4: Group by instrument category")
    print("-" * 80)
    
    instrument_types = {}
    for company_info in grouped_data.values():
        for instrument in company_info['instruments']:
            category = instrument['instrument_category']
            if category not in instrument_types:
                instrument_types[category] = 0
            instrument_types[category] += 1
    
    # Sort by count
    sorted_types = sorted(instrument_types.items(), key=lambda x: x[1], reverse=True)
    print("Top instrument categories:")
    for category, count in sorted_types[:10]:
        print(f"  - {category}: {count}")
    print()
    
    # Example 5: Export specific company to JSON
    print("Example 5: Export specific company to JSON file")
    print("-" * 80)
    
    if first_company_name in grouped_data:
        output_file = f"example_company_export.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(grouped_data[first_company_name], f, indent=2, ensure_ascii=False)
        print(f"Exported '{first_company_name}' to {output_file}")
    

if __name__ == '__main__':
    main()

