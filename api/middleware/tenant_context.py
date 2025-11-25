"""
Tenant context middleware for multi-tenancy
Automatically extracts and injects organization_id from JWT into request state
"""
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and inject organization_id into request state
    
    This middleware:
    1. Extracts JWT token from Authorization header
    2. Decodes token to get organization_id
    3. Stores organization_id in request.state
    4. Makes it available to all route handlers
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and inject tenant context"""
        # Initialize organization_id in request state
        request.state.organization_id = None
        request.state.user_id = None
        
        # Skip auth for health check and public endpoints
        public_paths = ['/health', '/docs', '/openapi.json', '/redoc']
        if any(request.url.path.startswith(path) for path in public_paths):
            response = await call_next(request)
            return response
        
        # Extract organization_id from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            # Decode token to get organization_id (without full validation)
            # Full validation happens in get_current_user dependency
            try:
                from ..auth.jwt_handler import decode_token_without_verification
                payload = decode_token_without_verification(token)
                
                if payload:
                    request.state.organization_id = payload.get('organization_id')
                    request.state.user_id = payload.get('user_id')
                    logger.debug(
                        f"Tenant context: organization_id={request.state.organization_id}, "
                        f"user_id={request.state.user_id}"
                    )
            except Exception as e:
                logger.warning(f"Error extracting tenant context from token: {str(e)}")
        
        response = await call_next(request)
        return response


def get_organization_id(request: Request) -> Optional[int]:
    """
    Get organization_id from request state
    
    Args:
        request: FastAPI request object
        
    Returns:
        Organization ID or None
    """
    return getattr(request.state, 'organization_id', None)


def require_organization_context(request: Request) -> int:
    """
    Require organization_id to be present in request state
    
    Args:
        request: FastAPI request object
        
    Returns:
        Organization ID
        
    Raises:
        HTTPException: If organization_id is not in request state
    """
    organization_id = get_organization_id(request)
    
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization context not found. Authentication required."
        )
    
    return organization_id

