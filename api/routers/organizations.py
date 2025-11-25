"""
Organization management API endpoints
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import get_current_user, require_permission, Permission
from ..auth.dependencies import CurrentUser
from ..database import get_db_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class OrganizationResponse(BaseModel):
    """Organization details response"""
    id: int
    name: str
    slug: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    subscription_status: str
    subscription_plan: str
    is_active: bool
    created_at: str


class OrganizationStatsResponse(BaseModel):
    """Organization statistics"""
    companies_count: int
    contacts_count: int
    deals_count: int
    active_campaigns_count: int
    whatsapp_instances_count: int


class UpdateOrganizationRequest(BaseModel):
    """Update organization request"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get current user's organization"""
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    name,
                    slug,
                    email,
                    phone,
                    website,
                    subscription_status,
                    subscription_plan,
                    is_active,
                    created_at
                FROM organizations
                WHERE id = %s
            """, (current_user.organization_id,))
            
            org = cursor.fetchone()
            
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
            
            return OrganizationResponse(
                id=org['id'],
                name=org['name'],
                slug=org['slug'],
                email=org['email'],
                phone=org['phone'],
                website=org['website'],
                subscription_status=org['subscription_status'],
                subscription_plan=org['subscription_plan'],
                is_active=org['is_active'],
                created_at=org['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organization"
        )


@router.patch("/me", response_model=OrganizationResponse)
async def update_my_organization(
    update_data: UpdateOrganizationRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.SETTINGS_WRITE))
):
    """
    Update organization details
    
    Requires: settings.write permission (owner, admin, manager)
    """
    try:
        with get_db_cursor(dict_cursor=True) as cursor:
            # Build update query dynamically based on provided fields
            update_fields = []
            params = []
            
            if update_data.name is not None:
                update_fields.append("name = %s")
                params.append(update_data.name)
            
            if update_data.email is not None:
                update_fields.append("email = %s")
                params.append(update_data.email)
            
            if update_data.phone is not None:
                update_fields.append("phone = %s")
                params.append(update_data.phone)
            
            if update_data.website is not None:
                update_fields.append("website = %s")
                params.append(update_data.website)
            
            if not update_fields:
                # No fields to update, just return current data
                cursor.execute("""
                    SELECT 
                        id, name, slug, email, phone, website,
                        subscription_status, subscription_plan, is_active, created_at
                    FROM organizations
                    WHERE id = %s
                """, (current_user.organization_id,))
                org = cursor.fetchone()
            else:
                # Update organization
                update_query = f"""
                    UPDATE organizations
                    SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING 
                        id, name, slug, email, phone, website,
                        subscription_status, subscription_plan, is_active, created_at
                """
                params.append(current_user.organization_id)
                
                cursor.execute(update_query, params)
                org = cursor.fetchone()
                
                logger.info(
                    f"Organization updated: {org['name']} (ID: {org['id']}) "
                    f"by {current_user.email}"
                )
            
            return OrganizationResponse(
                id=org['id'],
                name=org['name'],
                slug=org['slug'],
                email=org['email'],
                phone=org['phone'],
                website=org['website'],
                subscription_status=org['subscription_status'],
                subscription_plan=org['subscription_plan'],
                is_active=org['is_active'],
                created_at=org['created_at'].isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization"
        )


@router.get("/me/stats", response_model=OrganizationStatsResponse)
async def get_organization_stats(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get organization statistics for dashboard"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM get_organization_stats(%s)",
                (current_user.organization_id,)
            )
            
            stats = cursor.fetchone()
            
            return OrganizationStatsResponse(
                companies_count=stats[0] or 0,
                contacts_count=stats[1] or 0,
                deals_count=stats[2] or 0,
                active_campaigns_count=stats[3] or 0,
                whatsapp_instances_count=stats[4] or 0
            )
            
    except Exception as e:
        logger.error(f"Error getting organization stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )

