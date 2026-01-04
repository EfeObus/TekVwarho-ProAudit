"""
TekVwarho ProAudit - FastAPI Dependencies

Shared dependencies for authentication, database sessions, and RBAC.

This module provides dependency injection for:
1. Database sessions
2. Current user authentication
3. Role-based access control for platform staff
4. Permission-based access control for organization users
"""

import uuid
from typing import List, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_session
from app.models.user import User, UserRole, UserEntityAccess, PlatformRole
from app.models.organization import Organization
from app.utils.security import verify_access_token
from app.utils.permissions import (
    PlatformPermission,
    OrganizationPermission,
    has_platform_permission,
    has_organization_permission,
)


# HTTP Bearer token security
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.organization),
            selectinload(User.entity_access).selectinload(UserEntityAccess.entity)
        )
        .where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and verify they are active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current user and verify email is verified."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )
    return current_user


def require_role(allowed_roles: list[UserRole]):
    """
    Dependency factory for organization role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role([UserRole.OWNER, UserRole.ADMIN]))):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        # Platform staff bypass org role checks (they have their own permissions)
        if current_user.is_platform_staff:
            return current_user
            
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    
    return role_checker


# ===========================================
# PLATFORM STAFF RBAC DEPENDENCIES
# ===========================================

def require_platform_staff():
    """
    Require the user to be a platform staff member.
    
    Usage:
        @router.get("/staff-only")
        async def staff_endpoint(user: User = Depends(require_platform_staff())):
            ...
    """
    async def staff_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.is_platform_staff:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Platform staff only.",
            )
        return current_user
    
    return staff_checker


def require_platform_role(allowed_roles: List[PlatformRole]):
    """
    Require specific platform roles.
    
    Usage:
        @router.get("/super-admin-only")
        async def super_admin_endpoint(
            user: User = Depends(require_platform_role([PlatformRole.SUPER_ADMIN]))
        ):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.is_platform_staff:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Platform staff only.",
            )
        
        if current_user.platform_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required platform roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    
    return role_checker


def require_platform_permission(required_permissions: List[PlatformPermission]):
    """
    Require specific platform permissions.
    
    Usage:
        @router.get("/verify-orgs")
        async def verify_org_endpoint(
            user: User = Depends(require_platform_permission([PlatformPermission.VERIFY_ORGANIZATIONS]))
        ):
            ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.is_platform_staff or not current_user.platform_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Platform staff only.",
            )
        
        missing_permissions = []
        for perm in required_permissions:
            if not has_platform_permission(current_user.platform_role, perm):
                missing_permissions.append(perm.value)
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permissions: {missing_permissions}",
            )
        return current_user
    
    return permission_checker


def require_super_admin():
    """Shortcut for requiring Super Admin role."""
    return require_platform_role([PlatformRole.SUPER_ADMIN])


def require_admin_or_above():
    """Shortcut for requiring Admin or Super Admin role."""
    return require_platform_role([PlatformRole.SUPER_ADMIN, PlatformRole.ADMIN])


# ===========================================
# ORGANIZATION USER RBAC DEPENDENCIES
# ===========================================

def require_organization_permission(required_permissions: List[OrganizationPermission]):
    """
    Require specific organization permissions.
    
    Usage:
        @router.get("/transactions")
        async def get_transactions(
            user: User = Depends(require_organization_permission([OrganizationPermission.VIEW_ALL_TRANSACTIONS]))
        ):
            ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        # Platform staff have elevated access - check their platform permissions instead
        if current_user.is_platform_staff:
            # Platform staff can view user data
            if current_user.platform_role and has_platform_permission(
                current_user.platform_role, 
                PlatformPermission.VIEW_USER_DATA
            ):
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform staff: insufficient permissions for organization data",
            )
        
        if not current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organization role assigned",
            )
        
        missing_permissions = []
        for perm in required_permissions:
            if not has_organization_permission(current_user.role, perm):
                missing_permissions.append(perm.value)
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing permissions: {missing_permissions}",
            )
        return current_user
    
    return permission_checker


def require_organization_owner():
    """Require the user to be an organization owner."""
    return require_role([UserRole.OWNER])


def require_organization_admin():
    """Require the user to be an organization admin or owner."""
    return require_role([UserRole.OWNER, UserRole.ADMIN])


def require_financial_access():
    """Require access to financial data (accountant level or above)."""
    return require_role([UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.AUDITOR])


# ===========================================
# COMBINED ACCESS DEPENDENCIES
# ===========================================

def require_any_admin():
    """
    Require either platform admin or organization admin.
    Useful for endpoints that both platform staff and org admins can access.
    """
    async def admin_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        # Check platform admin
        if current_user.is_platform_staff:
            if current_user.platform_role in [PlatformRole.SUPER_ADMIN, PlatformRole.ADMIN]:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin access required.",
            )
        
        # Check organization admin
        if current_user.role in [UserRole.OWNER, UserRole.ADMIN]:
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin access required.",
        )
    
    return admin_checker


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work differently for authenticated vs anonymous users.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
