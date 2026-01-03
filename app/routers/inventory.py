"""
TekVwarho ProAudit - Inventory Router

API endpoints for inventory management, stock tracking, and write-offs.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.services.entity_service import EntityService
from app.services.inventory_service import InventoryService
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryItemListResponse,
    StockMovementCreate,
    StockMovementResponse,
    StockReceiveRequest,
    StockSaleRequest,
    StockAdjustmentRequest,
    StockWriteOffCreate,
    StockWriteOffResponse,
    StockWriteOffReviewRequest,
    InventorySummaryResponse,
    LowStockAlertResponse,
)
from app.schemas.auth import MessageResponse


router = APIRouter()


# ===========================================
# HELPER FUNCTIONS
# ===========================================

async def verify_entity_access(
    entity_id: UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Verify user has access to the entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id)
    
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


# ===========================================
# INVENTORY ITEM ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/inventory",
    response_model=InventoryItemListResponse,
    summary="List inventory items",
)
async def list_inventory_items(
    entity_id: UUID,
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    low_stock_only: bool = Query(False),
    search: Optional[str] = Query(None, description="Search by SKU, name, or barcode"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List inventory items for a business entity.
    
    Supports filtering by:
    - category
    - active status
    - low stock items only
    - search (SKU, name, barcode)
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    items, total, low_stock_count = await service.get_items_for_entity(
        entity_id=entity_id,
        category=category,
        is_active=is_active,
        low_stock_only=low_stock_only,
        search=search,
        skip=skip,
        limit=limit,
    )
    
    return InventoryItemListResponse(
        items=[
            InventoryItemResponse(
                id=item.id,
                entity_id=item.entity_id,
                sku=item.sku,
                name=item.name,
                description=item.description,
                barcode=item.barcode,
                category=item.category,
                unit_cost=float(item.unit_cost),
                unit_price=float(item.unit_price),
                quantity_on_hand=item.quantity_on_hand,
                reorder_level=item.reorder_level,
                reorder_quantity=item.reorder_quantity,
                unit_of_measure=item.unit_of_measure,
                is_active=item.is_active,
                is_tracked=item.is_tracked,
                is_low_stock=item.is_low_stock,
                stock_value=float(item.stock_value),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        low_stock_count=low_stock_count,
    )


@router.post(
    "/{entity_id}/inventory",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inventory item",
)
async def create_inventory_item(
    entity_id: UUID,
    request: InventoryItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new inventory item."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    try:
        item = await service.create_item(
            entity_id=entity_id,
            sku=request.sku,
            name=request.name,
            description=request.description,
            barcode=request.barcode,
            category=request.category,
            unit_cost=request.unit_cost,
            unit_price=request.unit_price,
            quantity_on_hand=request.quantity_on_hand,
            reorder_level=request.reorder_level,
            reorder_quantity=request.reorder_quantity,
            unit_of_measure=request.unit_of_measure,
            is_tracked=request.is_tracked,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get(
    "/{entity_id}/inventory/{item_id}",
    response_model=InventoryItemResponse,
    summary="Get inventory item",
)
async def get_inventory_item(
    entity_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific inventory item."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    item = await service.get_item_by_id(item_id)
    
    if not item or item.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.patch(
    "/{entity_id}/inventory/{item_id}",
    response_model=InventoryItemResponse,
    summary="Update inventory item",
)
async def update_inventory_item(
    entity_id: UUID,
    item_id: UUID,
    request: InventoryItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update an inventory item."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    # Verify item belongs to entity
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    
    try:
        item = await service.update_item(item_id, update_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete(
    "/{entity_id}/inventory/{item_id}",
    response_model=MessageResponse,
    summary="Delete inventory item",
)
async def delete_inventory_item(
    entity_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete (deactivate) an inventory item."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    await service.delete_item(item_id)
    
    return MessageResponse(message="Inventory item deactivated successfully")


# ===========================================
# STOCK OPERATIONS
# ===========================================

@router.post(
    "/{entity_id}/inventory/{item_id}/receive",
    response_model=InventoryItemResponse,
    summary="Receive stock",
)
async def receive_stock(
    entity_id: UUID,
    item_id: UUID,
    request: StockReceiveRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Receive stock from a purchase.
    
    Updates stock quantity and weighted average cost.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    try:
        item = await service.receive_stock(
            item_id=item_id,
            quantity=request.quantity,
            unit_cost=request.unit_cost,
            reference=request.reference,
            notes=request.notes,
            receive_date=request.receive_date,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "/{entity_id}/inventory/{item_id}/sale",
    response_model=InventoryItemResponse,
    summary="Record sale",
)
async def record_sale(
    entity_id: UUID,
    item_id: UUID,
    request: StockSaleRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record a sale (reduce stock).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    try:
        item = await service.record_sale(
            item_id=item_id,
            quantity=request.quantity,
            reference=request.reference,
            notes=request.notes,
            sale_date=request.sale_date,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "/{entity_id}/inventory/{item_id}/adjust",
    response_model=InventoryItemResponse,
    summary="Adjust stock",
)
async def adjust_stock(
    entity_id: UUID,
    item_id: UUID,
    request: StockAdjustmentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Adjust stock quantity (positive or negative).
    
    Use this for physical count corrections, etc.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    try:
        item = await service.adjust_stock(
            item_id=item_id,
            quantity_change=request.quantity_change,
            reason=request.reason,
            reference=request.reference,
            adjustment_date=request.adjustment_date,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return InventoryItemResponse(
        id=item.id,
        entity_id=item.entity_id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        barcode=item.barcode,
        category=item.category,
        unit_cost=float(item.unit_cost),
        unit_price=float(item.unit_price),
        quantity_on_hand=item.quantity_on_hand,
        reorder_level=item.reorder_level,
        reorder_quantity=item.reorder_quantity,
        unit_of_measure=item.unit_of_measure,
        is_active=item.is_active,
        is_tracked=item.is_tracked,
        is_low_stock=item.is_low_stock,
        stock_value=float(item.stock_value),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get(
    "/{entity_id}/inventory/{item_id}/movements",
    response_model=List[StockMovementResponse],
    summary="Get stock movements",
)
async def get_stock_movements(
    entity_id: UUID,
    item_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    movement_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get stock movement history for an item."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    from app.models.inventory import StockMovementType
    
    mt = None
    if movement_type:
        try:
            mt = StockMovementType(movement_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid movement type. Valid types: {[t.value for t in StockMovementType]}",
            )
    
    movements = await service.get_movements_for_item(
        item_id=item_id,
        start_date=start_date,
        end_date=end_date,
        movement_type=mt,
        limit=limit,
    )
    
    return [
        StockMovementResponse(
            id=m.id,
            item_id=m.item_id,
            movement_type=m.movement_type.value,
            quantity=m.quantity,
            unit_cost=float(m.unit_cost),
            reference=m.reference,
            notes=m.notes,
            movement_date=m.movement_date,
            created_at=m.created_at,
            created_by=m.created_by,
        )
        for m in movements
    ]


# ===========================================
# WRITE-OFF ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/inventory/{item_id}/write-off",
    response_model=StockWriteOffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create write-off",
)
async def create_write_off(
    entity_id: UUID,
    item_id: UUID,
    request: StockWriteOffCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a stock write-off for damaged/expired goods.
    
    Write-offs are flagged for tax deduction review.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    existing = await service.get_item_by_id(item_id)
    if not existing or existing.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    
    try:
        write_off = await service.create_write_off(
            item_id=item_id,
            quantity=request.quantity,
            reason=request.reason,
            notes=request.notes,
            documentation_url=request.documentation_url,
            write_off_date=request.write_off_date,
            is_tax_deductible=request.is_tax_deductible,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return StockWriteOffResponse(
        id=write_off.id,
        item_id=write_off.item_id,
        quantity=write_off.quantity,
        unit_cost=float(write_off.unit_cost),
        total_value=float(write_off.total_value),
        reason=write_off.reason.value,
        notes=write_off.notes,
        documentation_url=write_off.documentation_url,
        write_off_date=write_off.write_off_date,
        is_tax_deductible=write_off.is_tax_deductible,
        reviewed=write_off.reviewed,
        reviewed_at=write_off.reviewed_at,
        created_at=write_off.created_at,
        created_by=write_off.created_by,
    )


@router.get(
    "/{entity_id}/write-offs",
    response_model=List[StockWriteOffResponse],
    summary="List write-offs",
)
async def list_write_offs(
    entity_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    reviewed: Optional[bool] = Query(None),
    is_tax_deductible: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all write-offs for a business entity."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    write_offs = await service.get_write_offs_for_entity(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        reviewed=reviewed,
        is_tax_deductible=is_tax_deductible,
    )
    
    return [
        StockWriteOffResponse(
            id=wo.id,
            item_id=wo.item_id,
            quantity=wo.quantity,
            unit_cost=float(wo.unit_cost),
            total_value=float(wo.total_value),
            reason=wo.reason.value,
            notes=wo.notes,
            documentation_url=wo.documentation_url,
            write_off_date=wo.write_off_date,
            is_tax_deductible=wo.is_tax_deductible,
            reviewed=wo.reviewed,
            reviewed_at=wo.reviewed_at,
            created_at=wo.created_at,
            created_by=wo.created_by,
        )
        for wo in write_offs
    ]


@router.post(
    "/{entity_id}/write-offs/{write_off_id}/review",
    response_model=StockWriteOffResponse,
    summary="Review write-off",
)
async def review_write_off(
    entity_id: UUID,
    write_off_id: UUID,
    request: StockWriteOffReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Review a write-off (accountant/auditor approval).
    
    Confirms tax deductibility status.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    
    try:
        write_off = await service.review_write_off(
            write_off_id=write_off_id,
            is_tax_deductible=request.is_tax_deductible,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    
    return StockWriteOffResponse(
        id=write_off.id,
        item_id=write_off.item_id,
        quantity=write_off.quantity,
        unit_cost=float(write_off.unit_cost),
        total_value=float(write_off.total_value),
        reason=write_off.reason.value,
        notes=write_off.notes,
        documentation_url=write_off.documentation_url,
        write_off_date=write_off.write_off_date,
        is_tax_deductible=write_off.is_tax_deductible,
        reviewed=write_off.reviewed,
        reviewed_at=write_off.reviewed_at,
        created_at=write_off.created_at,
        created_by=write_off.created_by,
    )


# ===========================================
# REPORTS & ALERTS
# ===========================================

@router.get(
    "/{entity_id}/inventory/summary",
    response_model=InventorySummaryResponse,
    summary="Get inventory summary",
)
async def get_inventory_summary(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get inventory summary for a business entity."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    summary = await service.get_inventory_summary(entity_id)
    
    return InventorySummaryResponse(**summary)


@router.get(
    "/{entity_id}/inventory/low-stock",
    response_model=List[LowStockAlertResponse],
    summary="Get low stock alerts",
)
async def get_low_stock_alerts(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get items with stock at or below reorder level."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = InventoryService(db)
    alerts = await service.get_low_stock_alerts(entity_id)
    
    return [LowStockAlertResponse(**a) for a in alerts]
