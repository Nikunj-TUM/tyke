"""
Company Service

Handles business logic for company synchronization between Postgres and Airtable.
"""
import logging
from typing import Dict, List, Optional
from ..database import (
    get_companies_without_airtable_id,
    batch_update_company_airtable_ids,
    get_company_airtable_id
)
from ..airtable_client import AirtableClient
from ..config import settings

logger = logging.getLogger(__name__)


class CompanyService:
    """
    Service for managing company synchronization.
    
    Responsibilities:
    - Get companies needing Airtable sync from Postgres
    - Batch create companies in Airtable
    - Update Postgres with Airtable IDs
    - Handle errors and retries
    """
    
    def __init__(self, airtable_client: Optional[AirtableClient] = None):
        """
        Initialize company service.
        
        Args:
            airtable_client: Optional AirtableClient instance. Creates new one if not provided.
        """
        self.airtable_client = airtable_client or AirtableClient()
    
    def sync_companies_for_job(self, job_id: str) -> Dict[str, int]:
        """
        Sync all companies for a specific job to Airtable.
        
        This is the main entry point for company syncing.
        
        Args:
            job_id: Job ID to sync companies for
            
        Returns:
            Dictionary with sync statistics:
            - companies_synced: Number of companies synced
            - companies_failed: Number of companies that failed to sync
        """
        logger.info(f"Starting company sync for job {job_id}")
        
        # Get companies that need syncing for this job
        companies_to_sync = get_companies_without_airtable_id(job_id)
        
        if not companies_to_sync:
            logger.info("No companies need syncing")
            return {'companies_synced': 0, 'companies_failed': 0}
        
        company_names = [c['company_name'] for c in companies_to_sync]
        logger.info(f"Found {len(company_names)} companies to sync: {company_names[:5]}...")
        
        # Batch create companies in Airtable
        synced, failed = self._batch_create_companies(company_names)
        
        logger.info(f"Company sync complete: {synced} synced, {failed} failed")
        return {
            'companies_synced': synced,
            'companies_failed': failed
        }
    
    def _batch_create_companies(
        self,
        company_names: List[str]
    ) -> tuple[int, int]:
        """
        Batch create companies in Airtable and update Postgres.
        
        Args:
            company_names: List of company names to create
            
        Returns:
            Tuple of (synced_count, failed_count)
        """
        if not company_names:
            return (0, 0)
        
        synced_count = 0
        failed_count = 0
        company_mapping = {}
        
        # Process in batches of COMPANY_BATCH_SIZE
        batch_size = settings.COMPANY_BATCH_SIZE
        
        for i in range(0, len(company_names), batch_size):
            batch = company_names[i:i + batch_size]
            
            try:
                logger.info(f"Creating batch {i//batch_size + 1}: {len(batch)} companies")
                
                # Create companies in Airtable
                created_records = self.airtable_client.batch_create_companies(batch)
                
                # Build mapping of company_name -> airtable_id
                for j, record in enumerate(created_records):
                    if j < len(batch):
                        company_name = batch[j]
                        airtable_id = record['id']
                        company_mapping[company_name] = airtable_id
                        synced_count += 1
                        logger.debug(f"Created company: {company_name} -> {airtable_id}")
                
            except Exception as e:
                logger.error(f"Failed to create batch {i//batch_size + 1}: {str(e)}")
                failed_count += len(batch)
                continue
        
        # Batch update Postgres with Airtable IDs
        if company_mapping:
            try:
                updated = batch_update_company_airtable_ids(company_mapping)
                logger.info(f"Updated {updated} companies in Postgres with Airtable IDs")
            except Exception as e:
                logger.error(f"Failed to update Postgres with company Airtable IDs: {str(e)}")
        
        return (synced_count, failed_count)
    
    def get_company_airtable_id_from_db(self, company_name: str) -> Optional[str]:
        """
        Get Airtable ID for a company from Postgres.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Airtable record ID or None if not found
        """
        return get_company_airtable_id(company_name)

