"""
Contact Service

Handles business logic for fetching director contacts from Attestr API
and syncing them between PostgreSQL and Airtable.
"""
import logging
import requests
import base64
from typing import Dict, List, Optional, Tuple, Any
from ..config import settings
from ..airtable_client import AirtableClient
from ..database import (
    insert_contact_with_deduplication,
    get_contacts_by_company,
    get_contacts_without_airtable_id,
    batch_update_contact_airtable_ids,
    mark_contact_sync_failed
)

logger = logging.getLogger(__name__)


class ContactService:
    """
    Service for managing contact fetching and synchronization.
    
    Responsibilities:
    - Fetch contacts from Attestr API using CIN
    - Store contacts in PostgreSQL with deduplication
    - Sync contacts to Airtable
    - Handle errors and retries
    """
    
    def __init__(self, airtable_client: Optional[AirtableClient] = None):
        """
        Initialize contact service.
        
        Args:
            airtable_client: Optional AirtableClient instance. Creates new one if not provided.
        """
        self.airtable_client = airtable_client or AirtableClient()
    
    def fetch_and_store_contacts(
        self,
        cin: str,
        company_airtable_id: str,
        max_contacts: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Main orchestration method to fetch contacts from Attestr and sync to Airtable.
        
        Args:
            cin: Company Identification Number
            company_airtable_id: Airtable record ID of the company
            max_contacts: Optional maximum number of contacts to fetch
            force_refresh: Force refresh from Attestr API even if contacts exist
            
        Returns:
            Dictionary with results:
            - success: bool
            - message: str
            - business_name: str
            - total_contacts_fetched: int
            - new_contacts: int
            - updated_contacts: int
            - synced_to_airtable: int
            - failed_syncs: int
            - contacts: list of contact data
        """
        logger.info(f"Starting contact fetch for CIN: {cin}, Company: {company_airtable_id}")
        
        result = {
            'success': False,
            'message': '',
            'cin': cin,
            'business_name': None,
            'total_contacts_fetched': 0,
            'new_contacts': 0,
            'updated_contacts': 0,
            'synced_to_airtable': 0,
            'failed_syncs': 0,
            'contacts': []
        }
        
        try:
            # Step 0: Check if contacts already exist in PostgreSQL (unless force_refresh is True)
            if not force_refresh:
                logger.info(f"Checking if contacts already exist for company: {company_airtable_id}")
                existing_contacts = get_contacts_by_company(company_airtable_id)
            else:
                logger.info(f"Force refresh requested - skipping existing contact check")
                existing_contacts = []
            
            if existing_contacts and not force_refresh:
                logger.info(f"Found {len(existing_contacts)} existing contacts in PostgreSQL")
                
                # Convert existing contacts to response format
                import json
                contacts_list = []
                for contact in existing_contacts:
                    addresses = []
                    if contact.get('addresses'):
                        try:
                            addresses = json.loads(contact['addresses']) if isinstance(contact['addresses'], str) else contact['addresses']
                        except:
                            addresses = []
                    
                    contacts_list.append({
                        'indexId': contact.get('din'),
                        'fullName': contact.get('full_name'),
                        'mobileNumber': contact.get('mobile_number'),
                        'emailAddress': contact.get('email_address'),
                        'addresses': addresses
                    })
                
                result['success'] = True
                result['message'] = f"Returned {len(existing_contacts)} existing contacts from database (no API call made)"
                result['total_contacts_fetched'] = len(existing_contacts)
                result['contacts'] = contacts_list
                result['synced_to_airtable'] = sum(1 for c in existing_contacts if c.get('airtable_record_id'))
                
                logger.info(f"Returning existing contacts without calling Attestr API")
                return result
            
            # Step 1: No existing contacts - Fetch from Attestr API
            logger.info(f"No existing contacts found. Fetching from Attestr API for CIN: {cin}")
            attestr_response = self._fetch_from_attestr(cin, max_contacts)
            
            if not attestr_response.get('valid'):
                result['message'] = attestr_response.get('message', 'Data not available from Attestr')
                logger.warning(f"Attestr API returned invalid response: {result['message']}")
                return result
            
            result['business_name'] = attestr_response.get('businessName')
            contacts = attestr_response.get('contacts', [])
            result['total_contacts_fetched'] = len(contacts)
            result['contacts'] = contacts
            
            if not contacts:
                result['success'] = True
                result['message'] = 'No contacts found for this CIN'
                logger.info(f"No contacts found for CIN: {cin}")
                return result
            
            logger.info(f"Fetched {len(contacts)} contacts from Attestr")
            
            # Step 2: Store contacts in PostgreSQL with deduplication
            logger.info("Storing contacts in PostgreSQL...")
            new_count, updated_count, contact_ids = self._store_contacts_in_postgres(
                contacts,
                company_airtable_id
            )
            result['new_contacts'] = new_count
            result['updated_contacts'] = updated_count
            
            logger.info(f"Stored in Postgres: {new_count} new, {updated_count} updated")
            
            # Step 3: Sync contacts to Airtable
            logger.info("Syncing contacts to Airtable...")
            synced_count, failed_count = self._sync_contacts_to_airtable(
                company_airtable_id,
                contact_ids
            )
            result['synced_to_airtable'] = synced_count
            result['failed_syncs'] = failed_count
            
            logger.info(f"Synced to Airtable: {synced_count} successful, {failed_count} failed")
            
            result['success'] = True
            result['message'] = (
                f"Successfully processed {result['total_contacts_fetched']} contacts: "
                f"{new_count} new, {updated_count} updated, {synced_count} synced to Airtable"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing contacts: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            result['message'] = error_msg
            return result
    
    def _fetch_from_attestr(
        self,
        cin: str,
        max_contacts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch director contacts from Attestr API.
        
        Args:
            cin: Company Identification Number
            max_contacts: Optional maximum number of contacts
            
        Returns:
            API response dictionary
            
        Raises:
            Exception: If API call fails
        """
        if not settings.ATTESTR_API_KEY:
            raise Exception("ATTESTR_API_KEY not configured")
        
        # Prepare request
        url = settings.ATTESTR_API_URL
        
        # Create Basic auth header
        # If the API key already starts with base64-like pattern, use it directly
        # Otherwise, encode it
        api_key = settings.ATTESTR_API_KEY
        if api_key.endswith('==') or api_key.endswith('='):
            # Likely already base64 encoded
            auth_string = api_key
        else:
            # Need to encode
            auth_string = base64.b64encode(api_key.encode()).decode()
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_string}'
        }
        
        payload = {
            'reg': cin
        }
        
        # Add max_contacts if specified
        if max_contacts:
            payload['maxContacts'] = max_contacts
        else:
            payload['maxContacts'] = settings.ATTESTR_MAX_CONTACTS
        
        try:
            logger.debug(f"Calling Attestr API: {url}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            # Check for HTTP errors
            if response.status_code == 400:
                error_data = response.json()
                raise Exception(f"Bad request: {error_data.get('message', 'Unknown error')}")
            elif response.status_code == 401:
                raise Exception("Invalid Attestr API credentials")
            elif response.status_code == 403:
                error_data = response.json()
                raise Exception(f"Access forbidden: {error_data.get('message', 'Unknown error')}")
            elif response.status_code == 429:
                raise Exception("Rate limit exceeded")
            elif response.status_code >= 500:
                raise Exception(f"Attestr API server error: {response.status_code}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise Exception("Attestr API request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Attestr API request failed: {str(e)}")
    
    def _store_contacts_in_postgres(
        self,
        contacts: List[Dict[str, Any]],
        company_airtable_id: str
    ) -> Tuple[int, int, List[int]]:
        """
        Store contacts in PostgreSQL with deduplication.
        
        Args:
            contacts: List of contact dictionaries from Attestr API
            company_airtable_id: Airtable record ID of the company
            
        Returns:
            Tuple of (new_count, updated_count, list_of_contact_ids)
        """
        new_count = 0
        updated_count = 0
        contact_ids = []
        
        for contact in contacts:
            try:
                # Extract contact data
                din = contact.get('indexId')
                full_name = contact.get('fullName', '')
                mobile_number = contact.get('mobileNumber')
                email_address = contact.get('emailAddress')
                addresses = contact.get('addresses', [])
                
                # Skip if no name
                if not full_name:
                    logger.warning("Skipping contact with no name")
                    continue
                
                # Insert/update contact
                success, contact_id, is_new = insert_contact_with_deduplication(
                    din=din,
                    full_name=full_name,
                    mobile_number=mobile_number,
                    email_address=email_address,
                    addresses=addresses,
                    company_airtable_id=company_airtable_id
                )
                
                if success and contact_id:
                    contact_ids.append(contact_id)
                    if is_new:
                        new_count += 1
                        logger.debug(f"Created new contact: {full_name}")
                    else:
                        updated_count += 1
                        logger.debug(f"Updated existing contact: {full_name}")
                else:
                    logger.warning(f"Failed to store contact: {full_name}")
                    
            except Exception as e:
                logger.error(f"Error storing contact {contact.get('fullName', 'Unknown')}: {str(e)}")
                continue
        
        return (new_count, updated_count, contact_ids)
    
    def _sync_contacts_to_airtable(
        self,
        company_airtable_id: str,
        contact_ids: Optional[List[int]] = None
    ) -> Tuple[int, int]:
        """
        Sync contacts to Airtable (only those without Airtable IDs).
        
        Args:
            company_airtable_id: Airtable record ID of the company
            contact_ids: Optional list of specific contact IDs to sync
            
        Returns:
            Tuple of (synced_count, failed_count)
        """
        synced_count = 0
        failed_count = 0
        
        try:
            # Get contacts that need syncing
            contacts_to_sync = get_contacts_without_airtable_id(
                company_airtable_id=company_airtable_id
            )
            
            # If specific contact_ids provided, filter to those
            if contact_ids:
                contacts_to_sync = [
                    c for c in contacts_to_sync 
                    if c['id'] in contact_ids
                ]
            
            if not contacts_to_sync:
                logger.info("No contacts need syncing to Airtable")
                return (0, 0)
            
            logger.info(f"Syncing {len(contacts_to_sync)} contacts to Airtable")
            
            # Prepare contact data for Airtable
            airtable_contacts = []
            contact_id_mapping = {}  # Maps list index to postgres contact ID
            
            for idx, contact in enumerate(contacts_to_sync):
                # Extract full address from JSONB addresses field
                full_address = None
                if contact.get('addresses'):
                    import json
                    try:
                        addresses = json.loads(contact['addresses']) if isinstance(contact['addresses'], str) else contact['addresses']
                        if addresses and len(addresses) > 0:
                            full_address = addresses[0].get('fullAddress')
                    except:
                        pass
                
                airtable_contact = {
                    'name': contact['full_name'],
                    'phone_number': contact.get('mobile_number'),
                    'email': contact.get('email_address'),
                    'address': full_address,
                    'company_airtable_id': company_airtable_id
                }
                airtable_contacts.append(airtable_contact)
                contact_id_mapping[idx] = contact['id']
            
            # Batch create in Airtable
            try:
                created_records = self.airtable_client.batch_create_contacts(airtable_contacts)
                
                # Update PostgreSQL with Airtable IDs
                airtable_id_mapping = {}
                for idx, record in enumerate(created_records):
                    postgres_contact_id = contact_id_mapping.get(idx)
                    if postgres_contact_id:
                        airtable_id = record['id']
                        airtable_id_mapping[postgres_contact_id] = airtable_id
                        synced_count += 1
                
                # Batch update Airtable IDs in PostgreSQL
                if airtable_id_mapping:
                    batch_update_contact_airtable_ids(airtable_id_mapping)
                    logger.info(f"Updated {len(airtable_id_mapping)} contacts with Airtable IDs")
                
            except Exception as e:
                logger.error(f"Error batch creating contacts in Airtable: {str(e)}")
                failed_count = len(contacts_to_sync)
                
                # Mark all as failed in PostgreSQL
                for contact in contacts_to_sync:
                    mark_contact_sync_failed(contact['id'], str(e))
            
            return (synced_count, failed_count)
            
        except Exception as e:
            logger.error(f"Error syncing contacts to Airtable: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return (0, len(contacts_to_sync) if contacts_to_sync else 0)

