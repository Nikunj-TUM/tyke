#!/usr/bin/env python3
"""
Debug script to test duplicate detection with real Airtable data
This helps diagnose why duplicates might still be created
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from api.airtable_client import AirtableClient
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def debug_duplicate_check():
    """Debug the duplicate checking mechanism"""
    print("\n" + "="*80)
    print("Debugging Duplicate Detection")
    print("="*80 + "\n")
    
    # Initialize client
    print("1. Initializing Airtable client (no Redis cache for clarity)...")
    client = AirtableClient(use_redis_cache=False)
    print("   ✓ Client initialized\n")
    
    # Fetch some existing ratings from Airtable
    print("2. Fetching existing ratings from Airtable...")
    try:
        # Get first 5 ratings
        existing_ratings = client.credit_ratings_table.all(max_records=5)
        
        if not existing_ratings:
            print("   ✗ No existing ratings found in Airtable!")
            print("   Please create some ratings first by running the scraper.\n")
            return
        
        print(f"   ✓ Found {len(existing_ratings)} ratings\n")
        
        # Display and test each rating
        for i, record in enumerate(existing_ratings, 1):
            fields = record.get('fields', {})
            record_id = record['id']
            
            # Extract fields
            rating = fields.get('Rating', 'N/A')
            instrument = fields.get('Instrument', 'N/A')
            date = fields.get('Date', 'N/A')
            company_links = fields.get('Company', [])
            
            print(f"\n--- Testing Rating #{i} ---")
            print(f"Record ID: {record_id}")
            print(f"Rating: {rating}")
            print(f"Instrument: {instrument}")
            print(f"Date: {date}")
            print(f"Company Links: {company_links}")
            
            if not company_links:
                print("⚠️  WARNING: No company link found for this rating!")
                continue
            
            company_id = company_links[0]
            
            # Now test if our duplicate check can find this rating
            print(f"\n→ Testing duplicate check for this exact rating...")
            is_duplicate = client.check_duplicate_rating(
                company_record_id=company_id,
                instrument=instrument,
                rating=rating,
                date=date
            )
            
            if is_duplicate:
                print("✓ SUCCESS: Duplicate correctly detected!")
            else:
                print("✗ FAILURE: Duplicate NOT detected (this is the bug!)")
                print("\nDebugging info:")
                print(f"  - Company ID used: {company_id}")
                print(f"  - Rating: {rating}")
                print(f"  - Instrument: {instrument}")
                print(f"  - Date: {date}")
                
                # Try to manually query
                print("\n  Attempting manual query...")
                escaped_rating = client._escape_formula_string(rating)
                escaped_instrument = client._escape_formula_string(instrument)
                parsed_date = client._parse_date(date)
                
                formula = (
                    f"AND("
                    f"{{Rating}} = '{escaped_rating}', "
                    f"{{Instrument}} = '{escaped_instrument}', "
                    f"{{Date}} = '{parsed_date}'"
                    f")"
                )
                print(f"  Formula: {formula}")
                
                manual_records = client.credit_ratings_table.all(formula=formula)
                print(f"  Records found: {len(manual_records)}")
                
                for mr in manual_records:
                    mr_fields = mr.get('fields', {})
                    mr_companies = mr_fields.get('Company', [])
                    print(f"    - Record {mr['id']}: Company links = {mr_companies}")
                    print(f"      Does it contain our company {company_id}? {company_id in mr_companies}")
        
        print("\n" + "="*80)
        print("Debug Complete")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Error during debug: {e}", exc_info=True)


def test_specific_case():
    """Test a specific company/rating combination"""
    print("\n" + "="*80)
    print("Test Specific Rating Case")
    print("="*80 + "\n")
    
    # You can modify these values to test specific cases
    TEST_COMPANY_ID = input("Enter Company Record ID (e.g., recXXXXXX): ").strip()
    TEST_INSTRUMENT = input("Enter Instrument: ").strip()
    TEST_RATING = input("Enter Rating: ").strip()
    TEST_DATE = input("Enter Date (YYYY-MM-DD): ").strip()
    
    if not all([TEST_COMPANY_ID, TEST_INSTRUMENT, TEST_RATING, TEST_DATE]):
        print("All fields are required!")
        return
    
    client = AirtableClient(use_redis_cache=False)
    
    print(f"\nChecking for duplicate:")
    print(f"  Company: {TEST_COMPANY_ID}")
    print(f"  Instrument: {TEST_INSTRUMENT}")
    print(f"  Rating: {TEST_RATING}")
    print(f"  Date: {TEST_DATE}")
    
    is_duplicate = client.check_duplicate_rating(
        company_record_id=TEST_COMPANY_ID,
        instrument=TEST_INSTRUMENT,
        rating=TEST_RATING,
        date=TEST_DATE
    )
    
    print(f"\nResult: {'DUPLICATE FOUND' if is_duplicate else 'NO DUPLICATE (would create new)'}")
    print()


def main():
    """Main menu"""
    try:
        print("\nDuplicate Detection Debug Tool")
        print("1. Test with existing Airtable data")
        print("2. Test specific rating case")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            debug_duplicate_check()
        elif choice == '2':
            test_specific_case()
        elif choice == '3':
            print("Exiting...")
            return
        else:
            print("Invalid choice!")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    main()

