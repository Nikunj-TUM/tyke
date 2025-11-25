"""
Pydantic models for authentication requests and responses
"""
from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional


class SignupRequest(BaseModel):
    """Organization signup request"""
    # Organization details
    organization_name: str = Field(..., min_length=2, max_length=255)
    organization_slug: Optional[str] = Field(None, min_length=2, max_length=100)
    
    # User details
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    
    @field_validator('organization_slug')
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Validate organization slug format"""
        if v is not None:
            # Must be lowercase alphanumeric with hyphens
            if not v.replace('-', '').replace('_', '').isalnum() or not v.islower():
                raise ValueError('Slug must be lowercase alphanumeric with hyphens only')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Token response after login/signup"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class UserResponse(BaseModel):
    """User details response"""
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    organization_id: int
    organization_name: str
    created_at: str


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class InviteUserRequest(BaseModel):
    """Invite user to organization"""
    email: EmailStr
    role: str = Field(..., pattern="^(owner|admin|manager|agent)$")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class UpdateUserRoleRequest(BaseModel):
    """Update user role"""
    role: str = Field(..., pattern="^(owner|admin|manager|agent)$")


class UserPermissionsResponse(BaseModel):
    """User permissions response"""
    user_id: int
    role: str
    permissions: list[str]

