"""
TekVwarho ProAudit - Vendors Router

API endpoints for vendor management with TIN verification.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.vendor import (
    VendorCreateRequest,
    VendorUpdateRequest,
    VendorResponse,
    VendorListResponse,
    TINVerificationResponse,
)
from app.services.vendor_service import VendorService
from app.services.entity_service import EntityService


router = APIRouter()


@router.get(
    "/{entity_id}/vendors",
    response_model=VendorListResponse,
    summary="List vendors",
    description="Get all vendors for a business entity.",
)
async def list_vendors(
    entity_id: UUID,
    search: Optional[str] = Query(None, description="Search by name, TIN, or email"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all vendors for an entity."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    vendor_service = VendorService(db)
    vendors = await vendor_service.get_vendors_for_entity(
        entity_id,
        search=search,
    )
    
    vendor_responses = []
    for vendor in vendors:
        stats = await vendor_service.get_vendor_stats(vendor)
        vendor_responses.append(
            VendorResponse(
                id=vendor.id,
                entity_id=vendor.entity_id,
                name=vendor.name,
                tin=vendor.tin,
                contact_person=vendor.contact_person,
                email=vendor.email,
                phone=vendor.phone,
                address=vendor.address,
                city=vendor.city,
                state=vendor.state,
                country=vendor.country,
                bank_name=vendor.bank_name,
                bank_account_number=vendor.bank_account_number,
                bank_account_name=vendor.bank_account_name,
                is_vat_registered=vendor.is_vat_registered,
                default_wht_rate=vendor.default_wht_rate,
                tin_verified=vendor.tin_verified,
                tin_verified_at=vendor.tin_verified_at,
                total_paid=stats["total_paid"],
                transaction_count=stats["transaction_count"],
                notes=vendor.notes,
                is_active=vendor.is_active,
                created_at=vendor.created_at,
                updated_at=vendor.updated_at,
            )
        )
    
    return VendorListResponse(
        vendors=vendor_responses,
        total=len(vendor_responses),
    )


@router.post(
    "/{entity_id}/vendors",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor",
    description="Create a new vendor for a business entity.",
)
async def create_vendor(
    entity_id: UUID,
    request: VendorCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new vendor."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    vendor_service = VendorService(db)
    
    try:
        vendor = await vendor_service.create_vendor(
            entity_id=entity_id,
            name=request.name,
            tin=request.tin,
            contact_person=request.contact_person,
            email=request.email,
            phone=request.phone,
            address=request.address,
            city=request.city,
            state=request.state,
            bank_name=request.bank_name,
            bank_account_number=request.bank_account_number,
            bank_account_name=request.bank_account_name,
            is_vat_registered=request.is_vat_registered,
            default_wht_rate=request.default_wht_rate,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return VendorResponse(
        id=vendor.id,
        entity_id=vendor.entity_id,
        name=vendor.name,
        tin=vendor.tin,
        contact_person=vendor.contact_person,
        email=vendor.email,
        phone=vendor.phone,
        address=vendor.address,
        city=vendor.city,
        state=vendor.state,
        country=vendor.country,
        bank_name=vendor.bank_name,
        bank_account_number=vendor.bank_account_number,
        bank_account_name=vendor.bank_account_name,
        is_vat_registered=vendor.is_vat_registered,
        default_wht_rate=vendor.default_wht_rate,
        tin_verified=vendor.tin_verified,
        tin_verified_at=vendor.tin_verified_at,
        total_paid=0.0,
        transaction_count=0,
        notes=vendor.notes,
        is_active=vendor.is_active,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


@router.get(
    "/{entity_id}/vendors/{vendor_id}",
    response_model=VendorResponse,
    summary="Get vendor",
    description="Get a specific vendor by ID.",
)
async def get_vendor(
    entity_id: UUID,
    vendor_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific vendor."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    vendor_service = VendorService(db)
    vendor = await vendor_service.get_vendor_by_id(vendor_id, entity_id)
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    stats = await vendor_service.get_vendor_stats(vendor)
    
    return VendorResponse(
        id=vendor.id,
        entity_id=vendor.entity_id,
        name=vendor.name,
        tin=vendor.tin,
        contact_person=vendor.contact_person,
        email=vendor.email,
        phone=vendor.phone,
        address=vendor.address,
        city=vendor.city,
        state=vendor.state,
        country=vendor.country,
        bank_name=vendor.bank_name,
        bank_account_number=vendor.bank_account_number,
        bank_account_name=vendor.bank_account_name,
        is_vat_registered=vendor.is_vat_registered,
        default_wht_rate=vendor.default_wht_rate,
        tin_verified=vendor.tin_verified,
        tin_verified_at=vendor.tin_verified_at,
        total_paid=stats["total_paid"],
        transaction_count=stats["transaction_count"],
        notes=vendor.notes,
        is_active=vendor.is_active,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


@router.patch(
    "/{entity_id}/vendors/{vendor_id}",
    response_model=VendorResponse,
    summary="Update vendor",
    description="Update a vendor. Changing TIN will reset verification status.",
)
async def update_vendor(
    entity_id: UUID,
    vendor_id: UUID,
    request: VendorUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a vendor."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    vendor_service = VendorService(db)
    vendor = await vendor_service.get_vendor_by_id(vendor_id, entity_id)
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    vendor = await vendor_service.update_vendor(vendor, **update_data)
    stats = await vendor_service.get_vendor_stats(vendor)
    
    return VendorResponse(
        id=vendor.id,
        entity_id=vendor.entity_id,
        name=vendor.name,
        tin=vendor.tin,
        contact_person=vendor.contact_person,
        email=vendor.email,
        phone=vendor.phone,
        address=vendor.address,
        city=vendor.city,
        state=vendor.state,
        country=vendor.country,
        bank_name=vendor.bank_name,
        bank_account_number=vendor.bank_account_number,
        bank_account_name=vendor.bank_account_name,
        is_vat_registered=vendor.is_vat_registered,
        default_wht_rate=vendor.default_wht_rate,
        tin_verified=vendor.tin_verified,
        tin_verified_at=vendor.tin_verified_at,
        total_paid=stats["total_paid"],
        transaction_count=stats["transaction_count"],
        notes=vendor.notes,
        is_active=vendor.is_active,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )


@router.delete(
    "/{entity_id}/vendors/{vendor_id}",
    response_model=MessageResponse,
    summary="Delete vendor",
    description="Soft delete a vendor.",
)
async def delete_vendor(
    entity_id: UUID,
    vendor_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a vendor."""
    # Verify entity access and write permission
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    vendor_service = VendorService(db)
    vendor = await vendor_service.get_vendor_by_id(vendor_id, entity_id)
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    await vendor_service.delete_vendor(vendor)
    
    return MessageResponse(
        message="Vendor deleted successfully",
        success=True,
    )


@router.post(
    "/{entity_id}/vendors/{vendor_id}/verify-tin",
    response_model=TINVerificationResponse,
    summary="Verify vendor TIN",
    description="Verify vendor TIN with FIRS/NRS.",
)
async def verify_vendor_tin(
    entity_id: UUID,
    vendor_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Verify vendor TIN."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    vendor_service = VendorService(db)
    vendor = await vendor_service.get_vendor_by_id(vendor_id, entity_id)
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    
    if not vendor.tin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vendor has no TIN to verify",
        )
    
    verified, message = await vendor_service.verify_tin(vendor)
    
    return TINVerificationResponse(
        vendor_id=vendor.id,
        tin=vendor.tin,
        verified=verified,
        verified_at=vendor.tin_verified_at if verified else None,
        verification_message=message,
    )
