#!/usr/bin/env python3
"""
Test script for the contact fetch endpoint

This script demonstrates how to call the /contacts/fetch endpoint
to retrieve director contact information from Attestr API.

Usage:
    python test_contact_fetch.py
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "your-api-key-here")

def fetch_contacts(cin: str, company_airtable_id: str, max_contacts: int = 10):
    """
    Fetch contacts for a company using CIN
    
    Args:
        cin: Company Identification Number
        company_airtable_id: Airtable record ID of the company
        max_contacts: Maximum number of contacts to fetch
    """
    url = f"{API_URL}/contacts/fetch"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    payload = {
        "cin": cin,
        "company_airtable_id": company_airtable_id,
        "max_contacts": max_contacts
    }
    
    print(f"\n{'='*60}")
    print(f"Fetching contacts for CIN: {cin}")
    print(f"Company Airtable ID: {company_airtable_id}")
    print(f"Max contacts: {max_contacts}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✓ Success!")
            print(f"\nBusiness Name: {result.get('business_name')}")
            print(f"Total Contacts Fetched: {result.get('total_contacts_fetched')}")
            print(f"New Contacts: {result.get('new_contacts')}")
            print(f"Updated Contacts: {result.get('updated_contacts')}")
            print(f"Synced to Airtable: {result.get('synced_to_airtable')}")
            print(f"Failed Syncs: {result.get('failed_syncs')}")
            print(f"\nMessage: {result.get('message')}")
            
            if result.get('contacts'):
                print(f"\nContact Details:")
                for idx, contact in enumerate(result['contacts'], 1):
                    print(f"\n  Contact {idx}:")
                    print(f"    Name: {contact.get('fullName')}")
                    print(f"    DIN: {contact.get('indexId')}")
                    print(f"    Mobile: {contact.get('mobileNumber', 'N/A')}")
                    print(f"    Email: {contact.get('emailAddress', 'N/A')}")
                    if contact.get('addresses'):
                        print(f"    Address: {contact['addresses'][0].get('fullAddress', 'N/A')}")
        else:
            print(f"\n✗ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.Timeout:
        print("\n✗ Request timed out")
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Request failed: {str(e)}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")


if __name__ == "__main__":
    # Example test cases
    # Replace these with actual test data
    
    print("\n" + "="*60)
    print("Contact Fetch API Test Script")
    print("="*60)
    
    # Test Case 1: Valid CIN
    print("\n\nTest Case 1: Fetch contacts for a valid CIN")
    print("-" * 60)
    
    # Example CIN from Attestr API documentation
    test_cin = "U74999TG2017PTC118280"
    test_company_airtable_id = "recXXXXXXXXXXXXXX"  # Replace with actual Airtable record ID
    
    print("\n⚠️  Please update the following values in the script:")
    print(f"   - test_cin: {test_cin}")
    print(f"   - test_company_airtable_id: {test_company_airtable_id}")
    print(f"   - API_KEY in .env file")
    print(f"   - ATTESTR_API_KEY in .env file")
    
    # Uncomment to run the test
    # fetch_contacts(test_cin, test_company_airtable_id, max_contacts=5)
    
    print("\n\n" + "="*60)
    print("To run this test:")
    print("1. Update the test_cin and test_company_airtable_id values")
    print("2. Ensure API_KEY and ATTESTR_API_KEY are set in .env")
    print("3. Uncomment the fetch_contacts() call above")
    print("4. Run: python test_contact_fetch.py")
    print("="*60 + "\n")

