"""
TekVwarho ProAudit - Authentication Service

Business logic for user authentication and registration.
"""

import uuid
import re
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole, UserEntityAccess
from app.models.organization import Organization, SubscriptionTier
from app.models.entity import BusinessEntity
from app.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.config import settings


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.organization),
                selectinload(User.entity_access).selectinload(UserEntityAccess.entity)
            )
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.organization),
                selectinload(User.entity_access).selectinload(UserEntityAccess.entity)
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def authenticate_user(
        self, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate user with email and password.
        
        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_user_by_email(email)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    async def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        organization_name: str,
        phone_number: Optional[str] = None,
    ) -> Tuple[User, Organization, BusinessEntity]:
        """
        Register a new user with organization and default entity.
        
        Returns:
            Tuple of (User, Organization, BusinessEntity)
        """
        # Check if email already exists
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Create organization
        org_slug = self._generate_slug(organization_name)
        organization = Organization(
            name=organization_name,
            slug=org_slug,
            email=email.lower(),
            subscription_tier=SubscriptionTier.FREE,
        )
        self.db.add(organization)
        await self.db.flush()  # Get organization ID
        
        # Create default business entity
        entity = BusinessEntity(
            organization_id=organization.id,
            name=organization_name,
            legal_name=organization_name,
            country="Nigeria",
            currency="NGN",
            fiscal_year_start_month=1,
        )
        self.db.add(entity)
        await self.db.flush()  # Get entity ID
        
        # Create user
        user = User(
            email=email.lower(),
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            organization_id=organization.id,
            role=UserRole.OWNER,
            is_active=True,
            is_verified=False,  # Will be verified via email
        )
        self.db.add(user)
        await self.db.flush()  # Get user ID
        
        # Grant user access to default entity
        entity_access = UserEntityAccess(
            user_id=user.id,
            entity_id=entity.id,
            can_write=True,
            can_delete=True,
        )
        self.db.add(entity_access)
        
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(organization)
        await self.db.refresh(entity)
        
        return user, organization, entity
    
    def create_tokens(self, user: User) -> dict:
        """
        Create access and refresh tokens for user.
        
        Returns:
            Dictionary with access_token, refresh_token, token_type, expires_in
        """
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "org_id": str(user.organization_id),
            "role": user.role.value,
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    
    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Change user password.
        
        Returns:
            True if password changed successfully
        """
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")
        
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        return True
    
    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        # Convert to lowercase and replace spaces with hyphens
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Add random suffix to ensure uniqueness
        suffix = uuid.uuid4().hex[:6]
        return f"{slug}-{suffix}"
    
    def create_password_reset_token(self, user: User) -> str:
        """
        Create a password reset token for user.
        
        Returns:
            Password reset token string
        """
        token_data = {
            "sub": str(user.id),
            "email": user.email,
        }
        return create_password_reset_token(token_data)
    
    async def reset_password_with_token(
        self,
        token: str,
        new_password: str,
    ) -> bool:
        """
        Reset user password using reset token.
        
        Returns:
            True if password reset successfully
        """
        payload = verify_password_reset_token(token)
        
        if not payload:
            raise ValueError("Invalid or expired reset token")
        
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token payload")
        
        user = await self.get_user_by_id(uuid.UUID(user_id))
        
        if not user:
            raise ValueError("User not found")
        
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        return True
