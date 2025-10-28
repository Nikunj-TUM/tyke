#!/usr/bin/env python3
"""
Test script to verify the duplicate ratings fix
Run this script to test the duplicate detection functionality
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from api.airtable_client import AirtableClient
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_duplicate_detection():
    """Test the duplicate detection functionality"""
    print("\n" + "="*80)
    print("Testing Duplicate Rating Detection")
    print("="*80 + "\n")
    
    # Initialize client
    print("1. Initializing Airtable client...")
    client = AirtableClient(use_redis_cache=False)  # Disable Redis for simplicity
    print("   ✓ Client initialized\n")
    
    # Test data - create a simple rating
    test_company = "Test Company Limited - " + datetime.now().strftime("%Y%m%d%H%M%S")
    test_ratings = [
        {
            'company_name': test_company,
            'instrument_category': 'Long Term Loan',
            'rating': 'AA-',
            'outlook': 'Stable',
            'instrument_amount': 'Rs. 100 Cr.',
            'date': '2025-10-15',
            'url': 'https://test.com/rating1.pdf'
        }
    ]
    
    print(f"2. Creating test rating for '{test_company}'...")
    companies_created, ratings_created = client.batch_create_ratings(test_ratings)
    print(f"   ✓ First run: {companies_created} companies, {ratings_created} ratings created\n")
    
    if ratings_created != 1:
        print("   ✗ ERROR: Expected 1 rating to be created, got", ratings_created)
        return False
    
    # Try to create the same rating again (should be detected as duplicate)
    print("3. Attempting to create the same rating again (should detect duplicate)...")
    companies_created2, ratings_created2 = client.batch_create_ratings(test_ratings)
    print(f"   ✓ Second run: {companies_created2} companies, {ratings_created2} ratings created\n")
    
    if ratings_created2 != 0:
        print(f"   ✗ ERROR: Expected 0 ratings to be created (duplicate), got {ratings_created2}")
        print("   This means the duplicate detection is NOT working correctly!")
        return False
    else:
        print("   ✓ SUCCESS: Duplicate was correctly detected and prevented!\n")
    
    print("4. Testing with slightly different rating (should create new)...")
    test_ratings_different = [
        {
            'company_name': test_company,
            'instrument_category': 'Short Term Loan',  # Different instrument
            'rating': 'AA-',
            'outlook': 'Stable',
            'instrument_amount': 'Rs. 50 Cr.',
            'date': '2025-10-15',
            'url': 'https://test.com/rating2.pdf'
        }
    ]
    companies_created3, ratings_created3 = client.batch_create_ratings(test_ratings_different)
    print(f"   ✓ Third run: {companies_created3} companies, {ratings_created3} ratings created\n")
    
    if ratings_created3 != 1:
        print(f"   ✗ ERROR: Expected 1 rating to be created (different instrument), got {ratings_created3}")
        return False
    else:
        print("   ✓ SUCCESS: Different rating was correctly created!\n")
    
    print("5. Testing special characters in rating...")
    test_ratings_special = [
        {
            'company_name': test_company,
            'instrument_category': "Bank's Guarantee",  # Has apostrophe
            'rating': 'A1+',  # Has plus sign
            'outlook': 'Positive',
            'instrument_amount': 'Rs. 75 Cr.',
            'date': '2025-10-16',
            'url': 'https://test.com/rating3.pdf'
        }
    ]
    companies_created4, ratings_created4 = client.batch_create_ratings(test_ratings_special)
    print(f"   ✓ Fourth run: {companies_created4} companies, {ratings_created4} ratings created\n")
    
    if ratings_created4 != 1:
        print(f"   ✗ ERROR: Expected 1 rating with special chars, got {ratings_created4}")
        return False
    
    # Try duplicate with special chars
    companies_created5, ratings_created5 = client.batch_create_ratings(test_ratings_special)
    print(f"   ✓ Fifth run (duplicate with special chars): {companies_created5} companies, {ratings_created5} ratings created\n")
    
    if ratings_created5 != 0:
        print(f"   ✗ ERROR: Special char duplicate not detected, got {ratings_created5}")
        return False
    else:
        print("   ✓ SUCCESS: Special character duplicate was correctly detected!\n")
    
    print("="*80)
    print("ALL TESTS PASSED! ✓")
    print("="*80)
    print("\nSummary:")
    print("- Duplicate detection is working correctly")
    print("- Same ratings are properly identified and skipped")
    print("- Different ratings are correctly created")
    print("- Special characters are handled properly")
    print(f"\nTest company '{test_company}' was created with 3 ratings.")
    print("You can verify in Airtable that no duplicates were created.")
    print("\n")
    return True


def test_formula_escaping():
    """Test the formula string escaping"""
    print("\n" + "="*80)
    print("Testing Formula String Escaping")
    print("="*80 + "\n")
    
    client = AirtableClient(use_redis_cache=False)
    
    test_cases = [
        ("Simple rating", "Simple rating"),
        ("Rating with 'quotes'", "Rating with ''quotes''"),
        ("O'Brien & Co.", "O''Brien & Co."),
        ("AA-", "AA-"),
        ("", ""),
    ]
    
    all_passed = True
    for input_val, expected in test_cases:
        result = client._escape_formula_string(input_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: '{input_val}'")
        print(f"  Expected: '{expected}'")
        print(f"  Got:      '{result}'")
        if result != expected:
            all_passed = False
        print()
    
    if all_passed:
        print("="*80)
        print("ALL ESCAPING TESTS PASSED! ✓")
        print("="*80 + "\n")
    else:
        print("="*80)
        print("SOME ESCAPING TESTS FAILED! ✗")
        print("="*80 + "\n")
    
    return all_passed


def main():
    """Main test runner"""
    try:
        # Check environment variables
        if not os.getenv('AIRTABLE_API_KEY'):
            print("\n✗ ERROR: AIRTABLE_API_KEY environment variable not set")
            print("Please set it in your .env file or export it:")
            print("  export AIRTABLE_API_KEY='your-api-key'\n")
            sys.exit(1)
        
        if not os.getenv('AIRTABLE_BASE_ID'):
            print("\n✗ ERROR: AIRTABLE_BASE_ID environment variable not set")
            print("Please set it in your .env file or export it:")
            print("  export AIRTABLE_BASE_ID='your-base-id'\n")
            sys.exit(1)
        
        # Run tests
        print("\nStarting Duplicate Rating Fix Tests...")
        print("This will create test data in your Airtable base.\n")
        
        input("Press Enter to continue or Ctrl+C to cancel...")
        
        escaping_passed = test_formula_escaping()
        detection_passed = test_duplicate_detection()
        
        if escaping_passed and detection_passed:
            print("\n" + "="*80)
            print("SUCCESS! All tests passed. The duplicate fix is working correctly.")
            print("="*80 + "\n")
            sys.exit(0)
        else:
            print("\n" + "="*80)
            print("FAILURE! Some tests failed. Please check the output above.")
            print("="*80 + "\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

