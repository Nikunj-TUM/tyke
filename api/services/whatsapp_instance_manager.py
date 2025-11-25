"""
WhatsApp Instance Manager Service
Manages multiple WhatsApp instances per organization
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from ..database import get_db_cursor

logger = logging.getLogger(__name__)


class WhatsAppInstanceManager:
    """Manage WhatsApp instances for multi-tenant support"""
    
    def create_instance(
        self,
        organization_id: int,
        name: str,
        phone_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new WhatsApp instance
        
        Args:
            organization_id: Organization ID
            name: Instance name/label
            phone_number: Phone number for this instance
            
        Returns:
            Created instance data or None if failed
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                # Check if phone number already exists for this org
                cursor.execute("""
                    SELECT id FROM whatsapp_instances
                    WHERE organization_id = %s AND phone_number = %s
                """, (organization_id, phone_number))
                
                if cursor.fetchone():
                    logger.warning(f"Phone number {phone_number} already exists for org {organization_id}")
                    return None
                
                # Create instance
                cursor.execute("""
                    INSERT INTO whatsapp_instances (
                        organization_id,
                        name,
                        phone_number,
                        is_active,
                        is_authenticated,
                        daily_message_limit
                    )
                    VALUES (%s, %s, %s, TRUE, FALSE, 1000)
                    RETURNING id, name, phone_number, is_active, is_authenticated, created_at
                """, (organization_id, name, phone_number))
                
                instance = cursor.fetchone()
                logger.info(
                    f"Created WhatsApp instance: {instance['name']} "
                    f"(ID: {instance['id']}, Phone: {phone_number})"
                )
                return dict(instance)
                
        except Exception as e:
            logger.error(f"Error creating WhatsApp instance: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_instance(
        self,
        instance_id: int,
        organization_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get instance details
        
        Args:
            instance_id: Instance ID
            organization_id: Organization ID (for tenant isolation)
            
        Returns:
            Instance data or None if not found
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                cursor.execute("""
                    SELECT 
                        id,
                        organization_id,
                        name,
                        phone_number,
                        is_authenticated,
                        is_active,
                        qr_code,
                        qr_expires_at,
                        client_info,
                        last_connected_at,
                        last_disconnected_at,
                        messages_sent_today,
                        daily_message_limit,
                        last_message_sent_at,
                        created_at,
                        updated_at
                    FROM whatsapp_instances
                    WHERE id = %s AND organization_id = %s
                """, (instance_id, organization_id))
                
                instance = cursor.fetchone()
                return dict(instance) if instance else None
                
        except Exception as e:
            logger.error(f"Error getting instance: {str(e)}")
            return None
    
    def list_instances(
        self,
        organization_id: int,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all instances for an organization
        
        Args:
            organization_id: Organization ID
            active_only: If True, only return active instances
            
        Returns:
            List of instance data dictionaries
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                query = """
                    SELECT 
                        id,
                        name,
                        phone_number,
                        is_authenticated,
                        is_active,
                        last_connected_at,
                        messages_sent_today,
                        daily_message_limit,
                        created_at
                    FROM whatsapp_instances
                    WHERE organization_id = %s
                """
                params = [organization_id]
                
                if active_only:
                    query += " AND is_active = TRUE"
                
                query += " ORDER BY created_at DESC"
                
                cursor.execute(query, params)
                instances = cursor.fetchall()
                return [dict(i) for i in instances]
                
        except Exception as e:
            logger.error(f"Error listing instances: {str(e)}")
            return []
    
    def update_instance_status(
        self,
        instance_id: int,
        is_authenticated: bool,
        qr_code: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update instance authentication status
        
        Args:
            instance_id: Instance ID
            is_authenticated: Authentication status
            qr_code: QR code string (if pending auth)
            client_info: Client information (if authenticated)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import json
            
            with get_db_cursor() as cursor:
                # Calculate QR expiry (5 minutes from now)
                qr_expires_at = None
                if qr_code and not is_authenticated:
                    qr_expires_at = datetime.utcnow() + timedelta(minutes=5)
                
                cursor.execute("""
                    UPDATE whatsapp_instances
                    SET 
                        is_authenticated = %s,
                        qr_code = %s,
                        qr_expires_at = %s,
                        client_info = %s,
                        last_connected_at = CASE 
                            WHEN %s THEN CURRENT_TIMESTAMP 
                            ELSE last_connected_at 
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    is_authenticated,
                    qr_code,
                    qr_expires_at,
                    json.dumps(client_info) if client_info else None,
                    is_authenticated,
                    instance_id
                ))
                
                logger.info(
                    f"Updated instance {instance_id} status: "
                    f"authenticated={is_authenticated}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Error updating instance status: {str(e)}")
            return False
    
    def update_instance_disconnected(self, instance_id: int) -> bool:
        """
        Mark instance as disconnected
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE whatsapp_instances
                    SET 
                        is_authenticated = FALSE,
                        qr_code = NULL,
                        qr_expires_at = NULL,
                        last_disconnected_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (instance_id,))
                
                logger.info(f"Marked instance {instance_id} as disconnected")
                return True
                
        except Exception as e:
            logger.error(f"Error marking instance as disconnected: {str(e)}")
            return False
    
    def delete_instance(
        self,
        instance_id: int,
        organization_id: int
    ) -> bool:
        """
        Delete a WhatsApp instance
        
        Args:
            instance_id: Instance ID
            organization_id: Organization ID (for tenant isolation)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_cursor() as cursor:
                # Delete instance (cascades to related records)
                cursor.execute("""
                    DELETE FROM whatsapp_instances
                    WHERE id = %s AND organization_id = %s
                """, (instance_id, organization_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"Deleted WhatsApp instance: {instance_id}")
                    return True
                else:
                    logger.warning(f"Instance {instance_id} not found or doesn't belong to org {organization_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Error deleting instance: {str(e)}")
            return False
    
    def get_instance_qr(
        self,
        instance_id: int,
        organization_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get QR code for instance authentication
        
        Args:
            instance_id: Instance ID
            organization_id: Organization ID
            
        Returns:
            QR code data or None
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                cursor.execute("""
                    SELECT 
                        qr_code,
                        qr_expires_at,
                        is_authenticated
                    FROM whatsapp_instances
                    WHERE id = %s AND organization_id = %s
                """, (instance_id, organization_id))
                
                result = cursor.fetchone()
                
                if not result:
                    return None
                
                # Check if QR is expired
                if result['qr_expires_at'] and result['qr_expires_at'] < datetime.utcnow():
                    logger.info(f"QR code for instance {instance_id} has expired")
                    return {
                        'qr_code': None,
                        'expired': True,
                        'is_authenticated': result['is_authenticated']
                    }
                
                return {
                    'qr_code': result['qr_code'],
                    'expires_at': result['qr_expires_at'].isoformat() if result['qr_expires_at'] else None,
                    'is_authenticated': result['is_authenticated'],
                    'expired': False
                }
                
        except Exception as e:
            logger.error(f"Error getting QR code: {str(e)}")
            return None
    
    def increment_message_count(self, instance_id: int) -> bool:
        """
        Increment daily message count for an instance
        
        Args:
            instance_id: Instance ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE whatsapp_instances
                    SET 
                        messages_sent_today = messages_sent_today + 1,
                        last_message_sent_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (instance_id,))
                
                return True
                
        except Exception as e:
            logger.error(f"Error incrementing message count: {str(e)}")
            return False
    
    def reset_daily_message_counts(self) -> int:
        """
        Reset daily message counts for all instances
        Should be run daily via cron/scheduler
        
        Returns:
            Number of instances reset
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE whatsapp_instances
                    SET messages_sent_today = 0
                    WHERE messages_sent_today > 0
                """)
                
                count = cursor.rowcount
                logger.info(f"Reset daily message counts for {count} instances")
                return count
                
        except Exception as e:
            logger.error(f"Error resetting message counts: {str(e)}")
            return 0
    
    def check_message_limit(
        self,
        instance_id: int,
        organization_id: int
    ) -> Dict[str, Any]:
        """
        Check if instance can send more messages today
        
        Args:
            instance_id: Instance ID
            organization_id: Organization ID
            
        Returns:
            Dict with can_send, messages_sent, limit
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                cursor.execute("""
                    SELECT 
                        messages_sent_today,
                        daily_message_limit
                    FROM whatsapp_instances
                    WHERE id = %s AND organization_id = %s AND is_active = TRUE
                """, (instance_id, organization_id))
                
                result = cursor.fetchone()
                
                if not result:
                    return {
                        'can_send': False,
                        'messages_sent': 0,
                        'limit': 0,
                        'error': 'Instance not found or inactive'
                    }
                
                can_send = result['messages_sent_today'] < result['daily_message_limit']
                
                return {
                    'can_send': can_send,
                    'messages_sent': result['messages_sent_today'],
                    'limit': result['daily_message_limit'],
                    'remaining': result['daily_message_limit'] - result['messages_sent_today']
                }
                
        except Exception as e:
            logger.error(f"Error checking message limit: {str(e)}")
            return {
                'can_send': False,
                'messages_sent': 0,
                'limit': 0,
                'error': str(e)
            }
    
    def get_instances_needing_initialization(self) -> List[Dict[str, Any]]:
        """
        Get all instances that need to be initialized in Node.js service
        (active but not yet authenticated)
        
        Returns:
            List of instance data
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                cursor.execute("""
                    SELECT 
                        id,
                        organization_id,
                        name,
                        phone_number,
                        is_authenticated
                    FROM whatsapp_instances
                    WHERE is_active = TRUE
                    ORDER BY created_at ASC
                """)
                
                instances = cursor.fetchall()
                return [dict(i) for i in instances]
                
        except Exception as e:
            logger.error(f"Error getting instances needing initialization: {str(e)}")
            return []
    
    def update_instance_config(
        self,
        instance_id: int,
        organization_id: int,
        name: Optional[str] = None,
        daily_message_limit: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update instance configuration
        
        Args:
            instance_id: Instance ID
            organization_id: Organization ID
            name: New name (optional)
            daily_message_limit: New daily message limit (optional)
            is_active: New active status (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_cursor() as cursor:
                update_fields = []
                params = []
                
                if name is not None:
                    update_fields.append("name = %s")
                    params.append(name)
                
                if daily_message_limit is not None:
                    update_fields.append("daily_message_limit = %s")
                    params.append(daily_message_limit)
                
                if is_active is not None:
                    update_fields.append("is_active = %s")
                    params.append(is_active)
                
                if not update_fields:
                    return True  # Nothing to update
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.extend([instance_id, organization_id])
                
                query = f"""
                    UPDATE whatsapp_instances
                    SET {', '.join(update_fields)}
                    WHERE id = %s AND organization_id = %s
                """
                
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated instance {instance_id} configuration")
                    return True
                else:
                    logger.warning(f"Instance {instance_id} not found")
                    return False
                
        except Exception as e:
            logger.error(f"Error updating instance config: {str(e)}")
            return False

