"""
Fixed Assets Router - API endpoints for Fixed Asset Register.

2026 Nigeria Tax Reform Compliance:
- Fixed assets tracked for depreciation and capital gains
- Capital gains on disposal taxed at CIT rate
- VAT recovery on qualifying capital assets via IRN
- Integration with Development Levy threshold calculation

Author: TekVwarho ProAudit
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user, require_organization_permission
from app.models.user import User, UserRole
from app.utils.permissions import OrganizationPermission
from app.models.fixed_asset import (
    AssetCategory,
    AssetStatus,
    DepreciationMethod,
    DisposalType,
)
from app.services.fixed_asset_service import FixedAssetService

router = APIRouter(prefix="/api/v1/fixed-assets", tags=["Fixed Assets"])


# ===========================================
# PYDANTIC SCHEMAS
# ===========================================

class FixedAssetCreate(BaseModel):
    """Schema for creating a new fixed asset."""
    entity_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: AssetCategory
    
    # Acquisition details
    acquisition_date: date
    acquisition_cost: Decimal = Field(..., ge=0)
    vendor_name: Optional[str] = None
    vendor_irn: Optional[str] = Field(None, description="Invoice Reference Number for VAT recovery")
    invoice_number: Optional[str] = None
    
    # Depreciation settings
    depreciation_method: DepreciationMethod = DepreciationMethod.STRAIGHT_LINE
    useful_life_years: Optional[int] = Field(None, ge=1, le=100)
    depreciation_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    residual_value: Decimal = Field(default=Decimal("0"), ge=0)
    
    # Physical details
    serial_number: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    
    # Insurance
    is_insured: bool = False
    insurance_policy_number: Optional[str] = None
    insurance_value: Optional[Decimal] = Field(None, ge=0)
    insurance_expiry_date: Optional[date] = None

    class Config:
        json_encoders = {
            Decimal: str,
        }


class FixedAssetUpdate(BaseModel):
    """Schema for updating a fixed asset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[AssetCategory] = None
    status: Optional[AssetStatus] = None
    
    # Physical details
    serial_number: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    
    # Insurance
    is_insured: Optional[bool] = None
    insurance_policy_number: Optional[str] = None
    insurance_value: Optional[Decimal] = Field(None, ge=0)
    insurance_expiry_date: Optional[date] = None

    class Config:
        json_encoders = {
            Decimal: str,
        }


class AssetDisposalRequest(BaseModel):
    """Schema for disposing of an asset."""
    disposal_type: DisposalType
    disposal_date: date
    disposal_proceeds: Decimal = Field(default=Decimal("0"), ge=0)
    buyer_name: Optional[str] = None
    buyer_tin: Optional[str] = None
    notes: Optional[str] = None


class DepreciationRunRequest(BaseModel):
    """Schema for running depreciation."""
    entity_id: UUID
    fiscal_year_end: date
    period_start: date
    period_end: date


class FixedAssetResponse(BaseModel):
    """Response schema for fixed asset."""
    id: UUID
    entity_id: UUID
    name: str
    description: Optional[str]
    asset_code: str
    category: str
    status: str
    
    acquisition_date: date
    acquisition_cost: Decimal
    vendor_name: Optional[str]
    vendor_irn: Optional[str]
    
    depreciation_method: str
    useful_life_years: Optional[int]
    depreciation_rate: Decimal
    residual_value: Decimal
    accumulated_depreciation: Decimal
    net_book_value: Decimal
    is_fully_depreciated: bool
    
    location: Optional[str]
    is_insured: bool
    
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: str,
        }


# ===========================================
# CRUD ENDPOINTS
# ===========================================

@router.post(
    "/",
    response_model=FixedAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new fixed asset",
)
async def create_fixed_asset(
    asset_data: FixedAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_organization_permission([OrganizationPermission.CREATE_TRANSACTIONS])
    ),
):
    """
    Create a new fixed asset in the register.
    
    Required for 2026 compliance:
    - Track acquisition cost for depreciation
    - Capture vendor IRN for VAT recovery on capital assets
    - Auto-generate asset code for tracking
    """
    service = FixedAssetService(db)
    
    try:
        asset = await service.create_asset(
            entity_id=asset_data.entity_id,
            name=asset_data.name,
            category=asset_data.category,
            acquisition_date=asset_data.acquisition_date,
            acquisition_cost=asset_data.acquisition_cost,
            depreciation_method=asset_data.depreciation_method,
            useful_life_years=asset_data.useful_life_years,
            depreciation_rate=asset_data.depreciation_rate,
            residual_value=asset_data.residual_value,
            vendor_name=asset_data.vendor_name,
            vendor_irn=asset_data.vendor_irn,
            invoice_number=asset_data.invoice_number,
            description=asset_data.description,
            serial_number=asset_data.serial_number,
            location=asset_data.location,
            condition=asset_data.condition,
            is_insured=asset_data.is_insured,
            insurance_policy_number=asset_data.insurance_policy_number,
            insurance_value=asset_data.insurance_value,
            insurance_expiry_date=asset_data.insurance_expiry_date,
            created_by_id=current_user.id,
        )
        
        return _asset_to_response(asset)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/entity/{entity_id}",
    response_model=List[FixedAssetResponse],
    summary="Get all fixed assets for an entity",
)
async def get_entity_assets(
    entity_id: UUID,
    status: Optional[AssetStatus] = Query(None, description="Filter by status"),
    category: Optional[AssetCategory] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get all fixed assets for a specific entity."""
    service = FixedAssetService(db)
    
    assets = await service.get_assets_for_entity(
        entity_id=entity_id,
        status=status,
        category=category,
    )
    
    return [_asset_to_response(asset) for asset in assets]


@router.get(
    "/{asset_id}",
    response_model=FixedAssetResponse,
    summary="Get a specific fixed asset",
)
async def get_fixed_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get details of a specific fixed asset."""
    service = FixedAssetService(db)
    
    asset = await service.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    return _asset_to_response(asset)


@router.patch(
    "/{asset_id}",
    response_model=FixedAssetResponse,
    summary="Update a fixed asset",
)
async def update_fixed_asset(
    asset_id: UUID,
    asset_data: FixedAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_organization_permission([OrganizationPermission.CREATE_TRANSACTIONS])
    ),
):
    """Update a fixed asset's details."""
    service = FixedAssetService(db)
    
    asset = await service.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Build update dict from provided fields
    update_dict = asset_data.model_dump(exclude_unset=True)
    
    try:
        updated_asset = await service.update_asset(
            asset_id=asset_id,
            updated_by_id=current_user.id,
            **update_dict,
        )
        return _asset_to_response(updated_asset)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================
# DEPRECIATION ENDPOINTS
# ===========================================

@router.post(
    "/depreciation/run",
    summary="Run depreciation for all active assets",
)
async def run_depreciation(
    request: DepreciationRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_organization_permission([OrganizationPermission.CREATE_TRANSACTIONS])
    ),
):
    """
    Run depreciation posting for all active assets in an entity.
    
    This should be run at the end of each fiscal period (monthly/annually).
    Creates depreciation entries and updates accumulated depreciation.
    """
    service = FixedAssetService(db)
    
    try:
        entries = await service.run_depreciation(
            entity_id=request.entity_id,
            fiscal_year_end=request.fiscal_year_end,
            period_start=request.period_start,
            period_end=request.period_end,
            created_by_id=current_user.id,
        )
        
        return {
            "message": f"Depreciation posted for {len(entries)} assets",
            "entries_created": len(entries),
            "period": f"{request.period_start} to {request.period_end}",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/entity/{entity_id}/depreciation-schedule",
    summary="Get depreciation schedule for fiscal year",
)
async def get_depreciation_schedule(
    entity_id: UUID,
    fiscal_year_end: date = Query(..., description="Fiscal year end date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get depreciation schedule for all assets in an entity for a fiscal year.
    
    Shows opening balance, depreciation amount, and closing balance for each asset.
    """
    service = FixedAssetService(db)
    
    schedule = await service.get_depreciation_schedule(
        entity_id=entity_id,
        fiscal_year_end=fiscal_year_end,
    )
    
    return schedule


# ===========================================
# DISPOSAL ENDPOINTS
# ===========================================

@router.post(
    "/{asset_id}/dispose",
    summary="Dispose of a fixed asset",
)
async def dispose_asset(
    asset_id: UUID,
    disposal: AssetDisposalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_organization_permission([OrganizationPermission.CREATE_TRANSACTIONS])
    ),
):
    """
    Dispose of a fixed asset.
    
    2026 Compliance:
    - Capital gains on disposal are taxed at CIT rate
    - Must capture buyer details for audit trail
    - Proceeds are compared to net book value for gain/loss
    """
    service = FixedAssetService(db)
    
    asset = await service.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset.status == AssetStatus.DISPOSED:
        raise HTTPException(status_code=400, detail="Asset already disposed")
    
    try:
        disposed_asset, capital_gain = await service.dispose_asset(
            asset_id=asset_id,
            disposal_type=disposal.disposal_type,
            disposal_date=disposal.disposal_date,
            disposal_proceeds=disposal.disposal_proceeds,
            buyer_name=disposal.buyer_name,
            buyer_tin=disposal.buyer_tin,
            notes=disposal.notes,
            disposed_by_id=current_user.id,
        )
        
        return {
            "message": "Asset disposed successfully",
            "asset_id": str(disposed_asset.id),
            "asset_name": disposed_asset.name,
            "disposal_type": disposal.disposal_type.value,
            "disposal_proceeds": str(disposal.disposal_proceeds),
            "net_book_value_at_disposal": str(disposed_asset.net_book_value),
            "capital_gain_loss": str(capital_gain),
            "tax_note": "Capital gains taxed at CIT rate under 2026 reform" if capital_gain > 0 else None,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================
# REPORTING ENDPOINTS
# ===========================================

@router.get(
    "/entity/{entity_id}/summary",
    summary="Get asset register summary",
)
async def get_asset_register_summary(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get summary of the fixed asset register.
    
    Returns totals by category, total values, and VAT recovery status.
    """
    service = FixedAssetService(db)
    
    summary = await service.get_asset_register_summary(entity_id)
    
    return summary


@router.get(
    "/entity/{entity_id}/capital-gains",
    summary="Get capital gains report for disposed assets",
)
async def get_capital_gains_report(
    entity_id: UUID,
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get capital gains report for disposed assets within a date range.
    
    2026 Compliance:
    - Capital gains are now taxed at CIT rate (not separate CGT)
    - Report shows all disposals with gains/losses
    - Total taxable gain for CIT calculation
    """
    service = FixedAssetService(db)
    
    report = await service.get_capital_gains_report(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return report


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def _asset_to_response(asset) -> FixedAssetResponse:
    """Convert asset model to response schema."""
    return FixedAssetResponse(
        id=asset.id,
        entity_id=asset.entity_id,
        name=asset.name,
        description=asset.description,
        asset_code=asset.asset_code,
        category=asset.category.value,
        status=asset.status.value,
        acquisition_date=asset.acquisition_date,
        acquisition_cost=asset.acquisition_cost,
        vendor_name=asset.vendor_name,
        vendor_irn=asset.vendor_irn,
        depreciation_method=asset.depreciation_method.value,
        useful_life_years=asset.useful_life_years,
        depreciation_rate=asset.depreciation_rate,
        residual_value=asset.residual_value,
        accumulated_depreciation=asset.accumulated_depreciation,
        net_book_value=asset.net_book_value,
        is_fully_depreciated=asset.is_fully_depreciated,
        location=asset.location,
        is_insured=asset.is_insured,
        created_at=asset.created_at.isoformat() if asset.created_at else "",
        updated_at=asset.updated_at.isoformat() if asset.updated_at else None,
    )
