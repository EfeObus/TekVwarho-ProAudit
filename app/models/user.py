"""
TekVwarho ProAudit - User Model

User model with role-based access control.
"""

import uuid
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.entity import BusinessEntity


class UserRole(str, Enum):
    """User roles for RBAC."""
    OWNER = "owner"              # Full access to organization
    ADMIN = "admin"              # Administrative access
    ACCOUNTANT = "accountant"    # Financial data access
    AUDITOR = "auditor"          # Read-only access
    PAYROLL_MANAGER = "payroll_manager"  # Payroll access
    INVENTORY_MANAGER = "inventory_manager"  # Inventory access
    VIEWER = "viewer"            # Limited read-only


class User(BaseModel):
    """
    User model for authentication and authorization.
    
    Users belong to an organization and can have access to multiple business entities.
    """
    
    __tablename__ = "users"
    
    # Basic Info
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Organization
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Role
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.VIEWER,
        nullable=False,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users",
    )
    entity_access: Mapped[List["UserEntityAccess"]] = relationship(
        "UserEntityAccess",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class UserEntityAccess(BaseModel):
    """
    Many-to-many relationship between users and business entities.
    Allows users to have access to specific entities within their organization.
    """
    
    __tablename__ = "user_entity_access"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Access level for this specific entity
    can_write: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="entity_access")
    entity: Mapped["BusinessEntity"] = relationship("BusinessEntity", back_populates="user_access")
