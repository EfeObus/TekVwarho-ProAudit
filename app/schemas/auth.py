"""
TekVwarho ProAudit - Authentication Schemas

Pydantic schemas for authentication requests and responses.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ===========================================
# REQUEST SCHEMAS
# ===========================================

class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    organization_name: str = Field(..., min_length=1, max_length=255)
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordChangeRequest(BaseModel):
    """Schema for password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


# ===========================================
# RESPONSE SCHEMAS
# ===========================================

class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    role: Optional[str] = None  # Organization role (null for platform staff)
    is_active: bool
    is_verified: bool
    organization_id: Optional[UUID] = None  # Null for platform staff
    # RBAC fields
    is_platform_staff: bool = False
    platform_role: Optional[str] = None  # Platform role (null for org users)
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithTokenResponse(BaseModel):
    """Schema for user response with tokens."""
    user: UserResponse
    tokens: TokenResponse


class OrganizationResponse(BaseModel):
    """Schema for organization response."""
    id: UUID
    name: str
    slug: str
    subscription_tier: str
    organization_type: Optional[str] = None  # New: organization type
    verification_status: Optional[str] = None  # New: verification status
    is_verified: bool = False  # New: convenience field
    created_at: datetime
    
    class Config:
        from_attributes = True


class EntityAccessResponse(BaseModel):
    """Schema for entity access response."""
    entity_id: UUID
    entity_name: str
    can_write: bool
    can_delete: bool


class CurrentUserResponse(BaseModel):
    """Schema for current user with organization and entities."""
    user: UserResponse
    organization: Optional[OrganizationResponse] = None  # Null for platform staff
    entity_access: List[EntityAccessResponse] = []
    # RBAC permissions summary
    permissions: List[str] = []  # List of permission strings user has


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# ===========================================
# RBAC SCHEMAS
# ===========================================

class RolePermissionsResponse(BaseModel):
    """Schema for role permissions."""
    role: str
    role_type: str  # "platform" or "organization"
    permissions: List[str]


class UserPermissionsResponse(BaseModel):
    """Schema for user's permissions."""
    user_id: UUID
    is_platform_staff: bool
    role: str
    permissions: List[str]
