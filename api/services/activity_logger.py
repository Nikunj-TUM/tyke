"""
Activity logging service for audit trail and CRM activities
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from ..database import get_db_cursor

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Service for logging activities and audit trail"""
    
    @staticmethod
    def log_activity(
        organization_id: int,
        activity_type: str,
        title: str,
        description: Optional[str] = None,
        created_by: Optional[int] = None,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        due_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Log a CRM activity
        
        Args:
            organization_id: Organization ID
            activity_type: Type of activity (note, call, meeting, email, task, whatsapp)
            title: Activity title
            description: Activity description
            created_by: User ID who created the activity
            company_id: Related company ID
            contact_id: Related contact ID
            deal_id: Related deal ID
            assigned_to: User ID assigned to the activity
            due_date: Due date for tasks/meetings
            metadata: Additional metadata as JSON
            
        Returns:
            Activity ID if successful, None otherwise
        """
        try:
            import json
            
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO activities (
                        organization_id,
                        type,
                        title,
                        description,
                        company_id,
                        contact_id,
                        deal_id,
                        assigned_to,
                        created_by,
                        due_date,
                        metadata
                    )
                    VALUES (%s, %s::activity_type_enum, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    organization_id,
                    activity_type,
                    title,
                    description,
                    company_id,
                    contact_id,
                    deal_id,
                    assigned_to,
                    created_by,
                    due_date,
                    json.dumps(metadata) if metadata else None
                ))
                
                result = cursor.fetchone()
                activity_id = result[0] if result else None
                
                logger.info(
                    f"Activity logged: {activity_type} - {title} "
                    f"(ID: {activity_id}, Org: {organization_id})"
                )
                
                return activity_id
                
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")
            return None
    
    @staticmethod
    def log_audit(
        organization_id: int,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[int]:
        """
        Log an audit trail entry
        
        Args:
            organization_id: Organization ID
            user_id: User ID who performed the action
            action: Action performed (created, updated, deleted, etc.)
            resource_type: Type of resource (company, contact, deal, etc.)
            resource_id: ID of the resource
            old_values: Old values (for updates)
            new_values: New values (for creates/updates)
            ip_address: IP address of request
            user_agent: User agent of request
            
        Returns:
            Audit log ID if successful, None otherwise
        """
        try:
            import json
            
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO audit_logs (
                        organization_id,
                        user_id,
                        action,
                        resource_type,
                        resource_id,
                        old_values,
                        new_values,
                        ip_address,
                        user_agent
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    organization_id,
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    ip_address,
                    user_agent
                ))
                
                result = cursor.fetchone()
                log_id = result[0] if result else None
                
                logger.debug(
                    f"Audit log: {action} {resource_type}:{resource_id} "
                    f"by user:{user_id} (Org: {organization_id})"
                )
                
                return log_id
                
        except Exception as e:
            logger.error(f"Error logging audit: {str(e)}")
            return None
    
    @staticmethod
    def log_note(
        organization_id: int,
        title: str,
        description: str,
        created_by: int,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None
    ) -> Optional[int]:
        """Log a note activity"""
        return ActivityLogger.log_activity(
            organization_id=organization_id,
            activity_type='note',
            title=title,
            description=description,
            created_by=created_by,
            company_id=company_id,
            contact_id=contact_id,
            deal_id=deal_id
        )
    
    @staticmethod
    def log_call(
        organization_id: int,
        title: str,
        description: str,
        created_by: int,
        contact_id: Optional[int] = None,
        company_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        duration_minutes: Optional[int] = None
    ) -> Optional[int]:
        """Log a call activity"""
        metadata = {}
        if duration_minutes is not None:
            metadata['duration_minutes'] = duration_minutes
        
        return ActivityLogger.log_activity(
            organization_id=organization_id,
            activity_type='call',
            title=title,
            description=description,
            created_by=created_by,
            company_id=company_id,
            contact_id=contact_id,
            deal_id=deal_id,
            metadata=metadata if metadata else None
        )
    
    @staticmethod
    def log_meeting(
        organization_id: int,
        title: str,
        description: str,
        created_by: int,
        due_date: datetime,
        assigned_to: Optional[int] = None,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None
    ) -> Optional[int]:
        """Log a meeting activity"""
        return ActivityLogger.log_activity(
            organization_id=organization_id,
            activity_type='meeting',
            title=title,
            description=description,
            created_by=created_by,
            assigned_to=assigned_to,
            due_date=due_date,
            company_id=company_id,
            contact_id=contact_id,
            deal_id=deal_id
        )
    
    @staticmethod
    def log_task(
        organization_id: int,
        title: str,
        description: str,
        created_by: int,
        assigned_to: int,
        due_date: datetime,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None
    ) -> Optional[int]:
        """Log a task activity"""
        return ActivityLogger.log_activity(
            organization_id=organization_id,
            activity_type='task',
            title=title,
            description=description,
            created_by=created_by,
            assigned_to=assigned_to,
            due_date=due_date,
            company_id=company_id,
            contact_id=contact_id,
            deal_id=deal_id
        )
    
    @staticmethod
    def log_whatsapp_message(
        organization_id: int,
        title: str,
        description: str,
        created_by: int,
        contact_id: int,
        company_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> Optional[int]:
        """Log a WhatsApp message activity"""
        metadata = {}
        if message_id:
            metadata['whatsapp_message_id'] = message_id
        
        return ActivityLogger.log_activity(
            organization_id=organization_id,
            activity_type='whatsapp',
            title=title,
            description=description,
            created_by=created_by,
            company_id=company_id,
            contact_id=contact_id,
            deal_id=deal_id,
            metadata=metadata if metadata else None
        )
    
    @staticmethod
    def complete_activity(activity_id: int) -> bool:
        """Mark an activity as completed"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE activities
                    SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (activity_id,))
                
                logger.info(f"Activity {activity_id} marked as completed")
                return True
                
        except Exception as e:
            logger.error(f"Error completing activity: {str(e)}")
            return False
    
    @staticmethod
    def get_activities(
        organization_id: int,
        company_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        assigned_to: Optional[int] = None,
        activity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Get activities with optional filters
        
        Args:
            organization_id: Organization ID
            company_id: Filter by company
            contact_id: Filter by contact
            deal_id: Filter by deal
            assigned_to: Filter by assigned user
            activity_type: Filter by activity type
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of activity dictionaries
        """
        try:
            with get_db_cursor(dict_cursor=True) as cursor:
                # Build query with filters
                where_clauses = ["organization_id = %s"]
                params = [organization_id]
                
                if company_id is not None:
                    where_clauses.append("company_id = %s")
                    params.append(company_id)
                
                if contact_id is not None:
                    where_clauses.append("contact_id = %s")
                    params.append(contact_id)
                
                if deal_id is not None:
                    where_clauses.append("deal_id = %s")
                    params.append(deal_id)
                
                if assigned_to is not None:
                    where_clauses.append("assigned_to = %s")
                    params.append(assigned_to)
                
                if activity_type is not None:
                    where_clauses.append("type = %s::activity_type_enum")
                    params.append(activity_type)
                
                params.extend([limit, offset])
                
                query = f"""
                    SELECT 
                        id,
                        type,
                        title,
                        description,
                        company_id,
                        contact_id,
                        deal_id,
                        assigned_to,
                        created_by,
                        due_date,
                        completed,
                        completed_at,
                        metadata,
                        created_at
                    FROM activities
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                cursor.execute(query, params)
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"Error getting activities: {str(e)}")
            return []

