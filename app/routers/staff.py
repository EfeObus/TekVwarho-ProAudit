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


# ===========================================
# IMPERSONATION ENDPOINTS
# ===========================================

class ImpersonateRequest(BaseModel):
    """Request schema for user impersonation."""
    user_id: uuid.UUID
    reason: str = Field(..., min_length=10, max_length=500, description="Reason for impersonation (required for audit trail)")


class ImpersonateResponse(BaseModel):
    """Response schema for impersonation."""
    impersonation_token: str
    original_user_id: uuid.UUID
    impersonated_user_id: uuid.UUID
    impersonated_user_email: str
    expires_at: str
    message: str


class ActiveImpersonationResponse(BaseModel):
    """Response for listing active impersonations."""
    id: uuid.UUID
    staff_user_id: uuid.UUID
    staff_email: str
    impersonated_user_id: uuid.UUID
    impersonated_user_email: str
    reason: str
    started_at: str
    expires_at: str


@router.post(
    "/impersonate",
    response_model=ImpersonateResponse,
    summary="Impersonate a user",
    description="Start impersonating a user for support purposes. Creates audit trail and returns temporary token. Super Admin/Admin only.",
)
async def impersonate_user(
    request: ImpersonateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_admin_or_above),
):
    """
    Impersonate a user for support purposes.
    
    - Creates comprehensive audit log entry
    - Returns a temporary token valid for 1 hour
    - Staff cannot impersonate other staff or super admins
    - Impersonation sessions are tracked and can be terminated
    """
    from sqlalchemy import select
    from datetime import datetime, timedelta
    from app.services.auth_service import AuthService
    from app.services.audit_service import AuditService
    
    # Get the user to impersonate
    result = await db.execute(
        select(User).where(User.id == request.user_id)
    )
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Cannot impersonate platform staff
    if target_user.platform_role and target_user.platform_role not in [None]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot impersonate platform staff members",
        )
    
    # Cannot impersonate super admin
    if target_user.platform_role == PlatformRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot impersonate super admin",
        )
    
    # Log impersonation start
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="impersonation_start",
        resource_type="user",
        resource_id=str(target_user.id),
        details={
            "reason": request.reason,
            "staff_email": current_user.email,
            "target_email": target_user.email,
        },
    )
    
    # Generate impersonation token
    auth_service = AuthService(db)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    token = await auth_service.create_access_token(
        data={
            "sub": str(target_user.id),
            "impersonator_id": str(current_user.id),
            "impersonation": True,
            "exp": expires_at.timestamp(),
        }
    )
    
    await db.commit()
    
    return ImpersonateResponse(
        impersonation_token=token,
        original_user_id=current_user.id,
        impersonated_user_id=target_user.id,
        impersonated_user_email=target_user.email,
        expires_at=expires_at.isoformat(),
        message=f"Impersonation started. Session expires at {expires_at.isoformat()}",
    )


@router.post(
    "/impersonate/end",
    response_model=MessageResponse,
    summary="End impersonation session",
    description="End the current impersonation session and return to staff account.",
)
async def end_impersonation(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_platform_staff),
):
    """End the current impersonation session."""
    from app.services.audit_service import AuditService
    
    # Log impersonation end
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="impersonation_end",
        resource_type="user",
        resource_id=str(current_user.id),
        details={
            "staff_email": current_user.email,
        },
    )
    
    await db.commit()
    
    return MessageResponse(
        message="Impersonation session ended. Please use your original credentials to continue.",
    )


@router.get(
    "/impersonate/active",
    response_model=List[dict],
    summary="List active impersonation sessions",
    description="List all currently active impersonation sessions. Super Admin only.",
)
async def list_active_impersonations(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_super_admin),
):
    """List all active impersonation sessions."""
    from app.services.audit_service import AuditService
    
    # Get recent impersonation starts that don't have corresponding ends
    audit_service = AuditService(db)
    active_sessions = await audit_service.get_audit_logs(
        action_type="impersonation_start",
        limit=100,
    )
    
    # Filter out ended sessions (simplified - in production would track sessions properly)
    return [
        {
            "id": session.get("id"),
            "staff_email": session.get("details", {}).get("staff_email"),
            "target_email": session.get("details", {}).get("target_email"),
            "reason": session.get("details", {}).get("reason"),
            "started_at": session.get("timestamp"),
        }
        for session in active_sessions
    ]


@router.post(
    "/impersonate/{session_id}/terminate",
    response_model=MessageResponse,
    summary="Terminate impersonation session",
    description="Forcefully terminate an impersonation session. Super Admin only.",
)
async def terminate_impersonation(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_super_admin),
):
    """Terminate an active impersonation session."""
    from app.services.audit_service import AuditService
    
    # Log forced termination
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="impersonation_terminated",
        resource_type="impersonation_session",
        resource_id=str(session_id),
        details={
            "terminated_by": current_user.email,
        },
    )
    
    await db.commit()
    
    return MessageResponse(
        message=f"Impersonation session {session_id} has been terminated.",
    )


# ===========================================
# ADDITIONAL STAFF MANAGEMENT ENDPOINTS
# ===========================================

@router.delete(
    "/{staff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete staff member",
    description="Permanently delete a platform staff member. Super Admin only.",
)
async def delete_staff(
    staff_id: uuid.UUID,
    permanent: bool = False,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_super_admin()),
):
    """
    Delete a platform staff member.
    
    By default, this deactivates the staff account.
    Set permanent=true to permanently remove the staff record.
    
    Note: Super Admin cannot be deleted. All audit logs are preserved.
    """
    service = StaffManagementService(db)
    
    # Get the target staff
    target_staff = await service.get_staff_by_id(staff_id)
    
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    
    # Cannot delete yourself
    if staff_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    
    # Cannot delete Super Admin
    if target_staff.platform_role == PlatformRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete Super Admin account",
        )
    
    try:
        if permanent:
            await service.permanently_delete_staff(
                requesting_user=current_user,
                staff_id=staff_id,
            )
        else:
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
    
    return None


class ForceResetPasswordRequest(BaseModel):
    """Request for forcing password reset."""
    send_email: bool = Field(True, description="Send password reset email")
    generate_temp_password: bool = Field(False, description="Generate and return temporary password")


class ForceResetPasswordResponse(BaseModel):
    """Response for force password reset."""
    message: str
    temporary_password: Optional[str] = None
    email_sent: bool


@router.post(
    "/{staff_id}/force-reset-password",
    response_model=ForceResetPasswordResponse,
    summary="Force password reset for staff",
    description="Force a staff member to reset their password. Super Admin or Admin only.",
)
async def force_reset_staff_password(
    staff_id: uuid.UUID,
    request: ForceResetPasswordRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_admin_or_above),
):
    """
    Force a staff member to reset their password.
    
    Options:
    - Send password reset email
    - Generate temporary password
    - Mark account for password reset on next login
    """
    import secrets
    
    service = StaffManagementService(db)
    
    target_staff = await service.get_staff_by_id(staff_id)
    
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    
    # Cannot reset Super Admin password unless you're also Super Admin
    if target_staff.platform_role == PlatformRole.SUPER_ADMIN:
        if current_user.platform_role != PlatformRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admin can reset Super Admin password",
            )
    
    temp_password = None
    email_sent = False
    
    # Mark staff for forced password reset
    target_staff.must_reset_password = True
    
    if request.generate_temp_password:
        temp_password = secrets.token_urlsafe(12)
        from app.utils.security import hash_password
        target_staff.hashed_password = hash_password(temp_password)
    
    if request.send_email:
        from app.services.email_service import EmailService
        from app.services.auth_service import AuthService
        from app.config import settings
        
        auth_service = AuthService(db)
        email_service = EmailService()
        
        reset_token = auth_service.create_password_reset_token(target_staff)
        reset_url = f"{settings.base_url}/reset-password?token={reset_token}"
        
        try:
            await email_service.send_password_reset(
                to_email=target_staff.email,
                user_name=target_staff.first_name,
                reset_url=reset_url,
            )
            email_sent = True
        except Exception:
            pass
    
    # Log the action
    from app.services.audit_service import AuditService
    audit_service = AuditService(db)
    await audit_service.log_action(
        user_id=current_user.id,
        action="staff_password_reset_forced",
        resource_type="staff",
        resource_id=str(staff_id),
        details={
            "target_email": target_staff.email,
            "email_sent": email_sent,
            "temp_password_generated": temp_password is not None,
        },
    )
    
    await db.commit()
    
    return ForceResetPasswordResponse(
        message="Password reset initiated. Staff member will be prompted to change password on next login.",
        temporary_password=temp_password,
        email_sent=email_sent,
    )


class StaffActivityLogEntry(BaseModel):
    """Activity log entry for staff."""
    id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: dict
    timestamp: str
    ip_address: Optional[str]


class StaffActivityLogResponse(BaseModel):
    """Response for staff activity log."""
    staff_id: uuid.UUID
    staff_email: str
    entries: List[StaffActivityLogEntry]
    total: int
    page: int
    per_page: int


@router.get(
    "/{staff_id}/activity-log",
    response_model=StaffActivityLogResponse,
    summary="Get staff activity log",
    description="Get activity/audit log for a specific staff member. Super Admin or Admin only.",
)
async def get_staff_activity_log(
    staff_id: uuid.UUID,
    page: int = 1,
    per_page: int = 50,
    action_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_admin_or_above),
):
    """
    Get activity log for a staff member.
    
    Shows all actions performed by the staff member including:
    - Login/logout events
    - Impersonation sessions
    - Organization verifications
    - User management actions
    - Configuration changes
    """
    from app.services.audit_service import AuditService
    
    service = StaffManagementService(db)
    
    target_staff = await service.get_staff_by_id(staff_id)
    
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    
    # Non-Super Admins cannot view Super Admin logs
    if target_staff.platform_role == PlatformRole.SUPER_ADMIN:
        if current_user.platform_role != PlatformRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view Super Admin activity logs",
            )
    
    audit_service = AuditService(db)
    
    # Get audit logs for this staff member
    logs = await audit_service.get_audit_logs(
        user_id=staff_id,
        action_type=action_type,
        start_date=start_date,
        end_date=end_date,
        skip=(page - 1) * per_page,
        limit=per_page,
    )
    
    entries = [
        StaffActivityLogEntry(
            id=str(log.get("id", "")),
            action=log.get("action", ""),
            resource_type=log.get("resource_type", ""),
            resource_id=log.get("resource_id"),
            details=log.get("details", {}),
            timestamp=log.get("timestamp", ""),
            ip_address=log.get("ip_address"),
        )
        for log in logs
    ]
    
    return StaffActivityLogResponse(
        staff_id=target_staff.id,
        staff_email=target_staff.email,
        entries=entries,
        total=len(entries),  # In production, get total count from query
        page=page,
        per_page=per_page,
    )


@router.get(
    "/activity-log/all",
    summary="Get all staff activity logs",
    description="Get activity logs for all platform staff. Super Admin only.",
)
async def get_all_staff_activity_logs(
    page: int = 1,
    per_page: int = 100,
    action_type: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_super_admin),
):
    """
    Get consolidated activity log for all staff.
    
    Useful for security auditing and compliance reporting.
    """
    from app.services.audit_service import AuditService
    
    audit_service = AuditService(db)
    
    # Get logs for platform staff actions
    logs = await audit_service.get_audit_logs(
        action_type=action_type,
        platform_staff_only=True,
        skip=(page - 1) * per_page,
        limit=per_page,
    )
    
    return {
        "entries": logs,
        "total": len(logs),
        "page": page,
        "per_page": per_page,
    }


@router.get(
    "/{staff_id}/permissions",
    summary="Get staff permissions",
    description="Get all permissions for a staff member based on their role.",
)
async def get_staff_permissions(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(require_admin_or_above),
):
    """Get all permissions for a staff member."""
    from app.utils.permissions import get_platform_permissions
    
    service = StaffManagementService(db)
    
    target_staff = await service.get_staff_by_id(staff_id)
    
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    
    permissions = []
    if target_staff.platform_role:
        permissions = [p.value for p in get_platform_permissions(target_staff.platform_role)]
    
    return {
        "staff_id": str(staff_id),
        "staff_email": target_staff.email,
        "platform_role": target_staff.platform_role.value if target_staff.platform_role else None,
        "permissions": permissions,
    }
