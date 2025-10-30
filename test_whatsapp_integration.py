#!/usr/bin/env python3
"""
Test script for WhatsApp integration

This script tests the WhatsApp integration by:
1. Checking WhatsApp connection status
2. Sending a test message
3. Sending bulk test messages (optional)

Usage:
    python test_whatsapp_integration.py

Make sure to:
1. Set your API_KEY in .env
2. Start all services: docker-compose up -d
3. Authenticate WhatsApp by scanning QR code
"""

import os
import sys
import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "your_api_key_here")

# Test phone number (change this to your test number)
TEST_PHONE = os.getenv("TEST_PHONE", "+919876543210")

def print_section(title):
    """Print a section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def check_status():
    """Check WhatsApp connection status"""
    print_section("1. Checking WhatsApp Status")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/whatsapp/status",
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Status check successful")
            print(f"\nConnection Status:")
            print(f"  - Connected: {data.get('connected')}")
            print(f"  - QR Pending: {data.get('qr_pending')}")
            print(f"  - RabbitMQ Connected: {data.get('rabbitmq_connected')}")
            
            if data.get('client_info'):
                info = data['client_info']
                print(f"\nWhatsApp Client:")
                print(f"  - Phone: {info.get('phone')}")
                print(f"  - Name: {info.get('name')}")
                print(f"  - Platform: {info.get('platform')}")
            
            if data.get('queue_stats'):
                stats = data['queue_stats']
                print(f"\nQueue Statistics:")
                print(f"  - Queue Name: {stats.get('queue_name')}")
                print(f"  - Messages in Queue: {stats.get('message_count')}")
                print(f"  - Active Consumers: {stats.get('consumer_count')}")
            
            if data.get('qr_pending') and data.get('qr_code'):
                print("\n⚠ QR Code Authentication Required")
                print(f"Visit: http://localhost:3000/qr to scan QR code")
                return False
            
            if not data.get('connected'):
                print("\n✗ WhatsApp is not connected")
                if data.get('error'):
                    print(f"Error: {data.get('error')}")
                return False
            
            return True
        else:
            print(f"✗ Status check failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error checking status: {str(e)}")
        return False

def send_single_message(phone, message, name=None):
    """Send a single WhatsApp message"""
    print_section("2. Sending Single Test Message")
    
    print(f"Sending to: {phone}")
    print(f"Message: {message[:50]}...")
    
    try:
        payload = {
            "phone_number": phone,
            "message": message,
            "contact_name": name
        }
        
        response = requests.post(
            f"{API_BASE_URL}/whatsapp/send",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Message sent successfully")
            print(f"\nResponse:")
            print(f"  - Success: {data.get('success')}")
            print(f"  - Status: {data.get('status')}")
            print(f"  - Message ID: {data.get('message_id')}")
            print(f"  - Phone: {data.get('phone_number')}")
            return True
        else:
            print(f"✗ Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending message: {str(e)}")
        return False

def send_bulk_messages():
    """Send bulk WhatsApp messages"""
    print_section("3. Sending Bulk Test Messages")
    
    # Prepare test contacts (modify as needed)
    contacts = [
        {
            "phone_number": TEST_PHONE,
            "message": f"Test message 1 - {datetime.now().strftime('%H:%M:%S')}",
            "name": "Test Contact 1"
        },
        {
            "phone_number": TEST_PHONE,
            "message": f"Test message 2 - {datetime.now().strftime('%H:%M:%S')}",
            "name": "Test Contact 2"
        }
    ]
    
    print(f"Sending {len(contacts)} messages...")
    
    try:
        payload = {
            "contacts": contacts
        }
        
        response = requests.post(
            f"{API_BASE_URL}/whatsapp/send/bulk",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Bulk send completed")
            print(f"\nResults:")
            print(f"  - Total: {data.get('total')}")
            print(f"  - Queued: {data.get('queued')}")
            print(f"  - Failed: {data.get('failed')}")
            
            if data.get('message_ids'):
                print(f"\nMessage IDs:")
                for msg in data['message_ids']:
                    print(f"  - {msg['message_id']} → {msg['phone_number']}")
            
            if data.get('errors'):
                print(f"\nErrors:")
                for error in data['errors']:
                    print(f"  - {error}")
            
            return True
        else:
            print(f"✗ Failed to send bulk messages: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending bulk messages: {str(e)}")
        return False

def main():
    """Main test function"""
    print("\n" + "="*70)
    print("  WhatsApp Integration Test Script")
    print("="*70)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Test Phone: {TEST_PHONE}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if API key is set
    if API_KEY == "your_api_key_here":
        print("\n✗ ERROR: Please set your API_KEY in .env file")
        print("Example: API_KEY=your_actual_api_key_here")
        sys.exit(1)
    
    # Step 1: Check status
    is_connected = check_status()
    
    if not is_connected:
        print("\n" + "="*70)
        print("⚠ WhatsApp is not connected. Please:")
        print("  1. Start services: docker-compose up -d")
        print("  2. Check logs: docker-compose logs -f whatsapp-service")
        print("  3. Scan QR code: http://localhost:3000/qr")
        print("="*70)
        sys.exit(1)
    
    # Ask user if they want to send test messages
    print("\n" + "="*70)
    response = input("\nWhatsApp is connected. Send test messages? (y/n): ")
    
    if response.lower() != 'y':
        print("Skipping message tests.")
        sys.exit(0)
    
    # Step 2: Send single message
    test_message = f"Test message from Infomerics WhatsApp Integration - {datetime.now().strftime('%H:%M:%S')}"
    send_single_message(TEST_PHONE, test_message, "Test Contact")
    
    # Ask if user wants to test bulk sending
    print("\n" + "="*70)
    response = input("\nTest bulk sending? (y/n): ")
    
    if response.lower() == 'y':
        send_bulk_messages()
    
    print("\n" + "="*70)
    print("  Test Complete!")
    print("="*70)
    print("\nCheck the following:")
    print("  1. WhatsApp messages received on test phone")
    print("  2. Docker logs: docker-compose logs -f whatsapp-service")
    print("  3. RabbitMQ queue: http://localhost:15672 (guest/guest)")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

