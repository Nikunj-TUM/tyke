#!/usr/bin/env python3
"""
Integration test for PostgreSQL deduplication system
Tests the complete flow: insert -> dedupe -> sync to Airtable
"""
import sys
import os
from datetime import datetime

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from api.database import (
    init_database,
    insert_rating_with_deduplication,
    batch_insert_ratings,
    get_unsynced_ratings,
    get_company_airtable_id,
    update_company_airtable_id,
    update_ratings_airtable_ids,
    get_duplicate_stats,
    close_connection_pool
)
from api.airtable_client import AirtableClient
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80 + "\n")


def test_database_initialization():
    """Test 1: Database initialization"""
    print_header("TEST 1: Database Initialization")
    
    try:
        result = init_database()
        if result:
            print("✓ Database initialized successfully")
            return True
        else:
            print("⚠ Database already initialized or migration file not found")
            return True
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False


def test_insert_with_deduplication():
    """Test 2: Insert rating with automatic deduplication"""
    print_header("TEST 2: Insert with Deduplication")
    
    # Test data
    test_job_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_company = f"Test Company Ltd - {datetime.now().strftime('%H%M%S')}"
    
    test_rating = {
        'company_name': test_company,
        'instrument': 'Long Term Loan',
        'rating': 'AA-',
        'outlook': 'Stable',
        'instrument_amount': 'Rs. 100 Cr.',
        'date': '2025-10-15',
        'source_url': 'https://test.com/rating1.pdf'
    }
    
    try:
        # First insert - should succeed
        is_new, record_id = insert_rating_with_deduplication(
            company_name=test_rating['company_name'],
            instrument=test_rating['instrument'],
            rating=test_rating['rating'],
            outlook=test_rating['outlook'],
            instrument_amount=test_rating['instrument_amount'],
            date=test_rating['date'],
            source_url=test_rating['source_url'],
            job_id=test_job_id
        )
        
        if is_new and record_id:
            print(f"✓ First insert successful: Record ID {record_id}")
        else:
            print("✗ First insert failed")
            return False
        
        # Second insert - should detect duplicate
        is_new2, record_id2 = insert_rating_with_deduplication(
            company_name=test_rating['company_name'],
            instrument=test_rating['instrument'],
            rating=test_rating['rating'],
            outlook=test_rating['outlook'],
            instrument_amount=test_rating['instrument_amount'],
            date=test_rating['date'],
            source_url=test_rating['source_url'],
            job_id=test_job_id
        )
        
        if not is_new2 and record_id2 is None:
            print("✓ Duplicate detected correctly (second insert prevented)")
        else:
            print("✗ Duplicate detection failed - second insert succeeded when it shouldn't")
            return False
        
        # Insert with different instrument - should succeed
        is_new3, record_id3 = insert_rating_with_deduplication(
            company_name=test_rating['company_name'],
            instrument='Short Term Loan',  # Different
            rating=test_rating['rating'],
            outlook=test_rating['outlook'],
            instrument_amount='Rs. 50 Cr.',
            date=test_rating['date'],
            source_url=test_rating['source_url'],
            job_id=test_job_id
        )
        
        if is_new3 and record_id3:
            print(f"✓ Different instrument inserted successfully: Record ID {record_id3}")
        else:
            print("✗ Different instrument insert failed")
            return False
        
        print("\n✓ All deduplication tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_insert():
    """Test 3: Batch insert with duplicates"""
    print_header("TEST 3: Batch Insert with Duplicates")
    
    test_job_id = f"test_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_company = f"Batch Test Company - {datetime.now().strftime('%H%M%S')}"
    
    # Create batch with some duplicates
    batch_data = [
        {
            'company_name': test_company,
            'instrument_category': 'Long Term Loan',
            'rating': 'A+',
            'outlook': 'Stable',
            'instrument_amount': 'Rs. 200 Cr.',
            'date': '2025-10-20',
            'url': 'https://test.com/rating_batch1.pdf'
        },
        {
            'company_name': test_company,
            'instrument_category': 'Long Term Loan',  # Duplicate
            'rating': 'A+',
            'outlook': 'Stable',
            'instrument_amount': 'Rs. 200 Cr.',
            'date': '2025-10-20',
            'url': 'https://test.com/rating_batch1.pdf'
        },
        {
            'company_name': test_company,
            'instrument_category': 'Short Term Loan',  # Different
            'rating': 'A1+',
            'outlook': 'Positive',
            'instrument_amount': 'Rs. 100 Cr.',
            'date': '2025-10-20',
            'url': 'https://test.com/rating_batch2.pdf'
        },
        {
            'company_name': test_company,
            'instrument_category': 'Long Term Loan',  # Another duplicate
            'rating': 'A+',
            'outlook': 'Stable',
            'instrument_amount': 'Rs. 200 Cr.',
            'date': '2025-10-20',
            'url': 'https://test.com/rating_batch1.pdf'
        }
    ]
    
    try:
        new_count, dup_count = batch_insert_ratings(batch_data, test_job_id)
        
        print(f"Batch insert results:")
        print(f"  - New records: {new_count}")
        print(f"  - Duplicates skipped: {dup_count}")
        
        # Should be 2 new (Long Term + Short Term), 2 duplicates
        if new_count == 2 and dup_count == 2:
            print("✓ Batch insert handled duplicates correctly")
            return True
        else:
            print(f"✗ Expected 2 new and 2 duplicates, got {new_count} new and {dup_count} duplicates")
            return False
        
    except Exception as e:
        print(f"✗ Batch insert test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_airtable_sync():
    """Test 4: Sync to Airtable (requires Airtable credentials)"""
    print_header("TEST 4: Airtable Sync")
    
    # Check if Airtable is configured
    from api.config import settings
    if not settings.AIRTABLE_API_KEY or settings.AIRTABLE_API_KEY == "your_airtable_api_key_here":
        print("⚠ Skipping Airtable sync test - no credentials configured")
        return True
    
    test_job_id = f"test_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_company = f"Sync Test Company - {datetime.now().strftime('%H%M%S')}"
    
    try:
        # Insert a test rating
        is_new, record_id = insert_rating_with_deduplication(
            company_name=test_company,
            instrument='Term Loan',
            rating='BBB+',
            outlook='Stable',
            instrument_amount='Rs. 150 Cr.',
            date='2025-10-25',
            source_url='https://test.com/sync_test.pdf',
            job_id=test_job_id
        )
        
        if not is_new:
            print("✗ Failed to insert test rating")
            return False
        
        print(f"✓ Inserted test rating (ID: {record_id})")
        
        # Get unsynced ratings
        unsynced = get_unsynced_ratings(test_job_id)
        print(f"✓ Found {len(unsynced)} unsynced ratings")
        
        if len(unsynced) == 0:
            print("✗ No unsynced ratings found")
            return False
        
        # Sync to Airtable
        airtable_client = AirtableClient()
        
        # Check if company exists in Airtable
        company_airtable_id = get_company_airtable_id(test_company)
        
        if not company_airtable_id:
            # Create in Airtable
            company_airtable_id = airtable_client.upsert_company(test_company)
            update_company_airtable_id(test_company, company_airtable_id)
            print(f"✓ Created company in Airtable: {company_airtable_id}")
        else:
            print(f"✓ Company already exists in Airtable: {company_airtable_id}")
        
        # Create rating in Airtable
        rating = unsynced[0]
        fields = {
            "Company": [company_airtable_id],
            "Instrument": rating['instrument'],
            "Rating": rating['rating'],
        }
        
        if rating.get('outlook'):
            fields["Outlook"] = airtable_client._map_outlook(rating['outlook'])
        if rating.get('instrument_amount'):
            fields["Instrument Amount"] = rating['instrument_amount']
        if rating.get('date'):
            fields["Date"] = rating['date'].strftime('%Y-%m-%d')
        if rating.get('source_url'):
            fields["Source URL"] = rating['source_url']
        
        created_record = airtable_client.credit_ratings_table.create(fields)
        airtable_rating_id = created_record['id']
        
        print(f"✓ Created rating in Airtable: {airtable_rating_id}")
        
        # Update PostgreSQL with Airtable ID
        update_count = update_ratings_airtable_ids([(record_id, airtable_rating_id)])
        
        if update_count == 1:
            print("✓ Updated PostgreSQL with Airtable ID")
        else:
            print("✗ Failed to update PostgreSQL")
            return False
        
        # Verify sync
        unsynced_after = get_unsynced_ratings(test_job_id)
        if len(unsynced_after) == 0:
            print("✓ All ratings synced successfully")
            return True
        else:
            print(f"⚠ Still {len(unsynced_after)} unsynced ratings")
            return False
        
    except Exception as e:
        print(f"✗ Airtable sync test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_duplicate_stats():
    """Test 5: Duplicate statistics"""
    print_header("TEST 5: Duplicate Statistics")
    
    test_job_id = f"test_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_company = f"Stats Test Company - {datetime.now().strftime('%H%M%S')}"
    
    try:
        # Insert some test data
        batch_data = []
        for i in range(5):
            batch_data.append({
                'company_name': test_company,
                'instrument_category': 'Term Loan',
                'rating': f'A{i}',
                'outlook': 'Stable',
                'instrument_amount': f'Rs. {(i+1)*100} Cr.',
                'date': '2025-10-26',
                'url': f'https://test.com/stats_test_{i}.pdf'
            })
        
        # Add duplicates
        batch_data.extend(batch_data[:3])  # Duplicate first 3
        
        new_count, dup_count = batch_insert_ratings(batch_data, test_job_id)
        
        print(f"Inserted: {new_count} new, {dup_count} duplicates")
        
        # Get stats
        stats = get_duplicate_stats(test_job_id)
        
        print(f"\nStatistics from PostgreSQL:")
        print(f"  - Total ratings: {stats['total_ratings']}")
        print(f"  - Synced count: {stats['synced_count']}")
        print(f"  - Failed count: {stats['failed_count']}")
        
        if stats['total_ratings'] == new_count:
            print("✓ Statistics match expected values")
            return True
        else:
            print(f"⚠ Statistics mismatch: expected {new_count}, got {stats['total_ratings']}")
            return False
        
    except Exception as e:
        print(f"✗ Statistics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print_header("PostgreSQL Deduplication Integration Tests")
    print("This test suite will verify:")
    print("1. Database initialization")
    print("2. Single insert with deduplication")
    print("3. Batch insert with duplicates")
    print("4. Airtable sync (if credentials available)")
    print("5. Duplicate statistics")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    
    # Run tests
    results = []
    
    results.append(("Database Initialization", test_database_initialization()))
    results.append(("Insert with Deduplication", test_insert_with_deduplication()))
    results.append(("Batch Insert", test_batch_insert()))
    results.append(("Airtable Sync", test_airtable_sync()))
    results.append(("Duplicate Statistics", test_duplicate_stats()))
    
    # Cleanup
    close_connection_pool()
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<50} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! PostgreSQL deduplication is working correctly.")
        sys.exit(0)
    else:
        print(f"\n⚠ {failed} test(s) failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

