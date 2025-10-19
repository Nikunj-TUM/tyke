#!/usr/bin/env python3
"""
Example script showing how to use the Infomerics scraper programmatically
Splits a given date range into 15-day intervals for efficient scraping
"""

from scrape_press_release_page import main
from datetime import datetime, timedelta
import sys
import time

def generate_15_day_intervals(start_date: str, end_date: str):
    """
    Generate 15-day intervals between start_date and end_date
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of (from_date, to_date) tuples in YYYY-MM-DD format
    """
    try:
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start > end:
            raise ValueError("Start date must be before or equal to end date")
        
        intervals = []
        current_start = start
        
        while current_start <= end:
            # Calculate the end of the current 15-day interval
            current_end = min(current_start + timedelta(days=14), end)
            
            # Add the interval
            intervals.append((
                current_start.strftime('%Y-%m-%d'),
                current_end.strftime('%Y-%m-%d')
            ))
            
            # Move to the next interval (start from the day after current_end)
            current_start = current_end + timedelta(days=1)
        
        return intervals
        
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD format. Error: {str(e)}")
        else:
            raise e

def scrape_date_range_in_intervals(start_date: str, end_date: str, delay_seconds: int = 2):
    """
    Scrape a date range by splitting it into 15-day intervals
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        delay_seconds: Delay between requests in seconds (default: 2)
    """
    try:
        # Generate 15-day intervals
        intervals = generate_15_day_intervals(start_date, end_date)
        
        print(f"{'='*60}")
        print(f"SCRAPING DATE RANGE: {start_date} to {end_date}")
        print(f"Split into {len(intervals)} intervals of 15 days each")
        print(f"{'='*60}")
        
        successful_scrapes = 0
        failed_scrapes = 0
        
        for i, (from_date, to_date) in enumerate(intervals, 1):
            print(f"\n[{i}/{len(intervals)}] Scraping interval: {from_date} to {to_date}")
            print(f"{'-'*50}")
            
            try:
                main(from_date, to_date)
                print(f"✅ Successfully scraped {from_date} to {to_date}")
                successful_scrapes += 1
                
            except Exception as e:
                print(f"❌ Failed to scrape {from_date} to {to_date}: {str(e)}")
                failed_scrapes += 1
            
            # Add delay between requests to be respectful to the server
            if i < len(intervals):  # Don't delay after the last request
                print(f"Waiting {delay_seconds} seconds before next request...")
                time.sleep(delay_seconds)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Total intervals: {len(intervals)}")
        print(f"Successful: {successful_scrapes}")
        print(f"Failed: {failed_scrapes}")
        print(f"Success rate: {(successful_scrapes/len(intervals)*100):.1f}%")
        
        if failed_scrapes == 0:
            print("🎉 All intervals scraped successfully!")
        
    except Exception as e:
        print(f"Error in scrape_date_range_in_intervals: {str(e)}")

def main_cli():
    """Command line interface for the scraper"""
    if len(sys.argv) != 3:
        print("Usage: python example_usage.py <start_date> <end_date>")
        print("Date format: YYYY-MM-DD")
        print("Example: python example_usage.py 2025-09-01 2025-10-31")
        sys.exit(1)
    
    start_date = sys.argv[1]
    end_date = sys.argv[2]
    
    try:
        scrape_date_range_in_intervals(start_date, end_date)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

# Example usage for testing different scenarios
def example_usage():
    """Example of different usage scenarios"""
    
    # Example 1: Short range (within 15 days)
    print("Example 1: Short range (single interval)")
    scrape_date_range_in_intervals("2025-10-01", "2025-10-10")
    
    # Example 2: Medium range (multiple intervals)
    print("\nExample 2: Medium range (multiple intervals)")
    scrape_date_range_in_intervals("2025-09-01", "2025-10-15")
    
    # Example 3: Long range (many intervals)
    print("\nExample 3: Long range (many intervals)")
    scrape_date_range_in_intervals("2025-08-01", "2025-10-31")

if __name__ == "__main__":
    # If command line arguments are provided, use CLI mode
    if len(sys.argv) > 1:
        main_cli()
    else:
        # Otherwise, show usage examples
        print("No arguments provided. Here are some usage examples:")
        print("\nCommand line usage:")
        print("python example_usage.py 2025-09-01 2025-10-31")
        print("\nOr uncomment the line below to run example scenarios:")
        # example_usage()  # Uncomment this line to run examples
