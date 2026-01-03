"""
TekVwarho ProAudit - Business Entities Router

API endpoints for business entity management.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user, require_role
from app.models.user import User, UserRole
from app.schemas.entity import (
    EntityCreateRequest,
    EntityUpdateRequest,
    EntityResponse,
    EntityListResponse,
    EntitySummaryResponse,
)
from app.schemas.auth import MessageResponse
from app.services.entity_service import EntityService


router = APIRouter()


@router.get(
    "",
    response_model=EntityListResponse,
    summary="List business entities",
    description="Get all business entities the current user has access to.",
)
async def list_entities(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all entities user has access to."""
    entity_service = EntityService(db)
    entities = await entity_service.get_entities_for_user(current_user)
    
    entity_responses = []
    for entity in entities:
        entity_responses.append(
            EntityResponse(
                id=entity.id,
                organization_id=entity.organization_id,
                name=entity.name,
                legal_name=entity.legal_name,
                tin=entity.tin,
                rc_number=entity.rc_number,
                address_line1=entity.address_line1,
                address_line2=entity.address_line2,
                city=entity.city,
                state=entity.state,
                country=entity.country,
                full_address=entity.full_address,
                email=entity.email,
                phone=entity.phone,
                website=entity.website,
                fiscal_year_start_month=entity.fiscal_year_start_month,
                currency=entity.currency,
                is_vat_registered=entity.is_vat_registered,
                vat_registration_date=entity.vat_registration_date,
                annual_turnover_threshold=entity.annual_turnover_threshold,
                is_active=entity.is_active,
                created_at=entity.created_at,
                updated_at=entity.updated_at,
            )
        )
    
    return EntityListResponse(
        entities=entity_responses,
        total=len(entity_responses),
    )


@router.post(
    "",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create business entity",
    description="Create a new business entity. Only owners and admins can create entities.",
)
async def create_entity(
    request: EntityCreateRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new business entity."""
    entity_service = EntityService(db)
    
    entity = await entity_service.create_entity(
        user=current_user,
        name=request.name,
        legal_name=request.legal_name,
        tin=request.tin,
        rc_number=request.rc_number,
        address_line1=request.address_line1,
        address_line2=request.address_line2,
        city=request.city,
        state=request.state,
        email=request.email,
        phone=request.phone,
        website=request.website,
        fiscal_year_start_month=request.fiscal_year_start_month,
        currency=request.currency,
        is_vat_registered=request.is_vat_registered,
        vat_registration_date=request.vat_registration_date,
        annual_turnover_threshold=request.annual_turnover_threshold,
    )
    
    return EntityResponse(
        id=entity.id,
        organization_id=entity.organization_id,
        name=entity.name,
        legal_name=entity.legal_name,
        tin=entity.tin,
        rc_number=entity.rc_number,
        address_line1=entity.address_line1,
        address_line2=entity.address_line2,
        city=entity.city,
        state=entity.state,
        country=entity.country,
        full_address=entity.full_address,
        email=entity.email,
        phone=entity.phone,
        website=entity.website,
        fiscal_year_start_month=entity.fiscal_year_start_month,
        currency=entity.currency,
        is_vat_registered=entity.is_vat_registered,
        vat_registration_date=entity.vat_registration_date,
        annual_turnover_threshold=entity.annual_turnover_threshold,
        is_active=entity.is_active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get(
    "/{entity_id}",
    response_model=EntityResponse,
    summary="Get business entity",
    description="Get a specific business entity by ID.",
)
async def get_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    return EntityResponse(
        id=entity.id,
        organization_id=entity.organization_id,
        name=entity.name,
        legal_name=entity.legal_name,
        tin=entity.tin,
        rc_number=entity.rc_number,
        address_line1=entity.address_line1,
        address_line2=entity.address_line2,
        city=entity.city,
        state=entity.state,
        country=entity.country,
        full_address=entity.full_address,
        email=entity.email,
        phone=entity.phone,
        website=entity.website,
        fiscal_year_start_month=entity.fiscal_year_start_month,
        currency=entity.currency,
        is_vat_registered=entity.is_vat_registered,
        vat_registration_date=entity.vat_registration_date,
        annual_turnover_threshold=entity.annual_turnover_threshold,
        is_active=entity.is_active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.patch(
    "/{entity_id}",
    response_model=EntityResponse,
    summary="Update business entity",
    description="Update a business entity. Requires write access.",
)
async def update_entity(
    entity_id: UUID,
    request: EntityUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a business entity."""
    entity_service = EntityService(db)
    
    # Check access
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    # Check write permission
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    # Update entity
    update_data = request.model_dump(exclude_unset=True)
    entity = await entity_service.update_entity(entity, **update_data)
    
    return EntityResponse(
        id=entity.id,
        organization_id=entity.organization_id,
        name=entity.name,
        legal_name=entity.legal_name,
        tin=entity.tin,
        rc_number=entity.rc_number,
        address_line1=entity.address_line1,
        address_line2=entity.address_line2,
        city=entity.city,
        state=entity.state,
        country=entity.country,
        full_address=entity.full_address,
        email=entity.email,
        phone=entity.phone,
        website=entity.website,
        fiscal_year_start_month=entity.fiscal_year_start_month,
        currency=entity.currency,
        is_vat_registered=entity.is_vat_registered,
        vat_registration_date=entity.vat_registration_date,
        annual_turnover_threshold=entity.annual_turnover_threshold,
        is_active=entity.is_active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.delete(
    "/{entity_id}",
    response_model=MessageResponse,
    summary="Delete business entity",
    description="Soft delete a business entity. Only owners can delete entities.",
)
async def delete_entity(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete (deactivate) a business entity."""
    entity_service = EntityService(db)
    
    # Check access
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    # Check delete permission
    can_delete = await entity_service.check_user_can_delete(current_user, entity_id)
    if not can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Delete access denied for this entity",
        )
    
    await entity_service.delete_entity(entity)
    
    return MessageResponse(
        message="Entity deleted successfully",
        success=True,
    )
