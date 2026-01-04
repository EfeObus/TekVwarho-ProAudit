"""
TekVwarho ProAudit - Staff Management Service

Service for managing platform staff (internal TekVwarho employees).
Handles onboarding, deactivation, and role management.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, PlatformRole, UserRole
from app.models.organization import Organization, VerificationStatus
from app.utils.security import get_password_hash
from app.utils.permissions import (
    PlatformPermission,
    has_platform_permission,
    is_platform_role_higher_or_equal,
)
from app.config import settings


class StaffManagementService:
    """Service for platform staff management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # SUPER ADMIN MANAGEMENT
    # ===========================================
    
    async def get_or_create_super_admin(self) -> User:
        """
        Get or create the hardcoded super admin user.
        
        This is called during application startup to ensure a super admin exists.
        Credentials are stored in config/environment variables.
        
        Returns:
            User: The super admin user
        """
        # Get super admin credentials from config
        super_admin_email = getattr(settings, 'super_admin_email', 'superadmin@tekvwarho.com')
        super_admin_password = getattr(settings, 'super_admin_password', 'SuperAdmin@123!')
        super_admin_first_name = getattr(settings, 'super_admin_first_name', 'Super')
        super_admin_last_name = getattr(settings, 'super_admin_last_name', 'Admin')
        
        # Check if super admin exists
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == super_admin_email.lower(),
                    User.is_platform_staff == True,
                    User.platform_role == PlatformRole.SUPER_ADMIN
                )
            )
        )
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            return existing_admin
        
        # Create super admin
        super_admin = User(
            email=super_admin_email.lower(),
            hashed_password=get_password_hash(super_admin_password),
            first_name=super_admin_first_name,
            last_name=super_admin_last_name,
            is_platform_staff=True,
            platform_role=PlatformRole.SUPER_ADMIN,
            role=None,  # Platform staff don't have org roles
            organization_id=None,  # Platform staff don't belong to orgs
            is_active=True,
            is_verified=True,  # Super admin is pre-verified
            is_superuser=True,
        )
        
        self.db.add(super_admin)
        await self.db.commit()
        await self.db.refresh(super_admin)
        
        return super_admin
    
    # ===========================================
    # STAFF ONBOARDING
    # ===========================================
    
    async def onboard_staff(
        self,
        onboarding_user: User,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        platform_role: PlatformRole,
        phone_number: Optional[str] = None,
        staff_notes: Optional[str] = None,
    ) -> User:
        """
        Onboard a new platform staff member.
        
        Args:
            onboarding_user: The user performing the onboarding (must have permission)
            email: Email for the new staff member
            password: Initial password for the new staff member
            first_name: First name
            last_name: Last name
            platform_role: Role to assign to the new staff member
            phone_number: Optional phone number
            staff_notes: Optional internal notes
            
        Returns:
            User: The newly created staff member
            
        Raises:
            PermissionError: If onboarding user doesn't have permission
            ValueError: If email already exists or invalid role
        """
        # Verify onboarding user is platform staff
        if not onboarding_user.is_platform_staff or not onboarding_user.platform_role:
            raise PermissionError("Only platform staff can onboard new staff members")
        
        # Check if user can onboard the target role
        if not onboarding_user.can_onboard_role(platform_role):
            raise PermissionError(
                f"You don't have permission to onboard staff with role: {platform_role.value}"
            )
        
        # Cannot create another super admin
        if platform_role == PlatformRole.SUPER_ADMIN:
            raise ValueError("Cannot onboard another Super Admin")
        
        # Check if email already exists
        existing = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")
        
        # Create the new staff member
        new_staff = User(
            email=email.lower(),
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            is_platform_staff=True,
            platform_role=platform_role,
            role=None,
            organization_id=None,
            is_active=True,
            is_verified=True,  # Staff are pre-verified
            onboarded_by_id=onboarding_user.id,
            staff_notes=staff_notes,
        )
        
        self.db.add(new_staff)
        await self.db.commit()
        await self.db.refresh(new_staff)
        
        return new_staff
    
    async def get_all_staff(
        self,
        requesting_user: User,
        include_inactive: bool = False,
    ) -> List[User]:
        """
        Get all platform staff members.
        
        Args:
            requesting_user: The user making the request
            include_inactive: Whether to include inactive staff
            
        Returns:
            List of staff members visible to the requesting user
        """
        if not requesting_user.is_platform_staff:
            raise PermissionError("Only platform staff can view staff list")
        
        # Check permission
        if not has_platform_permission(
            requesting_user.platform_role, 
            PlatformPermission.MANAGE_INTERNAL_STAFF
        ):
            raise PermissionError("You don't have permission to view staff list")
        
        query = select(User).where(User.is_platform_staff == True)
        
        if not include_inactive:
            query = query.where(User.is_active == True)
        
        # Non-super admins can't see super admin details
        if requesting_user.platform_role != PlatformRole.SUPER_ADMIN:
            query = query.where(User.platform_role != PlatformRole.SUPER_ADMIN)
        
        result = await self.db.execute(query.order_by(User.created_at.desc()))
        return list(result.scalars().all())
    
    async def get_staff_by_id(self, staff_id: uuid.UUID) -> Optional[User]:
        """Get a staff member by ID."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == staff_id,
                    User.is_platform_staff == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_staff_role(
        self,
        requesting_user: User,
        staff_id: uuid.UUID,
        new_role: PlatformRole,
    ) -> User:
        """
        Update a staff member's role.
        
        Only Super Admin can change roles, and cannot change their own role.
        """
        if requesting_user.platform_role != PlatformRole.SUPER_ADMIN:
            raise PermissionError("Only Super Admin can change staff roles")
        
        if requesting_user.id == staff_id:
            raise ValueError("Cannot change your own role")
        
        staff = await self.get_staff_by_id(staff_id)
        if not staff:
            raise ValueError("Staff member not found")
        
        if staff.platform_role == PlatformRole.SUPER_ADMIN:
            raise ValueError("Cannot modify Super Admin role")
        
        if new_role == PlatformRole.SUPER_ADMIN:
            raise ValueError("Cannot promote to Super Admin")
        
        staff.platform_role = new_role
        await self.db.commit()
        await self.db.refresh(staff)
        
        return staff
    
    async def deactivate_staff(
        self,
        requesting_user: User,
        staff_id: uuid.UUID,
    ) -> User:
        """
        Deactivate a staff member.
        
        Only Admin and above can deactivate, and cannot deactivate self or higher roles.
        """
        if not has_platform_permission(
            requesting_user.platform_role,
            PlatformPermission.MANAGE_INTERNAL_STAFF
        ):
            raise PermissionError("You don't have permission to deactivate staff")
        
        if requesting_user.id == staff_id:
            raise ValueError("Cannot deactivate yourself")
        
        staff = await self.get_staff_by_id(staff_id)
        if not staff:
            raise ValueError("Staff member not found")
        
        # Can't deactivate someone with higher or equal role
        if is_platform_role_higher_or_equal(staff.platform_role, requesting_user.platform_role):
            raise PermissionError("Cannot deactivate staff with equal or higher role")
        
        staff.is_active = False
        await self.db.commit()
        await self.db.refresh(staff)
        
        return staff
    
    async def reactivate_staff(
        self,
        requesting_user: User,
        staff_id: uuid.UUID,
    ) -> User:
        """Reactivate a deactivated staff member."""
        if not has_platform_permission(
            requesting_user.platform_role,
            PlatformPermission.MANAGE_INTERNAL_STAFF
        ):
            raise PermissionError("You don't have permission to reactivate staff")
        
        staff = await self.get_staff_by_id(staff_id)
        if not staff:
            raise ValueError("Staff member not found")
        
        staff.is_active = True
        await self.db.commit()
        await self.db.refresh(staff)
        
        return staff
    
    # ===========================================
    # ORGANIZATION VERIFICATION (Admin Function)
    # ===========================================
    
    async def get_pending_verifications(
        self,
        requesting_user: User,
    ) -> List[Organization]:
        """Get organizations pending verification."""
        if not has_platform_permission(
            requesting_user.platform_role,
            PlatformPermission.VERIFY_ORGANIZATIONS
        ):
            raise PermissionError("You don't have permission to verify organizations")
        
        result = await self.db.execute(
            select(Organization)
            .where(Organization.verification_status == VerificationStatus.SUBMITTED)
            .order_by(Organization.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def verify_organization(
        self,
        requesting_user: User,
        organization_id: uuid.UUID,
        approved: bool,
        notes: Optional[str] = None,
    ) -> Organization:
        """
        Verify or reject an organization's documents.
        
        Args:
            requesting_user: Admin performing the verification
            organization_id: Organization to verify
            approved: True to approve, False to reject
            notes: Optional notes about the decision
        """
        if not has_platform_permission(
            requesting_user.platform_role,
            PlatformPermission.VERIFY_ORGANIZATIONS
        ):
            raise PermissionError("You don't have permission to verify organizations")
        
        result = await self.db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        org = result.scalar_one_or_none()
        
        if not org:
            raise ValueError("Organization not found")
        
        org.verification_status = (
            VerificationStatus.VERIFIED if approved 
            else VerificationStatus.REJECTED
        )
        org.verification_notes = notes
        org.verified_by_id = str(requesting_user.id)
        
        await self.db.commit()
        await self.db.refresh(org)
        
        return org
    
    # ===========================================
    # IMPERSONATION (CSR Function)
    # ===========================================
    
    async def can_impersonate_user(
        self,
        csr_user: User,
        target_user_id: uuid.UUID,
    ) -> Tuple[bool, str]:
        """
        Check if CSR can impersonate a target user.
        
        Returns:
            Tuple of (can_impersonate, reason)
        """
        if not has_platform_permission(
            csr_user.platform_role,
            PlatformPermission.IMPERSONATE_USER
        ):
            return False, "You don't have impersonation permission"
        
        result = await self.db.execute(
            select(User).where(User.id == target_user_id)
        )
        target = result.scalar_one_or_none()
        
        if not target:
            return False, "Target user not found"
        
        if target.is_platform_staff:
            return False, "Cannot impersonate platform staff"
        
        if not target.can_be_impersonated:
            return False, "User has not granted impersonation permission"
        
        return True, "Impersonation allowed"
    
    # ===========================================
    # ANALYTICS (Marketing Function)
    # ===========================================
    
    async def get_user_growth_stats(
        self,
        requesting_user: User,
    ) -> dict:
        """Get user growth statistics for marketing analytics."""
        if not has_platform_permission(
            requesting_user.platform_role,
            PlatformPermission.VIEW_USER_GROWTH
        ):
            raise PermissionError("You don't have permission to view user growth stats")
        
        # Total organizations
        org_count = await self.db.execute(
            select(func.count(Organization.id))
        )
        total_orgs = org_count.scalar()
        
        # Total users (non-platform staff)
        user_count = await self.db.execute(
            select(func.count(User.id)).where(User.is_platform_staff == False)
        )
        total_users = user_count.scalar()
        
        # Verified vs unverified orgs
        verified_count = await self.db.execute(
            select(func.count(Organization.id))
            .where(Organization.verification_status == VerificationStatus.VERIFIED)
        )
        verified_orgs = verified_count.scalar()
        
        return {
            "total_organizations": total_orgs,
            "total_users": total_users,
            "verified_organizations": verified_orgs,
            "pending_organizations": total_orgs - verified_orgs,
        }
