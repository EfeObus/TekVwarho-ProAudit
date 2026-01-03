"""
TekVwarho ProAudit - Customer Schemas

Pydantic schemas for customer management (for invoicing).
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ===========================================
# REQUEST SCHEMAS
# ===========================================

class CustomerCreateRequest(BaseModel):
    """Schema for creating a customer."""
    name: str = Field(..., min_length=1, max_length=255)
    tin: Optional[str] = Field(None, max_length=20, description="Tax Identification Number")
    
    # Contact Information
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    
    # Address
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    
    # Settings
    is_vat_registered: bool = False
    credit_limit: Optional[float] = Field(None, ge=0)
    payment_terms_days: int = Field(30, ge=0)
    
    notes: Optional[str] = None


class CustomerUpdateRequest(BaseModel):
    """Schema for updating a customer."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tin: Optional[str] = Field(None, max_length=20)
    
    # Contact Information
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    
    # Address
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    
    # Settings
    is_vat_registered: Optional[bool] = None
    credit_limit: Optional[float] = Field(None, ge=0)
    payment_terms_days: Optional[int] = Field(None, ge=0)
    
    notes: Optional[str] = None


# ===========================================
# RESPONSE SCHEMAS
# ===========================================

class CustomerResponse(BaseModel):
    """Schema for customer response."""
    id: UUID
    entity_id: UUID
    name: str
    tin: Optional[str] = None
    
    # Contact Information
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    
    # Settings
    is_vat_registered: bool
    credit_limit: Optional[float] = None
    payment_terms_days: int
    
    # Stats
    total_invoiced: float
    total_paid: float
    outstanding_balance: float
    invoice_count: int
    
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """List of customers response."""
    customers: List[CustomerResponse]
    total: int


class CustomerSummaryResponse(BaseModel):
    """Brief customer info for dropdowns."""
    id: UUID
    name: str
    tin: Optional[str] = None
    is_vat_registered: bool
    outstanding_balance: float
    
    class Config:
        from_attributes = True
