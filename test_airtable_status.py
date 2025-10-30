#!/usr/bin/env python3
"""
Test script for Airtable Status Update Feature

This script demonstrates how to use the new airtable_record_id field
to track scrape job status in Airtable.
"""

import requests
import time
import json
import os

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "your-api-key-here")

def test_scrape_with_airtable_status():
    """Test scraping with Airtable status updates"""
    
    print("=" * 60)
    print("Testing Airtable Status Update Feature")
    print("=" * 60)
    
    # Example 1: Scrape WITH Airtable status tracking
    print("\n1. Creating scrape job WITH Airtable status tracking...")
    print("-" * 60)
    
    request_data = {
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
        "airtable_record_id": "recXXXXXXXXXXXXXX"  # Replace with actual record ID
    }
    
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    response = requests.post(
        f"{API_BASE_URL}/infomerics/scrape",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json=request_data
    )
    
    if response.status_code == 200:
        job_data = response.json()
        print(f"\n✓ Job created successfully!")
        print(f"  Job ID: {job_data['job_id']}")
        print(f"  Status: {job_data['status']}")
        print(f"  Message: {job_data['message']}")
        
        # Check Airtable - status should now be "In progress"
        print(f"\n→ Check Airtable record {request_data['airtable_record_id']}")
        print(f"  Expected status: 'In progress'")
        
        # Poll job status
        print(f"\nPolling job status...")
        job_id = job_data['job_id']
        
        for i in range(10):  # Poll for up to ~50 seconds
            time.sleep(5)
            
            status_response = requests.get(
                f"{API_BASE_URL}/infomerics/jobs/{job_id}",
                headers={"X-API-Key": API_KEY}
            )
            
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"  Progress: {status['progress']}% - Status: {status['status']}")
                
                if status['status'] in ['completed', 'failed']:
                    print(f"\n✓ Job finished with status: {status['status']}")
                    
                    if status['status'] == 'completed':
                        print(f"\n→ Check Airtable record {request_data['airtable_record_id']}")
                        print(f"  Expected status: 'Done'")
                    else:
                        print(f"\n→ Check Airtable record {request_data['airtable_record_id']}")
                        print(f"  Expected status: 'Error'")
                    
                    break
        else:
            print("\n⚠ Job still running after timeout")
    else:
        print(f"\n✗ Error creating job: {response.status_code}")
        print(f"  {response.text}")
    
    # Example 2: Scrape WITHOUT Airtable status tracking
    print("\n\n2. Creating scrape job WITHOUT Airtable status tracking...")
    print("-" * 60)
    
    request_data_no_airtable = {
        "start_date": "2025-01-01",
        "end_date": "2025-01-05"
        # No airtable_record_id field
    }
    
    print(f"Request: {json.dumps(request_data_no_airtable, indent=2)}")
    
    response = requests.post(
        f"{API_BASE_URL}/infomerics/scrape",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json=request_data_no_airtable
    )
    
    if response.status_code == 200:
        job_data = response.json()
        print(f"\n✓ Job created successfully (no Airtable tracking)")
        print(f"  Job ID: {job_data['job_id']}")
        print(f"  Status: {job_data['status']}")
    else:
        print(f"\n✗ Error creating job: {response.status_code}")
        print(f"  {response.text}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


def test_api_health():
    """Test API health check"""
    print("\nChecking API health...")
    response = requests.get(f"{API_BASE_URL}/health")
    
    if response.status_code == 200:
        health = response.json()
        print(f"✓ API is healthy")
        print(f"  Status: {health['status']}")
        print(f"  Environment: {health['environment']}")
        return True
    else:
        print(f"✗ API health check failed: {response.status_code}")
        return False


if __name__ == "__main__":
    print("\nAirtable Status Update Feature - Test Script")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print(f"API Key: {API_KEY[:10]}..." if len(API_KEY) > 10 else "Not set")
    
    # Check API health first
    if test_api_health():
        print("\nNote: Replace 'recXXXXXXXXXXXXXX' with an actual Airtable record ID")
        print("      from the Infomerics Scraper table before running this test.\n")
        
        # Uncomment to run the test
        # test_scrape_with_airtable_status()
        
        print("\nTo run the test:")
        print("1. Create a record in the Airtable 'Infomerics Scraper' table")
        print("2. Get the record ID (starts with 'rec')")
        print("3. Replace 'recXXXXXXXXXXXXXX' in this script with the actual ID")
        print("4. Uncomment the test_scrape_with_airtable_status() call above")
        print("5. Run this script again")
    else:
        print("\n✗ API is not available. Please start the API server first.")

