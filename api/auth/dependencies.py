"""
FastAPI dependencies for authentication and authorization
"""
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .jwt_handler import verify_token
from .permissions import check_permission
from ..database import get_db_cursor

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer()


class CurrentUser:
    """Current user model"""
    def __init__(
        self,
        id: int,
        email: str,
        organization_id: int,
        role: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: bool = True
    ):
        self.id = id
        self.email = email
        self.organization_id = organization_id
        self.role = role
        self.first_name = first_name
        self.last_name = last_name
        self.is_active = is_active
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "organization_id": self.organization_id,
            "role": self.role,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "is_active": self.is_active
        }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Get current user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        CurrentUser instance
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise credentials_exception
    
    # Extract user info from token
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    if user_id is None or email is None:
        raise credentials_exception
    
    # Fetch user from database to ensure they still exist and are active
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.organization_id,
                    u.role,
                    u.first_name,
                    u.last_name,
                    u.is_active,
                    o.is_active as organization_is_active
                FROM users u
                JOIN organizations o ON o.id = u.organization_id
                WHERE u.id = %s
            """, (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                raise credentials_exception
            
            # Check if user and organization are active
            if not user_data['is_active']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )
            
            if not user_data['organization_is_active']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization is inactive"
                )
            
            return CurrentUser(
                id=user_data['id'],
                email=user_data['email'],
                organization_id=user_data['organization_id'],
                role=user_data['role'],
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                is_active=user_data['is_active']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user: {str(e)}")
        raise credentials_exception


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Get current active user (redundant check, but explicit)
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        CurrentUser instance
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


def require_permission(permission: str):
    """
    Dependency factory to require a specific permission
    
    Args:
        permission: Permission name (e.g., "companies.write")
        
    Returns:
        Dependency function that checks permission
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has required permission"""
        has_permission = check_permission(current_user.id, permission)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: {permission}"
            )
        
        return current_user
    
    return permission_checker


def require_role(allowed_roles: list[str]):
    """
    Dependency factory to require specific roles
    
    Args:
        allowed_roles: List of allowed roles
        
    Returns:
        Dependency function that checks role
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has required role"""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        
        return current_user
    
    return role_checker

