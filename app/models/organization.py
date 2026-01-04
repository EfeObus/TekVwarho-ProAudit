"""
TekVwarho ProAudit - Organization Model

Organization model for multi-tenancy support.

Organization Types:
- SME: Small and Medium Enterprises
- Small Business: Micro businesses
- School: Educational institutions
- Non-Profit: NGOs and charitable organizations
- Individual: Solo practitioners/freelancers

Verification Status:
- Pending: Awaiting document upload
- Submitted: Documents uploaded, awaiting review
- Verified: Documents approved by Admin
- Rejected: Documents rejected, needs resubmission
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String, Text, Enum as SQLEnum
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


class OrganizationType(str, Enum):
    """
    Organization types for differentiated features and compliance.
    Each type may have different tax obligations and reporting requirements.
    """
    SME = "sme"                       # Small and Medium Enterprises
    SMALL_BUSINESS = "small_business" # Micro businesses
    SCHOOL = "school"                 # Educational institutions
    NON_PROFIT = "non_profit"         # NGOs and charitable organizations  
    INDIVIDUAL = "individual"         # Solo practitioners/freelancers
    CORPORATION = "corporation"       # Large corporations


class VerificationStatus(str, Enum):
    """Verification status for organization documents."""
    PENDING = "pending"       # Awaiting document upload
    SUBMITTED = "submitted"   # Documents uploaded, awaiting review
    UNDER_REVIEW = "under_review"  # Currently being reviewed by admin
    VERIFIED = "verified"     # Documents approved by Admin
    REJECTED = "rejected"     # Documents rejected, needs resubmission


class Organization(BaseModel):
    """
    Organization model - top-level tenant.
    
    An organization can have multiple business entities and users.
    Organizations must be verified by platform admins before accessing
    full platform features.
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
    
    # Organization Type
    organization_type: Mapped[OrganizationType] = mapped_column(
        SQLEnum(OrganizationType),
        default=OrganizationType.SMALL_BUSINESS,
        nullable=False,
        comment="Type of organization for compliance and feature differentiation"
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
    
    # ===========================================
    # VERIFICATION FIELDS (For Admin Approval)
    # ===========================================
    
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus),
        default=VerificationStatus.PENDING,
        nullable=False,
        comment="Document verification status"
    )
    
    # Verification Documents Paths
    cac_document_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to CAC registration document"
    )
    tin_document_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to TIN certificate document"
    )
    additional_documents: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of additional document paths"
    )
    
    # Verification Review
    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from admin during verification review"
    )
    verified_by_id: Mapped[Optional[str]] = mapped_column(
        String(36),  # UUID as string for flexibility
        nullable=True,
        comment="ID of admin who verified the organization"
    )
    
    # Referral Engine
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="Unique referral code for marketing campaigns"
    )
    referred_by_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Referral code of the organization that referred this one"
    )
    
    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="User.organization_id",
    )
    entities: Mapped[List["BusinessEntity"]] = relationship(
        "BusinessEntity",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    
    @property
    def is_verified(self) -> bool:
        """Check if organization is verified."""
        return self.verification_status == VerificationStatus.VERIFIED
    
    @property
    def requires_verification(self) -> bool:
        """Check if organization requires verification."""
        return self.verification_status in [
            VerificationStatus.PENDING, 
            VerificationStatus.REJECTED
        ]
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, type={self.organization_type})>"
