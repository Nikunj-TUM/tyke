"""
Authentication and authorization module
"""
from .jwt_handler import create_access_token, create_refresh_token, verify_token
from .password_utils import hash_password, verify_password
from .dependencies import get_current_user, get_current_active_user, require_permission
from .permissions import Permission, check_permission

__all__ = [
    'create_access_token',
    'create_refresh_token',
    'verify_token',
    'hash_password',
    'verify_password',
    'get_current_user',
    'get_current_active_user',
    'require_permission',
    'Permission',
    'check_permission',
]

