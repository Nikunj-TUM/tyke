"""
Permission system for role-based access control
"""
import logging
from enum import Enum
from typing import Optional
from ..database import get_db_cursor

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Permission enumeration"""
    # Companies
    COMPANIES_READ = "companies.read"
    COMPANIES_WRITE = "companies.write"
    COMPANIES_DELETE = "companies.delete"
    
    # Contacts
    CONTACTS_READ = "contacts.read"
    CONTACTS_WRITE = "contacts.write"
    CONTACTS_DELETE = "contacts.delete"
    CONTACTS_IMPORT = "contacts.import"
    
    # Deals
    DEALS_READ = "deals.read"
    DEALS_WRITE = "deals.write"
    DEALS_DELETE = "deals.delete"
    
    # Activities
    ACTIVITIES_READ = "activities.read"
    ACTIVITIES_WRITE = "activities.write"
    ACTIVITIES_DELETE = "activities.delete"
    
    # Campaigns
    CAMPAIGNS_READ = "campaigns.read"
    CAMPAIGNS_CREATE = "campaigns.create"
    CAMPAIGNS_EXECUTE = "campaigns.execute"
    CAMPAIGNS_DELETE = "campaigns.delete"
    
    # WhatsApp
    WHATSAPP_READ = "whatsapp.read"
    WHATSAPP_MANAGE_INSTANCES = "whatsapp.manage_instances"
    WHATSAPP_SEND = "whatsapp.send"
    
    # Scraper
    SCRAPER_CREATE_JOBS = "scraper.create_jobs"
    SCRAPER_VIEW_RESULTS = "scraper.view_results"
    
    # Users
    USERS_READ = "users.read"
    USERS_INVITE = "users.invite"
    USERS_MANAGE = "users.manage"
    USERS_DELETE = "users.delete"
    
    # Settings
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"
    SETTINGS_API_KEYS = "settings.api_keys"
    SETTINGS_BILLING = "settings.billing"


def check_permission(user_id: int, permission: str) -> bool:
    """
    Check if a user has a specific permission
    
    Args:
        user_id: User ID
        permission: Permission name (e.g., "companies.write")
        
    Returns:
        True if user has permission, False otherwise
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_has_permission(%s, %s);",
                (user_id, permission)
            )
            result = cursor.fetchone()
            return result[0] if result else False
    except Exception as e:
        logger.error(f"Error checking permission: {str(e)}")
        return False


def get_user_permissions(user_id: int) -> list[str]:
    """
    Get all permissions for a user
    
    Args:
        user_id: User ID
        
    Returns:
        List of permission names
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT p.name
                FROM users u
                JOIN role_permissions rp ON rp.role = u.role
                JOIN permissions p ON p.id = rp.permission_id
                WHERE u.id = %s AND u.is_active = TRUE
                ORDER BY p.name
            """, (user_id,))
            
            results = cursor.fetchall()
            return [row['name'] for row in results]
    except Exception as e:
        logger.error(f"Error getting user permissions: {str(e)}")
        return []


def get_role_permissions(role: str) -> list[str]:
    """
    Get all permissions for a role
    
    Args:
        role: Role name (owner, admin, manager, agent)
        
    Returns:
        List of permission names
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT p.name
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role = %s::user_role_enum
                ORDER BY p.name
            """, (role,))
            
            results = cursor.fetchall()
            return [row['name'] for row in results]
    except Exception as e:
        logger.error(f"Error getting role permissions: {str(e)}")
        return []

