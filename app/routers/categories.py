"""
TekVwarho ProAudit - Categories Router

API endpoints for category management with WREN classification.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.services.category_service import CategoryService
from app.services.entity_service import EntityService


router = APIRouter()


# Simplified schemas matching actual model
class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    category_type: str
    vat_treatment: str
    parent_id: Optional[UUID] = None
    wren_default: bool
    wren_review_required: bool
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """List of categories response."""
    categories: list[CategoryResponse]
    total: int


@router.get(
    "/{entity_id}/categories",
    response_model=CategoryListResponse,
    summary="List categories",
    description="Get all categories for a business entity.",
)
async def list_categories(
    entity_id: UUID,
    category_type: Optional[str] = Query(None, description="Filter by type: income, expense"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all categories for an entity."""
    # Verify entity access
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    category_service = CategoryService(db)
    categories = await category_service.get_categories_for_entity(
        entity_id,
        category_type=category_type,
    )
    
    category_responses = [
        CategoryResponse(
            id=cat.id,
            name=cat.name,
            code=cat.code,
            description=cat.description,
            category_type=cat.category_type.value,
            vat_treatment=cat.vat_treatment.value,
            parent_id=cat.parent_id,
            wren_default=cat.wren_default,
            wren_review_required=cat.wren_review_required,
            is_system=cat.is_system,
            is_active=cat.is_active,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
        )
        for cat in categories
    ]
    
    return CategoryListResponse(
        categories=category_responses,
        total=len(category_responses),
    )


@router.get(
    "/{entity_id}/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Get category",
    description="Get a specific category by ID.",
)
async def get_category(
    entity_id: UUID,
    category_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific category."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    category_service = CategoryService(db)
    category = await category_service.get_category_by_id(category_id, entity_id)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        code=category.code,
        description=category.description,
        category_type=category.category_type.value,
        vat_treatment=category.vat_treatment.value,
        parent_id=category.parent_id,
        wren_default=category.wren_default,
        wren_review_required=category.wren_review_required,
        is_system=category.is_system,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.post(
    "/{entity_id}/categories/initialize-defaults",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize default categories",
)
async def initialize_default_categories(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Initialize default WREN categories."""
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
    
    category_service = CategoryService(db)
    
    existing = await category_service.get_categories_for_entity(entity_id)
    if any(cat.is_system for cat in existing):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default categories already exist",
        )
    
    await category_service.create_default_categories(entity_id)
    
    return MessageResponse(
        message="Default WREN categories created successfully",
        success=True,
    )
