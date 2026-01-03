"""
TekVwarho ProAudit - Organization Model

Organization model for multi-tenancy support.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.entity import BusinessEntity


class SubscriptionTier(str, Enum):
    """Subscription tiers for organizations."""
    FREE = "free"           # Limited features
    STARTER = "starter"     # Basic features
    PROFESSIONAL = "professional"  # Full features
    ENTERPRISE = "enterprise"      # Custom features


class Organization(BaseModel):
    """
    Organization model - top-level tenant.
    
    An organization can have multiple business entities and users.
    """
    
    __tablename__ = "organizations"
    
    # Basic Info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Contact
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Subscription
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier),
        default=SubscriptionTier.FREE,
        nullable=False,
    )
    
    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    entities: Mapped[List["BusinessEntity"]] = relationship(
        "BusinessEntity",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
