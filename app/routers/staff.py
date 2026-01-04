"""
TekVwarho ProAudit - Staff Management Router

API endpoints for platform staff management.

Endpoints:
- POST /staff/onboard - Onboard new staff member (Super Admin/Admin only)
- GET /staff - List all platform staff (Admin and above)
- GET /staff/{staff_id} - Get staff member details
- PUT /staff/{staff_id}/role - Update staff role (Super Admin only)
- POST /staff/{staff_id}/deactivate - Deactivate staff
- POST /staff/{staff_id}/reactivate - Reactivate staff

Organization Verification:
- GET /staff/verifications/pending - List pending verifications
- POST /staff/verifications/{org_id}/verify - Approve organization
- POST /staff/verifications/{org_id}/reject - Reject organization

Analytics:
- GET /staff/analytics/user-growth - Get user growth stats
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import (
    get_current_active_user,
    require_platform_staff,
    require_platform_permission,
    require_admin_or_above,
    require_super_admin,
)
from app.models.user import User, PlatformRole
from app.services.staff_management_service import StaffManagementService
from app.utils.permissions import PlatformPermission


router = APIRouter(prefix="/staff", tags=["Staff Management"])


# ===========================================
# REQUEST/RESPONSE SCHEMAS
# ===========================================

class StaffOnboardRequest(BaseModel):
    """Request schema for onboarding new staff."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    platform_role: str = Field(..., description="Platform role: admin, it_developer, customer_service, marketing")
    staff_notes: Optional[str] = Field(None, max_length=1000)


class StaffResponse(BaseModel):
    """Response schema for staff member."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone_number: Optional[str]
    platform_role: str
    is_active: bool
    is_verified: bool
    onboarded_by_id: Optional[uuid.UUID]
    staff_notes: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True


class StaffListResponse(BaseModel):
    """Response schema for staff list."""
    staff: List[StaffResponse]
    total: int


class UpdateRoleRequest(BaseModel):
    """Request schema for updating staff role."""
    platform_role: str = Field(..., description="New platform role")


class OrganizationVerificationResponse(BaseModel):
    """Response schema for organization verification."""
    id: uuid.UUID
    name: str
    organization_type: str
    verification_status: str
    cac_document_path: Optional[str]
    tin_document_path: Optional[str]
    email: Optional[str]
    created_at: str


class VerifyOrganizationRequest(BaseModel):
    """Request schema for verifying an organization."""
    notes: Optional[str] = Field(None, max_length=1000)


class UserGrowthStatsResponse(BaseModel):
    """Response schema for user growth statistics."""
    total_organizations: int
    total_users: int
    verified_organizations: int
    pending_organizations: int


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def parse_platform_role(role_str: str) -> PlatformRole:
    """Parse string to PlatformRole enum."""
    role_map = {
        "admin": PlatformRole.ADMIN,
        "it_developer": PlatformRole.IT_DEVELOPER,
        "customer_service": PlatformRole.CUSTOMER_SERVICE,
        "marketing": PlatformRole.MARKETING,
    }
    role = role_map.get(role_str.lower())
    if not role:
        raise ValueError(f"Invalid platform role: {role_str}. Valid roles: {list(role_map.keys())}")
    return role


def staff_to_response(staff: User) -> StaffResponse:
    """Convert User model to StaffResponse."""
    return StaffResponse(
        id=staff.id,
        email=staff.email,
        first_name=staff.first_name,
        last_name=staff.last_name,
        phone_number=staff.phone_number,
        platform_role=staff.platform_role.value if staff.platform_role else "unknown",
        is_active=staff.is_active,
        is_verified=staff.is_verified,
        onboarded_by_id=staff.onboarded_by_id,
        staff_notes=staff.staff_notes,
        created_at=staff.created_at.isoformat() if staff.created_at else "",
    )


# ===========================================
# STAFF ONBOARDING ENDPOINTS
# ===========================================

@router.post(
    "/onboard",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new platform staff",
    description="Create a new platform staff account. Super Admin can create Admin; Admin can create IT, CSR, Marketing.",
)
async def onboard_staff(
    request: StaffOnboardRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.ONBOARD_STAFF])),
):
    """Onboard a new platform staff member."""
    try:
        platform_role = parse_platform_role(request.platform_role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    service = StaffManagementService(db)
    
    try:
        new_staff = await service.onboard_staff(
            onboarding_user=current_user,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            platform_role=platform_role,
            phone_number=request.phone_number,
            staff_notes=request.staff_notes,
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
    
    return staff_to_response(new_staff)


@router.get(
    "",
    response_model=StaffListResponse,
    summary="List all platform staff",
    description="Get a list of all platform staff members. Admins cannot see Super Admin details.",
)
async def list_staff(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.MANAGE_INTERNAL_STAFF])),
):
    """List all platform staff members."""
    service = StaffManagementService(db)
    
    try:
        staff_list = await service.get_all_staff(
            requesting_user=current_user,
            include_inactive=include_inactive,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return StaffListResponse(
        staff=[staff_to_response(s) for s in staff_list],
        total=len(staff_list),
    )


@router.get(
    "/{staff_id}",
    response_model=StaffResponse,
    summary="Get staff member details",
    description="Get details of a specific platform staff member.",
)
async def get_staff(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.MANAGE_INTERNAL_STAFF])),
):
    """Get a specific staff member's details."""
    service = StaffManagementService(db)
    staff = await service.get_staff_by_id(staff_id)
    
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    
    # Non-super admins can't view super admin details
    if (staff.platform_role == PlatformRole.SUPER_ADMIN and 
        current_user.platform_role != PlatformRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view Super Admin details",
        )
    
    return staff_to_response(staff)


@router.put(
    "/{staff_id}/role",
    response_model=StaffResponse,
    summary="Update staff role",
    description="Update a staff member's platform role. Super Admin only.",
)
async def update_staff_role(
    staff_id: uuid.UUID,
    request: UpdateRoleRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_super_admin()),
):
    """Update a staff member's role."""
    try:
        new_role = parse_platform_role(request.platform_role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    service = StaffManagementService(db)
    
    try:
        updated_staff = await service.update_staff_role(
            requesting_user=current_user,
            staff_id=staff_id,
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
    
    return staff_to_response(updated_staff)


@router.post(
    "/{staff_id}/deactivate",
    response_model=MessageResponse,
    summary="Deactivate staff member",
    description="Deactivate a platform staff member's account.",
)
async def deactivate_staff(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.MANAGE_INTERNAL_STAFF])),
):
    """Deactivate a staff member."""
    service = StaffManagementService(db)
    
    try:
        await service.deactivate_staff(
            requesting_user=current_user,
            staff_id=staff_id,
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
    
    return MessageResponse(message="Staff member deactivated successfully")


@router.post(
    "/{staff_id}/reactivate",
    response_model=MessageResponse,
    summary="Reactivate staff member",
    description="Reactivate a deactivated staff member's account.",
)
async def reactivate_staff(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.MANAGE_INTERNAL_STAFF])),
):
    """Reactivate a deactivated staff member."""
    service = StaffManagementService(db)
    
    try:
        await service.reactivate_staff(
            requesting_user=current_user,
            staff_id=staff_id,
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
    
    return MessageResponse(message="Staff member reactivated successfully")


# ===========================================
# ORGANIZATION VERIFICATION ENDPOINTS
# ===========================================

@router.get(
    "/verifications/pending",
    response_model=List[OrganizationVerificationResponse],
    summary="List pending verifications",
    description="Get organizations pending document verification.",
)
async def list_pending_verifications(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.VERIFY_ORGANIZATIONS])),
):
    """List organizations pending verification."""
    service = StaffManagementService(db)
    
    try:
        pending = await service.get_pending_verifications(current_user)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return [
        OrganizationVerificationResponse(
            id=org.id,
            name=org.name,
            organization_type=org.organization_type.value,
            verification_status=org.verification_status.value,
            cac_document_path=org.cac_document_path,
            tin_document_path=org.tin_document_path,
            email=org.email,
            created_at=org.created_at.isoformat() if org.created_at else "",
        )
        for org in pending
    ]


@router.post(
    "/verifications/{org_id}/verify",
    response_model=MessageResponse,
    summary="Approve organization",
    description="Approve an organization's verification documents.",
)
async def verify_organization(
    org_id: uuid.UUID,
    request: VerifyOrganizationRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.VERIFY_ORGANIZATIONS])),
):
    """Approve an organization's documents."""
    service = StaffManagementService(db)
    
    try:
        await service.verify_organization(
            requesting_user=current_user,
            organization_id=org_id,
            approved=True,
            notes=request.notes,
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
    
    return MessageResponse(message="Organization verified successfully")


@router.post(
    "/verifications/{org_id}/reject",
    response_model=MessageResponse,
    summary="Reject organization",
    description="Reject an organization's verification documents.",
)
async def reject_organization(
    org_id: uuid.UUID,
    request: VerifyOrganizationRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.VERIFY_ORGANIZATIONS])),
):
    """Reject an organization's documents."""
    service = StaffManagementService(db)
    
    try:
        await service.verify_organization(
            requesting_user=current_user,
            organization_id=org_id,
            approved=False,
            notes=request.notes,
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
    
    return MessageResponse(message="Organization verification rejected")


# ===========================================
# ANALYTICS ENDPOINTS
# ===========================================

@router.get(
    "/analytics/user-growth",
    response_model=UserGrowthStatsResponse,
    summary="Get user growth statistics",
    description="Get user and organization growth statistics for marketing analytics.",
)
async def get_user_growth_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_permission([PlatformPermission.VIEW_USER_GROWTH])),
):
    """Get user growth statistics."""
    service = StaffManagementService(db)
    
    try:
        stats = await service.get_user_growth_stats(current_user)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return UserGrowthStatsResponse(**stats)


# ===========================================
# DASHBOARD ENDPOINT
# ===========================================

@router.get(
    "/dashboard",
    summary="Get platform staff dashboard data",
    description="Get dashboard data for the current platform staff member based on their role.",
)
async def get_staff_dashboard(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_staff),
):
    """Get dashboard data for platform staff."""
    from app.services.dashboard_service import DashboardService
    
    service = DashboardService(db)
    
    try:
        dashboard_data = await service.get_dashboard(current_user)
        return dashboard_data
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
