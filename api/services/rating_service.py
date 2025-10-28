"""
Rating Service

Handles business logic for rating synchronization between Postgres and Airtable.
"""
import logging
from typing import Dict, List, Tuple, Optional
from ..database import (
    get_unsynced_ratings,
    get_company_airtable_id,
    update_ratings_airtable_ids,
    mark_ratings_sync_failed
)
from ..airtable_client import AirtableClient
from ..config import settings

logger = logging.getLogger(__name__)


class RatingService:
    """
    Service for managing rating synchronization.
    
    Responsibilities:
    - Get ratings needing Airtable sync from Postgres
    - Batch create ratings in Airtable
    - Update Postgres with Airtable IDs
    - Handle sync failures
    """
    
    def __init__(self, airtable_client: Optional[AirtableClient] = None):
        """
        Initialize rating service.
        
        Args:
            airtable_client: Optional AirtableClient instance. Creates new one if not provided.
        """
        self.airtable_client = airtable_client or AirtableClient()
    
    def sync_ratings_for_job(self, job_id: str) -> Dict[str, int]:
        """
        Sync all ratings for a specific job to Airtable.
        
        This is the main entry point for rating syncing.
        All companies must be synced before calling this method.
        
        Args:
            job_id: Job ID to sync ratings for
            
        Returns:
            Dictionary with sync statistics:
            - ratings_synced: Number of ratings synced
            - ratings_failed: Number of ratings that failed to sync
        """
        logger.info(f"Starting rating sync for job {job_id}")
        
        # Get unsynced ratings from Postgres
        unsynced_ratings = get_unsynced_ratings(job_id)
        
        if not unsynced_ratings:
            logger.info("No ratings need syncing")
            return {'ratings_synced': 0, 'ratings_failed': 0}
        
        logger.info(f"Found {len(unsynced_ratings)} ratings to sync")
        
        # Enrich ratings with company Airtable IDs
        enriched_ratings, failed_rating_ids = self._enrich_ratings_with_company_ids(
            unsynced_ratings
        )
        
        if failed_rating_ids:
            # Mark ratings without company IDs as failed
            mark_ratings_sync_failed(
                failed_rating_ids,
                "Company not synced to Airtable"
            )
            logger.warning(
                f"{len(failed_rating_ids)} ratings failed: missing company Airtable IDs"
            )
        
        if not enriched_ratings:
            return {
                'ratings_synced': 0,
                'ratings_failed': len(failed_rating_ids)
            }
        
        # Batch create ratings in Airtable
        synced, failed = self._batch_create_ratings(enriched_ratings)
        
        total_failed = failed + len(failed_rating_ids)
        logger.info(f"Rating sync complete: {synced} synced, {total_failed} failed")
        
        return {
            'ratings_synced': synced,
            'ratings_failed': total_failed
        }
    
    def _enrich_ratings_with_company_ids(
        self,
        ratings: List[Dict]
    ) -> Tuple[List[Dict], List[int]]:
        """
        Enrich ratings with company Airtable IDs from Postgres.
        
        Args:
            ratings: List of rating dictionaries from Postgres
            
        Returns:
            Tuple of (enriched_ratings, failed_rating_ids)
        """
        enriched_ratings = []
        failed_rating_ids = []
        
        for rating in ratings:
            company_name = rating['company_name']
            company_airtable_id = get_company_airtable_id(company_name)
            
            if not company_airtable_id:
                logger.warning(
                    f"Rating {rating['id']}: Company '{company_name}' "
                    f"has no Airtable ID"
                )
                failed_rating_ids.append(rating['id'])
                continue
            
            # Add company Airtable ID to rating
            enriched_rating = dict(rating)
            enriched_rating['company_airtable_id'] = company_airtable_id
            enriched_ratings.append(enriched_rating)
        
        return (enriched_ratings, failed_rating_ids)
    
    def _batch_create_ratings(
        self,
        ratings: List[Dict]
    ) -> Tuple[int, int]:
        """
        Batch create ratings in Airtable and update Postgres.
        
        Args:
            ratings: List of enriched rating dictionaries with company_airtable_id
            
        Returns:
            Tuple of (synced_count, failed_count)
        """
        if not ratings:
            return (0, 0)
        
        synced_count = 0
        failed_count = 0
        rating_airtable_mapping = []
        failed_rating_ids = []
        
        # Process in batches of RATING_BATCH_SIZE
        batch_size = settings.RATING_BATCH_SIZE
        
        for i in range(0, len(ratings), batch_size):
            batch = ratings[i:i + batch_size]
            batch_rating_ids = [r['id'] for r in batch]
            
            try:
                logger.info(f"Creating batch {i//batch_size + 1}: {len(batch)} ratings")
                
                # Prepare batch data for Airtable
                batch_data = []
                for rating in batch:
                    batch_data.append({
                        'company_airtable_id': rating['company_airtable_id'],
                        'instrument': rating.get('instrument', ''),
                        'rating': rating.get('rating', ''),
                        'outlook': rating.get('outlook'),
                        'instrument_amount': rating.get('instrument_amount'),
                        'date': rating['date'].strftime('%Y-%m-%d') if rating.get('date') else None,
                        'source_url': rating.get('source_url')
                    })
                
                # Create ratings in Airtable
                created_records = self.airtable_client.batch_create_ratings(batch_data)
                
                # Build mapping of rating_id -> airtable_id
                for j, record in enumerate(created_records):
                    if j < len(batch_rating_ids):
                        rating_id = batch_rating_ids[j]
                        airtable_id = record['id']
                        rating_airtable_mapping.append((rating_id, airtable_id))
                        synced_count += 1
                
                logger.info(f"Batch {i//batch_size + 1} created successfully")
                
            except Exception as e:
                logger.error(f"Failed to create batch {i//batch_size + 1}: {str(e)}")
                failed_rating_ids.extend(batch_rating_ids)
                failed_count += len(batch)
                continue
        
        # Batch update Postgres with Airtable IDs
        if rating_airtable_mapping:
            try:
                updated = update_ratings_airtable_ids(rating_airtable_mapping)
                logger.info(f"Updated {updated} ratings in Postgres with Airtable IDs")
            except Exception as e:
                logger.error(f"Failed to update Postgres with rating Airtable IDs: {str(e)}")
        
        # Mark failed ratings
        if failed_rating_ids:
            mark_ratings_sync_failed(
                failed_rating_ids,
                "Failed to create in Airtable"
            )
        
        return (synced_count, failed_count)

