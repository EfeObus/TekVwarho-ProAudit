"""
TekVwarho ProAudit - Organization Users Router

API endpoints for managing users within an organization.

Endpoints:
- GET /organizations/{org_id}/users - List organization users
- POST /organizations/{org_id}/users/invite - Invite new user
- PUT /organizations/{org_id}/users/{user_id}/role - Update user role
- POST /organizations/{org_id}/users/{user_id}/deactivate - Deactivate user
- POST /organizations/{org_id}/users/{user_id}/reactivate - Reactivate user
- PUT /organizations/{org_id}/users/{user_id}/entity-access - Update entity access
- POST /me/impersonation - Toggle impersonation permission
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import (
    get_current_active_user,
    require_organization_permission,
)
from app.models.user import User, UserRole
from app.services.organization_user_service import OrganizationUserService
from app.utils.permissions import OrganizationPermission


router = APIRouter(prefix="/organizations", tags=["Organization Users"])


# ===========================================
# REQUEST/RESPONSE SCHEMAS
# ===========================================

class InviteUserRequest(BaseModel):
    """Request schema for inviting a new user."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    role: str = Field(..., description="User role: owner, admin, accountant, auditor, payroll_manager, inventory_manager, viewer")
    entity_ids: Optional[List[uuid.UUID]] = Field(None, description="Optional list of entity IDs to grant access to")


class OrgUserResponse(BaseModel):
    """Response schema for organization user."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone_number: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    can_be_impersonated: bool
    created_at: str
    
    class Config:
        from_attributes = True


class InviteUserResponse(BaseModel):
    """Response for user invitation."""
    user: OrgUserResponse
    temporary_password: str
    message: str


class OrgUserListResponse(BaseModel):
    """Response for user list."""
    users: List[OrgUserResponse]
    total: int


class UpdateRoleRequest(BaseModel):
    """Request for updating user role."""
    role: str = Field(..., description="New role")


class UpdateEntityAccessRequest(BaseModel):
    """Request for updating entity access."""
    entity_id: uuid.UUID
    can_write: bool
    can_delete: bool


class EntityAccessResponse(BaseModel):
    """Response for entity access update."""
    entity_id: uuid.UUID
    can_write: bool
    can_delete: bool


class ImpersonationToggleRequest(BaseModel):
    """Request for toggling impersonation permission."""
    allow: bool


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def parse_user_role(role_str: str) -> UserRole:
    """Parse string to UserRole enum."""
    role_map = {
        "owner": UserRole.OWNER,
        "admin": UserRole.ADMIN,
        "accountant": UserRole.ACCOUNTANT,
        "auditor": UserRole.AUDITOR,
        "payroll_manager": UserRole.PAYROLL_MANAGER,
        "inventory_manager": UserRole.INVENTORY_MANAGER,
        "viewer": UserRole.VIEWER,
    }
    role = role_map.get(role_str.lower())
    if not role:
        raise ValueError(f"Invalid role: {role_str}. Valid roles: {list(role_map.keys())}")
    return role


def user_to_response(user: User) -> OrgUserResponse:
    """Convert User model to OrgUserResponse."""
    return OrgUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        role=user.role.value if user.role else "unknown",
        is_active=user.is_active,
        is_verified=user.is_verified,
        can_be_impersonated=user.can_be_impersonated,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# ===========================================
# ENDPOINTS
# ===========================================

@router.get(
    "/{org_id}/users",
    response_model=OrgUserListResponse,
    summary="List organization users",
    description="Get all users in an organization. Requires MANAGE_USERS permission.",
)
async def list_organization_users(
    org_id: uuid.UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """List all users in an organization."""
    service = OrganizationUserService(db)
    
    try:
        users = await service.get_organization_users(
            requesting_user=current_user,
            organization_id=org_id,
            include_inactive=include_inactive,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return OrgUserListResponse(
        users=[user_to_response(u) for u in users],
        total=len(users),
    )


@router.post(
    "/{org_id}/users/invite",
    response_model=InviteUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite new user",
    description="Invite a new user to the organization. Returns a temporary password.",
)
async def invite_user(
    org_id: uuid.UUID,
    request: InviteUserRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """Invite a new user to the organization."""
    # Verify org_id matches current user's org
    if not current_user.is_platform_staff and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite users to another organization",
        )
    
    try:
        role = parse_user_role(request.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    service = OrganizationUserService(db)
    
    try:
        new_user, temp_password = await service.invite_user(
            requesting_user=current_user,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            role=role,
            phone_number=request.phone_number,
            entity_ids=request.entity_ids,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InviteUserResponse(
        user=user_to_response(new_user),
        temporary_password=temp_password,
        message="User invited successfully. Please share the temporary password securely.",
    )


@router.put(
    "/{org_id}/users/{user_id}/role",
    response_model=OrgUserResponse,
    summary="Update user role",
    description="Update a user's role within the organization.",
)
async def update_user_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    request: UpdateRoleRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """Update a user's role."""
    if not current_user.is_platform_staff and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users in another organization",
        )
    
    try:
        new_role = parse_user_role(request.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    service = OrganizationUserService(db)
    
    try:
        updated_user = await service.update_user_role(
            requesting_user=current_user,
            target_user_id=user_id,
            new_role=new_role,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return user_to_response(updated_user)


@router.post(
    "/{org_id}/users/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Deactivate user",
    description="Deactivate a user's account in the organization.",
)
async def deactivate_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """Deactivate a user."""
    if not current_user.is_platform_staff and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users in another organization",
        )
    
    service = OrganizationUserService(db)
    
    try:
        await service.deactivate_user(
            requesting_user=current_user,
            target_user_id=user_id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return MessageResponse(message="User deactivated successfully")


@router.post(
    "/{org_id}/users/{user_id}/reactivate",
    response_model=MessageResponse,
    summary="Reactivate user",
    description="Reactivate a deactivated user's account.",
)
async def reactivate_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """Reactivate a deactivated user."""
    if not current_user.is_platform_staff and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users in another organization",
        )
    
    service = OrganizationUserService(db)
    
    try:
        await service.reactivate_user(
            requesting_user=current_user,
            target_user_id=user_id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return MessageResponse(message="User reactivated successfully")


@router.put(
    "/{org_id}/users/{user_id}/entity-access",
    response_model=EntityAccessResponse,
    summary="Update entity access",
    description="Update a user's access level for a specific entity.",
)
async def update_entity_access(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    request: UpdateEntityAccessRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_organization_permission([OrganizationPermission.MANAGE_USERS])),
):
    """Update entity access for a user."""
    if not current_user.is_platform_staff and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users in another organization",
        )
    
    service = OrganizationUserService(db)
    
    try:
        access = await service.update_entity_access(
            requesting_user=current_user,
            target_user_id=user_id,
            entity_id=request.entity_id,
            can_write=request.can_write,
            can_delete=request.can_delete,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return EntityAccessResponse(
        entity_id=access.entity_id,
        can_write=access.can_write,
        can_delete=access.can_delete,
    )


# ===========================================
# USER SELF-SERVICE ENDPOINTS
# ===========================================

@router.post(
    "/me/impersonation",
    response_model=MessageResponse,
    summary="Toggle impersonation permission",
    description="Allow or disallow customer service to impersonate your account for troubleshooting.",
)
async def toggle_impersonation(
    request: ImpersonationToggleRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """Toggle whether CSR can impersonate this user."""
    if current_user.is_platform_staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform staff accounts cannot be impersonated",
        )
    
    service = OrganizationUserService(db)
    await service.toggle_impersonation_permission(current_user, request.allow)
    
    if request.allow:
        return MessageResponse(message="Customer service can now access your account for troubleshooting")
    else:
        return MessageResponse(message="Customer service impersonation disabled")
