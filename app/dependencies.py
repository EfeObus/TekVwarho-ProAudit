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

from fastapi import Depends, HTTPException, status, Request
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
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Token can be provided via:
    1. Authorization: Bearer <token> header
    2. access_token cookie
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = None
    
    # Try Bearer header first
    if credentials:
        token = credentials.credentials
    else:
        # Fallback to cookie
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
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


async def get_current_entity_id(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> uuid.UUID:
    """
    Get the current entity ID from cookie or user's first accessible entity.
    
    For API endpoints, retrieves entity_id from:
    1. Cookie (if set by UI entity selection)
    2. User's first accessible entity (fallback)
    
    Args:
        request: FastAPI request object (for cookie access)
        current_user: Authenticated user
        db: Database session
        
    Returns:
        uuid.UUID of the current entity
        
    Raises:
        HTTPException: 400 if no entity selected or accessible
    """
    from app.models.entity import BusinessEntity
    
    # Try to get from cookie first
    entity_id_str = request.cookies.get("entity_id")
    if entity_id_str:
        try:
            entity_id = uuid.UUID(entity_id_str)
            # Verify user has access to this entity
            has_access = any(
                access.entity_id == entity_id 
                for access in current_user.entity_access
            )
            if has_access:
                return entity_id
        except ValueError:
            pass
    
    # Fallback: Get user's first accessible entity
    if current_user.entity_access:
        return current_user.entity_access[0].entity_id
    
    # For platform staff, get first entity from their organization
    if current_user.is_platform_staff and current_user.organization_id:
        result = await db.execute(
            select(BusinessEntity)
            .where(BusinessEntity.organization_id == current_user.organization_id)
            .limit(1)
        )
        entity = result.scalar_one_or_none()
        if entity:
            return entity.id
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No entity selected. Please select a business entity first.",
    )


async def verify_entity_access(
    entity_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """
    Verify user has access to the specified business entity.
    
    Args:
        entity_id: UUID of the business entity
        user: Current authenticated user
        db: Database session
        
    Raises:
        HTTPException: 404 if entity not found, 403 if access denied
    """
    from app.models.entity import BusinessEntity
    
    result = await db.execute(
        select(BusinessEntity).where(BusinessEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business entity not found",
        )
    
    has_access = any(
        access.entity_id == entity_id 
        for access in user.entity_access
    )
    
    if not has_access and entity.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this business entity",
        )


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
