#!/usr/bin/env python3
"""
Script to combine all CSV files in csv_data directory into a single CSV file
Uses built-in csv module instead of pandas to avoid dependency issues
"""

import os
import csv
import glob
from datetime import datetime
from collections import defaultdict, Counter

def combine_csv_files(csv_directory: str, output_filename: str = None):
    """
    Combine all CSV files in the specified directory into a single CSV file
    
    Args:
        csv_directory: Path to directory containing CSV files
        output_filename: Name of output file (optional)
    """
    
    # Get all CSV files in the directory
    csv_pattern = os.path.join(csv_directory, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
    
    print(f"Found {len(csv_files)} CSV files to combine:")
    
    # Sort files by name to ensure chronological order
    csv_files.sort()
    
    # Generate output filename if not provided
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"infomerics_combined_{timestamp}.csv"
    
    output_path = output_filename
    
    # Variables for tracking
    total_records = 0
    header_written = False
    headers = None
    company_counter = Counter()
    rating_counter = Counter()
    dates_found = []
    
    # Open output file for writing
    with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
        writer = None
        
        for i, csv_file in enumerate(csv_files, 1):
            filename = os.path.basename(csv_file)
            print(f"[{i:2d}/{len(csv_files)}] Processing {filename}...")
            
            try:
                with open(csv_file, 'r', encoding='utf-8') as infile:
                    reader = csv.reader(infile)
                    
                    # Read header
                    file_headers = next(reader, None)
                    if file_headers is None:
                        print(f"    ❌ Empty file: {filename}")
                        continue
                    
                    # Initialize writer with headers from first file
                    if not header_written:
                        headers = file_headers + ['source_file']  # Add source_file column
                        writer = csv.writer(outfile)
                        writer.writerow(headers)
                        header_written = True
                    
                    # Check if headers match (excluding source_file)
                    if file_headers != headers[:-1]:
                        print(f"    ⚠️  Header mismatch in {filename}, attempting to align...")
                    
                    # Read and write data rows
                    file_record_count = 0
                    for row in reader:
                        if row:  # Skip empty rows
                            # Add source file name
                            row_with_source = row + [filename]
                            writer.writerow(row_with_source)
                            file_record_count += 1
                            total_records += 1
                            
                            # Collect statistics (assuming standard column positions)
                            if len(row) > 0 and len(headers) > 0:
                                # Try to find company name (first column usually)
                                company_counter[row[0]] += 1
                                
                                # Try to find rating (assuming it's in column 2)
                                if len(row) > 2:
                                    rating_counter[row[2]] += 1
                                
                                # Try to find date (assuming it's in column 5)
                                if len(row) > 5:
                                    dates_found.append(row[5])
                    
                    print(f"    ✓ Added {file_record_count} records")
                    
            except Exception as e:
                print(f"    ❌ Error reading {filename}: {str(e)}")
                continue
    
    if total_records == 0:
        print("No data to combine!")
        return
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"COMBINATION COMPLETE")
    print(f"{'='*60}")
    print(f"Input files: {len(csv_files)}")
    print(f"Total records: {total_records:,}")
    print(f"Output file: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
    
    # Show column info
    if headers:
        print(f"\nColumns in combined dataset ({len(headers)}):")
        for i, col in enumerate(headers):
            print(f"  {i+1:2d}. {col}")
    
    # Show date range (basic analysis)
    if dates_found:
        unique_dates = set(dates_found)
        print(f"\nDate analysis:")
        print(f"  Unique dates found: {len(unique_dates)}")
        sorted_dates = sorted(unique_dates)
        if len(sorted_dates) >= 2:
            print(f"  Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    
    # Show top companies by number of instruments
    if company_counter:
        print(f"\nTop 10 companies by number of instruments:")
        for company, count in company_counter.most_common(10):
            print(f"  {count:3d} - {company}")
    
    # Show rating distribution
    if rating_counter:
        print(f"\nTop 10 ratings by frequency:")
        for rating, count in rating_counter.most_common(10):
            print(f"  {count:3d} - {rating}")
    
    print(f"\n✅ Combined CSV saved as: {output_path}")
    return output_path

def main():
    """Main function"""
    
    # Set paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_directory = os.path.join(script_dir, "csv_data")
    
    # Check if csv_data directory exists
    if not os.path.exists(csv_directory):
        print(f"Error: Directory {csv_directory} does not exist!")
        return
    
    # Combine CSV files
    output_file = combine_csv_files(csv_directory)
    
    if output_file:
        print(f"\n🎉 Success! All CSV files combined into: {output_file}")

if __name__ == "__main__":
    main()
