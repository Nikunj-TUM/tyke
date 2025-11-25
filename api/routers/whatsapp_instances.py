"""
WhatsApp Instance Management and Campaign API endpoints
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import requests

from ..auth import get_current_user, require_permission, Permission
from ..auth.dependencies import CurrentUser
from ..services.whatsapp_instance_manager import WhatsAppInstanceManager
from ..services.activity_logger import ActivityLogger
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["WhatsApp"])

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WhatsAppInstanceResponse(BaseModel):
    """WhatsApp instance response model"""
    id: int
    name: str
    phone_number: str
    is_authenticated: bool
    is_active: bool
    last_connected_at: Optional[str] = None
    messages_sent_today: int = 0
    daily_message_limit: int = 1000
    created_at: str


class CreateWhatsAppInstanceRequest(BaseModel):
    """Create WhatsApp instance request"""
    name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=50)


class WhatsAppQRResponse(BaseModel):
    """QR code response"""
    qr_code: Optional[str] = None
    qr_image: Optional[str] = None
    is_authenticated: bool
    expires_at: Optional[str] = None
    expired: bool = False


class SendWhatsAppMessageRequest(BaseModel):
    """Send WhatsApp message request"""
    instance_id: int
    phone_number: str = Field(..., min_length=10)
    message: str = Field(..., min_length=1, max_length=4096)
    contact_id: Optional[int] = None


class WhatsAppMessageResponse(BaseModel):
    """WhatsApp message response"""
    success: bool
    message: str
    message_id: Optional[str] = None
    instance_id: int
    phone_number: str


class WhatsAppMessageHistoryResponse(BaseModel):
    """WhatsApp message history item"""
    id: int
    phone_number: str
    message: str
    direction: str
    status: str
    contact_name: Optional[str] = None
    whatsapp_instance_name: str
    queued_at: str
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None


# ============================================================================
# WHATSAPP INSTANCE ENDPOINTS
# ============================================================================

@router.get("/instances", response_model=List[WhatsAppInstanceResponse])
async def list_whatsapp_instances(
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_READ))
):
    """
    List all WhatsApp instances for the organization
    
    Requires: whatsapp.read permission
    """
    try:
        manager = WhatsAppInstanceManager()
        instances = manager.list_instances(current_user.organization_id)
        
        return [
            WhatsAppInstanceResponse(
                id=i['id'],
                name=i['name'],
                phone_number=i['phone_number'],
                is_authenticated=i['is_authenticated'],
                is_active=i['is_active'],
                last_connected_at=i['last_connected_at'].isoformat() if i.get('last_connected_at') else None,
                messages_sent_today=i.get('messages_sent_today', 0),
                daily_message_limit=i.get('daily_message_limit', 1000),
                created_at=i['created_at'].isoformat()
            )
            for i in instances
        ]
        
    except Exception as e:
        logger.error(f"Error listing WhatsApp instances: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WhatsApp instances"
        )


@router.post("/instances", response_model=WhatsAppInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_whatsapp_instance(
    instance_data: CreateWhatsAppInstanceRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_MANAGE_INSTANCES))
):
    """
    Create a new WhatsApp instance
    
    Requires: whatsapp.manage_instances permission
    """
    try:
        manager = WhatsAppInstanceManager()
        
        # Create instance
        instance = manager.create_instance(
            organization_id=current_user.organization_id,
            name=instance_data.name,
            phone_number=instance_data.phone_number
        )
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create instance. Phone number may already exist."
            )
        
        # Log activity
        ActivityLogger.log_audit(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="created",
            resource_type="whatsapp_instance",
            resource_id=str(instance['id']),
            new_values={
                "name": instance['name'],
                "phone_number": instance['phone_number']
            }
        )
        
        logger.info(
            f"WhatsApp instance created: {instance['name']} "
            f"(ID: {instance['id']}) by {current_user.email}"
        )
        
        return WhatsAppInstanceResponse(
            id=instance['id'],
            name=instance['name'],
            phone_number=instance['phone_number'],
            is_authenticated=instance['is_authenticated'],
            is_active=instance['is_active'],
            last_connected_at=None,
            messages_sent_today=0,
            daily_message_limit=1000,
            created_at=instance['created_at'].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating WhatsApp instance: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create WhatsApp instance"
        )


@router.get("/instances/{instance_id}", response_model=WhatsAppInstanceResponse)
async def get_whatsapp_instance(
    instance_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_READ))
):
    """
    Get WhatsApp instance details
    
    Requires: whatsapp.read permission
    """
    try:
        manager = WhatsAppInstanceManager()
        instance = manager.get_instance(instance_id, current_user.organization_id)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WhatsApp instance not found"
            )
        
        return WhatsAppInstanceResponse(
            id=instance['id'],
            name=instance['name'],
            phone_number=instance['phone_number'],
            is_authenticated=instance['is_authenticated'],
            is_active=instance['is_active'],
            last_connected_at=instance['last_connected_at'].isoformat() if instance.get('last_connected_at') else None,
            messages_sent_today=instance.get('messages_sent_today', 0),
            daily_message_limit=instance.get('daily_message_limit', 1000),
            created_at=instance['created_at'].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting WhatsApp instance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WhatsApp instance"
        )


@router.get("/instances/{instance_id}/qr", response_model=WhatsAppQRResponse)
async def get_instance_qr_code(
    instance_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_MANAGE_INSTANCES))
):
    """
    Get QR code for WhatsApp instance authentication
    
    Requires: whatsapp.manage_instances permission
    """
    try:
        manager = WhatsAppInstanceManager()
        
        # Verify instance belongs to organization
        instance = manager.get_instance(instance_id, current_user.organization_id)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WhatsApp instance not found"
            )
        
        # If already authenticated, no QR needed
        if instance['is_authenticated']:
            return WhatsAppQRResponse(
                is_authenticated=True,
                expired=False
            )
        
        # Try to get QR from Node.js service
        try:
            whatsapp_service_url = "http://whatsapp-service:3000"
            response = requests.get(
                f"{whatsapp_service_url}/instances/{instance_id}/qr",
                timeout=5
            )
            
            if response.status_code == 200:
                qr_data = response.json()
                return WhatsAppQRResponse(
                    qr_code=qr_data.get('qr_code'),
                    qr_image=qr_data.get('qr_image'),
                    is_authenticated=False,
                    expired=False
                )
        except Exception as e:
            logger.warning(f"Could not fetch QR from WhatsApp service: {str(e)}")
        
        # Fallback to database QR
        qr_data = manager.get_instance_qr(instance_id, current_user.organization_id)
        
        if not qr_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not available yet. Please wait for instance to initialize."
            )
        
        return WhatsAppQRResponse(
            qr_code=qr_data.get('qr_code'),
            is_authenticated=qr_data.get('is_authenticated', False),
            expires_at=qr_data.get('expires_at'),
            expired=qr_data.get('expired', False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting QR code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve QR code"
        )


@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_whatsapp_instance(
    instance_id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_MANAGE_INSTANCES))
):
    """
    Delete WhatsApp instance
    
    Requires: whatsapp.manage_instances permission
    """
    try:
        manager = WhatsAppInstanceManager()
        
        # Get instance name for logging
        instance = manager.get_instance(instance_id, current_user.organization_id)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WhatsApp instance not found"
            )
        
        # Delete instance
        success = manager.delete_instance(instance_id, current_user.organization_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete WhatsApp instance"
            )
        
        # Log activity
        ActivityLogger.log_audit(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action="deleted",
            resource_type="whatsapp_instance",
            resource_id=str(instance_id),
            old_values={
                "name": instance['name'],
                "phone_number": instance['phone_number']
            }
        )
        
        logger.info(
            f"WhatsApp instance deleted: {instance['name']} "
            f"(ID: {instance_id}) by {current_user.email}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting WhatsApp instance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete WhatsApp instance"
        )


@router.post("/send", response_model=WhatsAppMessageResponse)
async def send_whatsapp_message(
    message_data: SendWhatsAppMessageRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_SEND))
):
    """
    Send WhatsApp message from specific instance
    
    Requires: whatsapp.send permission
    """
    try:
        from ..services.whatsapp_service import WhatsAppService
        from ..database import get_db_cursor
        import uuid
        
        manager = WhatsAppInstanceManager()
        
        # Verify instance belongs to organization and is authenticated
        instance = manager.get_instance(message_data.instance_id, current_user.organization_id)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WhatsApp instance not found"
            )
        
        if not instance['is_authenticated']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp instance is not authenticated. Please scan QR code first."
            )
        
        if not instance['is_active']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp instance is not active"
            )
        
        # Check message limit
        limit_check = manager.check_message_limit(message_data.instance_id, current_user.organization_id)
        
        if not limit_check['can_send']:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily message limit reached ({limit_check['limit']}). Try again tomorrow."
            )
        
        # Get contact name if contact_id provided
        contact_name = None
        if message_data.contact_id:
            with get_db_cursor(dict_cursor=True) as cursor:
                cursor.execute("""
                    SELECT full_name FROM contacts
                    WHERE id = %s AND organization_id = %s
                """, (message_data.contact_id, current_user.organization_id))
                
                contact = cursor.fetchone()
                if contact:
                    contact_name = contact['full_name']
        
        # Queue message with instance_id
        message_id = str(uuid.uuid4())
        
        whatsapp_service = WhatsAppService()
        
        # Add instance_id to message data
        import pika
        import json
        
        message_payload = {
            'message_id': message_id,
            'instance_id': message_data.instance_id,
            'phone_number': message_data.phone_number,
            'message': message_data.message,
            'contact_name': contact_name or message_data.phone_number,
            'queued_at': datetime.now().isoformat()
        }
        
        whatsapp_service.channel.basic_publish(
            exchange='',
            routing_key=whatsapp_service.MESSAGE_QUEUE,
            body=json.dumps(message_payload),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json'
            )
        )
        
        whatsapp_service.close()
        
        # Log message in database
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO whatsapp_messages (
                    organization_id,
                    whatsapp_instance_id,
                    phone_number,
                    message,
                    direction,
                    contact_id,
                    status,
                    sent_by
                )
                VALUES (%s, %s, %s, %s, 'outbound', %s, 'queued', %s)
            """, (
                current_user.organization_id,
                message_data.instance_id,
                message_data.phone_number,
                message_data.message,
                message_data.contact_id,
                current_user.id
            ))
        
        # Log activity
        if message_data.contact_id:
            ActivityLogger.log_whatsapp_message(
                organization_id=current_user.organization_id,
                title=f"WhatsApp message sent",
                description=message_data.message[:200],
                created_by=current_user.id,
                contact_id=message_data.contact_id,
                message_id=message_id
            )
        
        logger.info(
            f"WhatsApp message queued: {message_id} to {message_data.phone_number} "
            f"via instance {message_data.instance_id} by {current_user.email}"
        )
        
        return WhatsAppMessageResponse(
            success=True,
            message="Message queued successfully",
            message_id=message_id,
            instance_id=message_data.instance_id,
            phone_number=message_data.phone_number
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send WhatsApp message"
        )


@router.get("/messages", response_model=List[WhatsAppMessageHistoryResponse])
async def get_whatsapp_messages(
    current_user: CurrentUser = Depends(require_permission(Permission.WHATSAPP_READ)),
    limit: int = 100,
    offset: int = 0,
    instance_id: Optional[int] = None,
    contact_id: Optional[int] = None
):
    """
    Get WhatsApp message history
    
    Requires: whatsapp.read permission
    """
    try:
        from ..database import get_db_cursor
        
        with get_db_cursor(dict_cursor=True) as cursor:
            # Build query with filters
            where_clauses = ["wm.organization_id = %s"]
            params = [current_user.organization_id]
            
            if instance_id is not None:
                where_clauses.append("wm.whatsapp_instance_id = %s")
                params.append(instance_id)
            
            if contact_id is not None:
                where_clauses.append("wm.contact_id = %s")
                params.append(contact_id)
            
            params.extend([limit, offset])
            
            cursor.execute(f"""
                SELECT 
                    wm.id,
                    wm.phone_number,
                    wm.message,
                    wm.direction,
                    wm.status,
                    c.full_name as contact_name,
                    wi.name as whatsapp_instance_name,
                    wm.queued_at,
                    wm.sent_at,
                    wm.delivered_at
                FROM whatsapp_messages wm
                JOIN whatsapp_instances wi ON wi.id = wm.whatsapp_instance_id
                LEFT JOIN contacts c ON c.id = wm.contact_id
                WHERE {' AND '.join(where_clauses)}
                ORDER BY wm.queued_at DESC
                LIMIT %s OFFSET %s
            """, params)
            
            messages = cursor.fetchall()
            
            return [
                WhatsAppMessageHistoryResponse(
                    id=m['id'],
                    phone_number=m['phone_number'],
                    message=m['message'],
                    direction=m['direction'],
                    status=m['status'],
                    contact_name=m.get('contact_name'),
                    whatsapp_instance_name=m['whatsapp_instance_name'],
                    queued_at=m['queued_at'].isoformat(),
                    sent_at=m['sent_at'].isoformat() if m.get('sent_at') else None,
                    delivered_at=m['delivered_at'].isoformat() if m.get('delivered_at') else None
                )
                for m in messages
            ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting WhatsApp messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WhatsApp messages"
        )

