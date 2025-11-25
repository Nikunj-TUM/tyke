"""
Campaign Management API endpoints
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import get_current_user, require_permission, Permission
from ..auth.dependencies import CurrentUser
from ..database import get_db_cursor
from ..services.activity_logger import ActivityLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/campaigns", tags=["Campaigns"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CampaignResponse(BaseModel):
    """Campaign response model"""
    id: int
    name: str
    description: Optional[str] = None
    message_template: str
    status: str
    whatsapp_instance_id: int
    whatsapp_instance_name: str
    scheduled_start_time: Optional[str] = None
    actual_start_time: Optional[str] = None
    completed_at: Optional[str] = None
    messages_per_hour: int = 60
    delay_between_messages_seconds: int = 10
    total_contacts: int = 0
    messages_sent: int = 0
    messages_failed: int = 0
    messages_pending: int = 0
    created_by_name: Optional[str] = None
    created_at: str


class CreateCampaignRequest(BaseModel):
    """Create campaign request"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    message_template: str = Field(..., min_length=1)
    whatsapp_instance_id: int
    scheduled_start_time: Optional[str] = None
    messages_per_hour: int = Field(default=60, ge=1, le=500)
    delay_between_messages_seconds: int = Field(default=10, ge=1)


class UpdateCampaignRequest(BaseModel):
    """Update campaign request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    message_template: Optional[str] = None
    scheduled_start_time: Optional[str] = None
    messages_per_hour: Optional[int] = Field(None, ge=1, le=500)
    delay_between_messages_seconds: Optional[int] = Field(None, ge=1)


class AddContactsToCampaignRequest(BaseModel):
    """Add contacts to campaign request"""
    contact_ids: List[int] = Field(..., min_items=1, max_items=1000)


class CampaignStatsResponse(BaseModel):
    """Campaign statistics response"""
    campaign_id: int
    total_contacts: int
    messages_sent: int
    messages_failed: int
    messages_pending: int
    delivery_rate: float
    status: str


# ============================================================================
# CAMPAIGN ENDPOINTS
# ============================================================================

@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_READ)),
    limit: int = 100,
    offset: int = 0,
    status_filter: Optional[str] = None
):
    """
    List all campaigns in the organization
    
    Requires: campaigns.read permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Build query with optional status filter
            where_clause = "c.organization_id = %s"
            params = [current_user.organization_id]
            
            if status_filter:
                where_clause += " AND c.status = %s::campaign_status_enum"
                params.append(status_filter)
            
            params.extend([limit, offset])
            
            cursor.execute(f"""
                SELECT 
                    c.id,
                    c.name,
                    c.description,
                    c.message_template,
                    c.status,
                    c.whatsapp_instance_id,
                    wi.name as whatsapp_instance_name,
                    c.scheduled_start_time,
                    c.actual_start_time,
                    c.completed_at,
                    c.messages_per_hour,
                    c.delay_between_messages_seconds,
                    c.total_contacts,
                    c.messages_sent,
                    c.messages_failed,
                    c.messages_pending,
                    u.first_name || ' ' || u.last_name as created_by_name,
                    c.created_at
                FROM campaigns c
                JOIN whatsapp_instances wi ON wi.id = c.whatsapp_instance_id
                LEFT JOIN users u ON u.id = c.created_by
                WHERE {where_clause}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            
            campaigns = cursor.fetchall()
            
            return [
                CampaignResponse(
                    id=c['id'],
                    name=c['name'],
                    description=c['description'],
                    message_template=c['message_template'],
                    status=c['status'],
                    whatsapp_instance_id=c['whatsapp_instance_id'],
                    whatsapp_instance_name=c['whatsapp_instance_name'],
                    scheduled_start_time=c['scheduled_start_time'].isoformat() if c.get('scheduled_start_time') else None,
                    actual_start_time=c['actual_start_time'].isoformat() if c.get('actual_start_time') else None,
                    completed_at=c['completed_at'].isoformat() if c.get('completed_at') else None,
                    messages_per_hour=c['messages_per_hour'],
                    delay_between_messages_seconds=c['delay_between_messages_seconds'],
                    total_contacts=c['total_contacts'],
                    messages_sent=c['messages_sent'],
                    messages_failed=c['messages_failed'],
                    messages_pending=c['messages_pending'],
                    created_by_name=c.get('created_by_name'),
                    created_at=c['created_at'].isoformat()
                )
                for c in campaigns
            ]
            
    except Exception as e:
        logger.error(f"Error listing campaigns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaigns"
        )


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CreateCampaignRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_CREATE))
):
    """
    Create a new campaign
    
    Requires: campaigns.create permission
    """
    try:
        from ..services.whatsapp_instance_manager import WhatsAppInstanceManager
        
        with get_db_cursor(dict_cursor=True) as cursor:
            # Verify WhatsApp instance exists and belongs to organization
            manager = WhatsAppInstanceManager()
            instance = manager.get_instance(campaign_data.whatsapp_instance_id, current_user.organization_id)
            
            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WhatsApp instance not found or doesn't belong to your organization"
                )
            
            # Parse scheduled start time if provided
            scheduled_start_time = None
            if campaign_data.scheduled_start_time:
                try:
                    scheduled_start_time = datetime.fromisoformat(campaign_data.scheduled_start_time.replace('Z', '+00:00'))
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid scheduled_start_time format. Use ISO format."
                    )
            
            # Create campaign
            cursor.execute("""
                INSERT INTO campaigns (
                    organization_id,
                    whatsapp_instance_id,
                    name,
                    description,
                    message_template,
                    status,
                    scheduled_start_time,
                    messages_per_hour,
                    delay_between_messages_seconds,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s)
                RETURNING id, name, description, message_template, status, scheduled_start_time,
                          messages_per_hour, delay_between_messages_seconds, created_at
            """, (
                current_user.organization_id,
                campaign_data.whatsapp_instance_id,
                campaign_data.name,
                campaign_data.description,
                campaign_data.message_template,
                scheduled_start_time,
                campaign_data.messages_per_hour,
                campaign_data.delay_between_messages_seconds,
                current_user.id
            ))
            
            campaign = cursor.fetchone()
            
            # Log activity
            ActivityLogger.log_audit(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="created",
                resource_type="campaign",
                resource_id=str(campaign['id']),
                new_values={
                    "name": campaign['name'],
                    "whatsapp_instance_id": campaign_data.whatsapp_instance_id
                }
            )
            
            logger.info(
                f"Campaign created: {campaign['name']} (ID: {campaign['id']}) "
                f"by {current_user.email}"
            )
            
            return CampaignResponse(
                id=campaign['id'],
                name=campaign['name'],
                description=campaign['description'],
                message_template=campaign['message_template'],
                status=campaign['status'],
                whatsapp_instance_id=campaign_data.whatsapp_instance_id,
                whatsapp_instance_name=instance['name'],
                scheduled_start_time=campaign['scheduled_start_time'].isoformat() if campaign.get('scheduled_start_time') else None,
                actual_start_time=None,
                completed_at=None,
                messages_per_hour=campaign['messages_per_hour'],
                delay_between_messages_seconds=campaign['delay_between_messages_seconds'],
                total_contacts=0,
                messages_sent=0,
                messages_failed=0,
                messages_pending=0,
                created_by_name=current_user.full_name,
                created_at=campaign['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating campaign: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create campaign"
        )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_READ))
):
    """
    Get campaign details
    
    Requires: campaigns.read permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    c.id,
                    c.name,
                    c.description,
                    c.message_template,
                    c.status,
                    c.whatsapp_instance_id,
                    wi.name as whatsapp_instance_name,
                    c.scheduled_start_time,
                    c.actual_start_time,
                    c.completed_at,
                    c.messages_per_hour,
                    c.delay_between_messages_seconds,
                    c.total_contacts,
                    c.messages_sent,
                    c.messages_failed,
                    c.messages_pending,
                    u.first_name || ' ' || u.last_name as created_by_name,
                    c.created_at
                FROM campaigns c
                JOIN whatsapp_instances wi ON wi.id = c.whatsapp_instance_id
                LEFT JOIN users u ON u.id = c.created_by
                WHERE c.id = %s AND c.organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            return CampaignResponse(
                id=campaign['id'],
                name=campaign['name'],
                description=campaign['description'],
                message_template=campaign['message_template'],
                status=campaign['status'],
                whatsapp_instance_id=campaign['whatsapp_instance_id'],
                whatsapp_instance_name=campaign['whatsapp_instance_name'],
                scheduled_start_time=campaign['scheduled_start_time'].isoformat() if campaign.get('scheduled_start_time') else None,
                actual_start_time=campaign['actual_start_time'].isoformat() if campaign.get('actual_start_time') else None,
                completed_at=campaign['completed_at'].isoformat() if campaign.get('completed_at') else None,
                messages_per_hour=campaign['messages_per_hour'],
                delay_between_messages_seconds=campaign['delay_between_messages_seconds'],
                total_contacts=campaign['total_contacts'],
                messages_sent=campaign['messages_sent'],
                messages_failed=campaign['messages_failed'],
                messages_pending=campaign['messages_pending'],
                created_by_name=campaign.get('created_by_name'),
                created_at=campaign['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign"
        )


@router.post("/{campaign_id}/contacts", status_code=status.HTTP_200_OK)
async def add_contacts_to_campaign(
    campaign_id: int,
    contacts_data: AddContactsToCampaignRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_CREATE))
):
    """
    Add contacts to campaign
    
    Requires: campaigns.create permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Verify campaign exists and belongs to organization
            cursor.execute("""
                SELECT id, status FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            # Can only add contacts to draft or scheduled campaigns
            if campaign['status'] not in ['draft', 'scheduled']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot add contacts to running or completed campaign"
                )
            
            # Verify all contacts belong to organization
            cursor.execute("""
                SELECT id FROM contacts
                WHERE id = ANY(%s) AND organization_id = %s
            """, (contacts_data.contact_ids, current_user.organization_id))
            
            valid_contacts = cursor.fetchall()
            valid_contact_ids = [c['id'] for c in valid_contacts]
            
            if len(valid_contact_ids) != len(contacts_data.contact_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Some contacts not found or don't belong to your organization"
                )
            
            # Add contacts to campaign
            added_count = 0
            for contact_id in valid_contact_ids:
                try:
                    cursor.execute("""
                        INSERT INTO campaign_contacts (campaign_id, contact_id, status)
                        VALUES (%s, %s, 'pending')
                        ON CONFLICT (campaign_id, contact_id) DO NOTHING
                    """, (campaign_id, contact_id))
                    
                    if cursor.rowcount > 0:
                        added_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error adding contact {contact_id} to campaign: {str(e)}")
            
            # Update total_contacts and messages_pending in campaign
            cursor.execute("""
                UPDATE campaigns
                SET 
                    total_contacts = (SELECT COUNT(*) FROM campaign_contacts WHERE campaign_id = %s),
                    messages_pending = (SELECT COUNT(*) FROM campaign_contacts WHERE campaign_id = %s AND status = 'pending')
                WHERE id = %s
            """, (campaign_id, campaign_id, campaign_id))
            
            logger.info(
                f"Added {added_count} contacts to campaign {campaign_id} "
                f"by {current_user.email}"
            )
            
            return {
                "success": True,
                "message": f"Added {added_count} contacts to campaign",
                "contacts_added": added_count
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding contacts to campaign: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add contacts to campaign"
        )


@router.post("/{campaign_id}/start", status_code=status.HTTP_200_OK)
async def start_campaign(
    campaign_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_EXECUTE))
):
    """
    Start a campaign
    
    Requires: campaigns.execute permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Get campaign details
            cursor.execute("""
                SELECT id, status, total_contacts
                FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            # Check campaign status
            if campaign['status'] not in ['draft', 'scheduled', 'paused']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot start campaign with status: {campaign['status']}"
                )
            
            # Check if campaign has contacts
            if campaign['total_contacts'] == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot start campaign with no contacts"
                )
            
            # Update campaign status
            cursor.execute("""
                UPDATE campaigns
                SET 
                    status = 'running',
                    actual_start_time = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (campaign_id,))
            
            # Log activity
            ActivityLogger.log_audit(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="started",
                resource_type="campaign",
                resource_id=str(campaign_id)
            )
            
            logger.info(f"Campaign {campaign_id} started by {current_user.email}")
            
            # TODO: Trigger Celery task to process campaign messages
            
            return {
                "success": True,
                "message": "Campaign started successfully",
                "campaign_id": campaign_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting campaign: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start campaign"
        )


@router.post("/{campaign_id}/pause", status_code=status.HTTP_200_OK)
async def pause_campaign(
    campaign_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_EXECUTE))
):
    """
    Pause a running campaign
    
    Requires: campaigns.execute permission
    """
    try:
        with get_db_cursor() as cursor:
            # Verify campaign exists and is running
            cursor.execute("""
                SELECT status FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            if campaign[0] != 'running':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only pause running campaigns"
                )
            
            # Update status
            cursor.execute("""
                UPDATE campaigns
                SET status = 'paused'
                WHERE id = %s
            """, (campaign_id,))
            
            # Log activity
            ActivityLogger.log_audit(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="paused",
                resource_type="campaign",
                resource_id=str(campaign_id)
            )
            
            logger.info(f"Campaign {campaign_id} paused by {current_user.email}")
            
            return {
                "success": True,
                "message": "Campaign paused successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing campaign: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause campaign"
        )


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_READ))
):
    """
    Get campaign statistics
    
    Requires: campaigns.read permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    status,
                    total_contacts,
                    messages_sent,
                    messages_failed,
                    messages_pending,
                    CASE 
                        WHEN total_contacts > 0 THEN 
                            ROUND(100.0 * messages_sent / total_contacts, 2)
                        ELSE 0
                    END as delivery_rate
                FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            return CampaignStatsResponse(
                campaign_id=campaign['id'],
                total_contacts=campaign['total_contacts'],
                messages_sent=campaign['messages_sent'],
                messages_failed=campaign['messages_failed'],
                messages_pending=campaign['messages_pending'],
                delivery_rate=float(campaign['delivery_rate']),
                status=campaign['status']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve campaign statistics"
        )


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.CAMPAIGNS_DELETE))
):
    """
    Delete campaign
    
    Requires: campaigns.delete permission
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Get campaign name for logging
            cursor.execute("""
                SELECT name, status FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            
            # Cannot delete running campaigns
            if campaign['status'] == 'running':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete running campaign. Pause it first."
                )
            
            # Delete campaign
            cursor.execute("""
                DELETE FROM campaigns
                WHERE id = %s AND organization_id = %s
            """, (campaign_id, current_user.organization_id))
            
            # Log activity
            ActivityLogger.log_audit(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                action="deleted",
                resource_type="campaign",
                resource_id=str(campaign_id),
                old_values={"name": campaign['name']}
            )
            
            logger.info(f"Campaign deleted: {campaign['name']} (ID: {campaign_id}) by {current_user.email}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting campaign: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete campaign"
        )

