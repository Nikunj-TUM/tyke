"""
User and authentication API endpoints
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from slugify import slugify

from ..auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_password,
    verify_password,
    get_current_user,
    require_permission,
    Permission
)
from ..auth.models import (
    SignupRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
    InviteUserRequest,
    UpdateUserRoleRequest,
    UserPermissionsResponse
)
from ..auth.dependencies import CurrentUser, require_role
from ..auth.password_utils import is_strong_password
from ..auth.permissions import get_user_permissions
from ..database import get_db_cursor
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Authentication & Users"])


@router.post("/auth/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(signup_data: SignupRequest):
    """
    Create new organization and owner user
    
    This endpoint:
    1. Creates a new organization
    2. Creates the owner user account
    3. Returns JWT tokens
    """
    # Validate password strength
    is_valid, error_message = is_strong_password(signup_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (signup_data.email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Generate slug if not provided
            slug = signup_data.organization_slug
            if not slug:
                slug = slugify(signup_data.organization_name)
            
            # Check if slug already exists
            cursor.execute("SELECT id FROM organizations WHERE slug = %s", (slug,))
            if cursor.fetchone():
                # Append timestamp to make it unique
                slug = f"{slug}-{int(datetime.utcnow().timestamp())}"
            
            # Create organization
            cursor.execute("""
                INSERT INTO organizations (name, slug, subscription_status, subscription_plan)
                VALUES (%s, %s, 'trial', 'basic')
                RETURNING id, name, slug
            """, (signup_data.organization_name, slug))
            
            org_data = cursor.fetchone()
            organization_id = org_data['id']
            
            # Hash password
            password_hash = hash_password(signup_data.password)
            
            # Create owner user
            cursor.execute("""
                INSERT INTO users (
                    organization_id,
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    phone,
                    role,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'owner', TRUE)
                RETURNING id, email, first_name, last_name, role
            """, (
                organization_id,
                signup_data.email,
                password_hash,
                signup_data.first_name,
                signup_data.last_name,
                signup_data.phone
            ))
            
            user_data = cursor.fetchone()
            
            # Create JWT tokens
            token_data = {
                "user_id": user_data['id'],
                "email": user_data['email'],
                "organization_id": organization_id,
                "role": user_data['role']
            }
            
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token({"user_id": user_data['id']})
            
            logger.info(f"New organization created: {org_data['name']} (ID: {organization_id})")
            logger.info(f"Owner user created: {user_data['email']} (ID: {user_data['id']})")
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user={
                    "id": user_data['id'],
                    "email": user_data['email'],
                    "first_name": user_data['first_name'],
                    "last_name": user_data['last_name'],
                    "role": user_data['role'],
                    "organization_id": organization_id,
                    "organization_name": org_data['name']
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during signup: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account. Please try again."
        )


@router.post("/auth/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """
    User login
    
    Returns JWT access and refresh tokens
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Get user with organization info
            cursor.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.password_hash,
                    u.first_name,
                    u.last_name,
                    u.role,
                    u.is_active,
                    u.organization_id,
                    o.name as organization_name,
                    o.is_active as organization_is_active
                FROM users u
                JOIN organizations o ON o.id = u.organization_id
                WHERE u.email = %s
            """, (login_data.email,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Verify password
            if not verify_password(login_data.password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Check if user is active
            if not user['is_active']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )
            
            # Check if organization is active
            if not user['organization_is_active']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization is inactive"
                )
            
            # Update last login
            cursor.execute("""
                UPDATE users
                SET last_login_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (user['id'],))
            
            # Create JWT tokens
            token_data = {
                "user_id": user['id'],
                "email": user['email'],
                "organization_id": user['organization_id'],
                "role": user['role']
            }
            
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token({"user_id": user['id']})
            
            logger.info(f"User logged in: {user['email']} (ID: {user['id']})")
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user={
                    "id": user['id'],
                    "email": user['email'],
                    "first_name": user['first_name'],
                    "last_name": user['last_name'],
                    "role": user['role'],
                    "organization_id": user['organization_id'],
                    "organization_name": user['organization_name']
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(refresh_data: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    # Verify refresh token
    payload = verify_token(refresh_data.refresh_token, token_type="refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Get user data
            cursor.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    u.role,
                    u.is_active,
                    u.organization_id,
                    o.name as organization_name
                FROM users u
                JOIN organizations o ON o.id = u.organization_id
                WHERE u.id = %s AND u.is_active = TRUE AND o.is_active = TRUE
            """, (user_id,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            # Create new tokens
            token_data = {
                "user_id": user['id'],
                "email": user['email'],
                "organization_id": user['organization_id'],
                "role": user['role']
            }
            
            access_token = create_access_token(token_data)
            new_refresh_token = create_refresh_token({"user_id": user['id']})
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user={
                    "id": user['id'],
                    "email": user['email'],
                    "first_name": user['first_name'],
                    "last_name": user['last_name'],
                    "role": user['role'],
                    "organization_id": user['organization_id'],
                    "organization_name": user['organization_name']
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )


@router.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser = Depends(get_current_user)):
    """Get current user information"""
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    u.phone,
                    u.role,
                    u.is_active,
                    u.organization_id,
                    u.created_at,
                    o.name as organization_name
                FROM users u
                JOIN organizations o ON o.id = u.organization_id
                WHERE u.id = %s
            """, (current_user.id,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return UserResponse(
                id=user['id'],
                email=user['email'],
                first_name=user['first_name'],
                last_name=user['last_name'],
                phone=user['phone'],
                role=user['role'],
                is_active=user['is_active'],
                organization_id=user['organization_id'],
                organization_name=user['organization_name'],
                created_at=user['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )


@router.get("/users/me/permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(current_user: CurrentUser = Depends(get_current_user)):
    """Get current user's permissions"""
    permissions = get_user_permissions(current_user.id)
    
    return UserPermissionsResponse(
        user_id=current_user.id,
        role=current_user.role,
        permissions=permissions
    )


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_READ))
):
    """
    List all users in the organization
    
    Requires: users.read permission (admin+)
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    u.phone,
                    u.role,
                    u.is_active,
                    u.organization_id,
                    u.created_at,
                    o.name as organization_name
                FROM users u
                JOIN organizations o ON o.id = u.organization_id
                WHERE u.organization_id = %s
                ORDER BY u.created_at DESC
            """, (current_user.organization_id,))
            
            users = cursor.fetchall()
            
            return [
                UserResponse(
                    id=u['id'],
                    email=u['email'],
                    first_name=u['first_name'],
                    last_name=u['last_name'],
                    phone=u['phone'],
                    role=u['role'],
                    is_active=u['is_active'],
                    organization_id=u['organization_id'],
                    organization_name=u['organization_name'],
                    created_at=u['created_at'].isoformat()
                )
                for u in users
            ]
            
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    invite_data: InviteUserRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_INVITE))
):
    """
    Invite a new user to the organization
    
    Requires: users.invite permission (admin+)
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (invite_data.email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )
            
            # Generate temporary password (should be sent via email in production)
            temp_password = f"TempPass{int(datetime.utcnow().timestamp())}"
            password_hash = hash_password(temp_password)
            
            # Create user
            cursor.execute("""
                INSERT INTO users (
                    organization_id,
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    role,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s::user_role_enum, TRUE)
                RETURNING id, email, first_name, last_name, role, created_at
            """, (
                current_user.organization_id,
                invite_data.email,
                password_hash,
                invite_data.first_name,
                invite_data.last_name,
                invite_data.role
            ))
            
            user = cursor.fetchone()
            
            # Get organization name
            cursor.execute(
                "SELECT name FROM organizations WHERE id = %s",
                (current_user.organization_id,)
            )
            org = cursor.fetchone()
            
            logger.info(
                f"User invited: {user['email']} (ID: {user['id']}) "
                f"by {current_user.email}"
            )
            
            # TODO: Send invitation email with temporary password
            logger.warning(f"Temporary password for {user['email']}: {temp_password}")
            
            return UserResponse(
                id=user['id'],
                email=user['email'],
                first_name=user['first_name'],
                last_name=user['last_name'],
                phone=None,
                role=user['role'],
                is_active=True,
                organization_id=current_user.organization_id,
                organization_name=org['name'],
                created_at=user['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inviting user: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite user"
        )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_data: UpdateUserRoleRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE))
):
    """
    Update user role
    
    Requires: users.manage permission (admin+)
    """
    # Can't change own role
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Verify user belongs to same organization
            cursor.execute("""
                SELECT id, organization_id, role
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            if user['organization_id'] != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot modify users from other organizations"
                )
            
            # Update role
            cursor.execute("""
                UPDATE users
                SET role = %s::user_role_enum
                WHERE id = %s
                RETURNING id, email, first_name, last_name, phone, role, is_active, organization_id, created_at
            """, (role_data.role, user_id))
            
            updated_user = cursor.fetchone()
            
            # Get organization name
            cursor.execute(
                "SELECT name FROM organizations WHERE id = %s",
                (current_user.organization_id,)
            )
            org = cursor.fetchone()
            
            logger.info(
                f"User role updated: {updated_user['email']} "
                f"from {user['role']} to {updated_user['role']} "
                f"by {current_user.email}"
            )
            
            return UserResponse(
                id=updated_user['id'],
                email=updated_user['email'],
                first_name=updated_user['first_name'],
                last_name=updated_user['last_name'],
                phone=updated_user['phone'],
                role=updated_user['role'],
                is_active=updated_user['is_active'],
                organization_id=updated_user['organization_id'],
                organization_name=org['name'],
                created_at=updated_user['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_role(['owner']))
):
    """
    Delete user (only owner can do this)
    
    Requires: owner role
    """
    # Can't delete self
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    try:
        with get_db_cursor() as cursor:
            # Verify user belongs to same organization
            cursor.execute("""
                SELECT id, organization_id, email
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            if user[1] != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete users from other organizations"
                )
            
            # Delete user
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            
            logger.info(f"User deleted: {user[2]} (ID: {user_id}) by {current_user.email}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

