"""
TekVwarho ProAudit - Fixed Asset Register Service

Business logic for fixed asset management, depreciation, and capital gains.

Under the 2026 Nigeria Tax Administration Act:
- Capital gains are taxed at the flat CIT rate (30% for large companies)
- Input VAT on fixed assets is now recoverable (with valid vendor IRN)
- Fixed asset values affect Development Levy exemption threshold (₦250M)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fixed_asset import (
    FixedAsset,
    DepreciationEntry,
    AssetCategory,
    AssetStatus,
    DepreciationMethod,
    DisposalType,
    STANDARD_DEPRECIATION_RATES,
)
from app.models.entity import BusinessEntity


class FixedAssetService:
    """Service for fixed asset management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # ASSET CRUD OPERATIONS
    # ===========================================
    
    async def create_asset(
        self,
        entity_id: uuid.UUID,
        asset_code: str,
        name: str,
        category: AssetCategory,
        acquisition_date: date,
        acquisition_cost: Decimal,
        description: Optional[str] = None,
        location: Optional[str] = None,
        department: Optional[str] = None,
        vendor_name: Optional[str] = None,
        vendor_invoice_number: Optional[str] = None,
        vendor_irn: Optional[str] = None,
        vat_amount: Decimal = Decimal("0"),
        depreciation_method: DepreciationMethod = DepreciationMethod.REDUCING_BALANCE,
        depreciation_rate: Optional[Decimal] = None,
        useful_life_years: Optional[int] = None,
        residual_value: Decimal = Decimal("0"),
        serial_number: Optional[str] = None,
        warranty_expiry: Optional[date] = None,
        insured_value: Optional[Decimal] = None,
        insurance_policy_number: Optional[str] = None,
        insurance_expiry: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> FixedAsset:
        """Create a new fixed asset."""
        # Check for duplicate asset code
        existing = await self.get_asset_by_code(entity_id, asset_code)
        if existing:
            raise ValueError(f"Asset with code '{asset_code}' already exists")
        
        # Use standard depreciation rate if not provided
        if depreciation_rate is None:
            depreciation_rate = STANDARD_DEPRECIATION_RATES.get(category, Decimal("20"))
        
        asset = FixedAsset(
            entity_id=entity_id,
            asset_code=asset_code,
            name=name,
            description=description,
            category=category,
            status=AssetStatus.ACTIVE,
            location=location,
            department=department,
            acquisition_date=acquisition_date,
            acquisition_cost=acquisition_cost,
            vendor_name=vendor_name,
            vendor_invoice_number=vendor_invoice_number,
            vendor_irn=vendor_irn,
            vat_amount=vat_amount,
            vat_recovered=False,
            depreciation_method=depreciation_method,
            depreciation_rate=depreciation_rate,
            useful_life_years=useful_life_years,
            residual_value=residual_value,
            accumulated_depreciation=Decimal("0"),
            serial_number=serial_number,
            warranty_expiry=warranty_expiry,
            insured_value=insured_value,
            insurance_policy_number=insurance_policy_number,
            insurance_expiry=insurance_expiry,
            notes=notes,
        )
        
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        
        return asset
    
    async def get_asset_by_id(self, asset_id: uuid.UUID) -> Optional[FixedAsset]:
        """Get an asset by ID."""
        result = await self.db.execute(
            select(FixedAsset)
            .where(FixedAsset.id == asset_id)
            .options(selectinload(FixedAsset.depreciation_entries))
        )
        return result.scalar_one_or_none()
    
    async def get_asset_by_code(
        self,
        entity_id: uuid.UUID,
        asset_code: str,
    ) -> Optional[FixedAsset]:
        """Get an asset by code."""
        result = await self.db.execute(
            select(FixedAsset)
            .where(FixedAsset.entity_id == entity_id)
            .where(FixedAsset.asset_code == asset_code)
        )
        return result.scalar_one_or_none()
    
    async def get_assets_for_entity(
        self,
        entity_id: uuid.UUID,
        category: Optional[AssetCategory] = None,
        status: Optional[AssetStatus] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[FixedAsset], int]:
        """Get assets for an entity with filters."""
        query = select(FixedAsset).where(FixedAsset.entity_id == entity_id)
        
        if category:
            query = query.where(FixedAsset.category == category)
        
        if status:
            query = query.where(FixedAsset.status == status)
        
        if search:
            search_filter = or_(
                FixedAsset.asset_code.ilike(f"%{search}%"),
                FixedAsset.name.ilike(f"%{search}%"),
                FixedAsset.description.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Get paginated results
        query = query.order_by(FixedAsset.acquisition_date.desc())
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        assets = list(result.scalars().all())
        
        return assets, total or 0
    
    async def update_asset(
        self,
        asset_id: uuid.UUID,
        **updates,
    ) -> Optional[FixedAsset]:
        """Update an asset."""
        asset = await self.get_asset_by_id(asset_id)
        if not asset:
            return None
        
        for key, value in updates.items():
            if hasattr(asset, key) and value is not None:
                setattr(asset, key, value)
        
        await self.db.commit()
        await self.db.refresh(asset)
        
        return asset
    
    # ===========================================
    # DEPRECIATION
    # ===========================================
    
    async def run_depreciation(
        self,
        entity_id: uuid.UUID,
        period_year: int,
        period_month: Optional[int] = None,
        posted_by_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Run depreciation for all active assets in an entity.
        
        Returns summary of depreciation posted.
        """
        # Get all active, non-fully-depreciated assets
        result = await self.db.execute(
            select(FixedAsset)
            .where(FixedAsset.entity_id == entity_id)
            .where(FixedAsset.status == AssetStatus.ACTIVE)
        )
        assets = list(result.scalars().all())
        
        entries_created = 0
        total_depreciation = Decimal("0")
        skipped = 0
        
        for asset in assets:
            if asset.is_fully_depreciated:
                skipped += 1
                continue
            
            # Check if depreciation already posted for this period
            existing = await self._check_depreciation_exists(
                asset.id, period_year, period_month
            )
            if existing:
                skipped += 1
                continue
            
            # Calculate depreciation
            annual_depreciation = asset.calculate_annual_depreciation()
            
            # If monthly, divide by 12
            if period_month is not None:
                depreciation_amount = annual_depreciation / 12
            else:
                depreciation_amount = annual_depreciation
            
            # Don't depreciate below residual value
            max_depreciation = asset.net_book_value - asset.residual_value
            depreciation_amount = min(depreciation_amount, max_depreciation)
            
            if depreciation_amount <= 0:
                skipped += 1
                continue
            
            # Create depreciation entry
            entry = DepreciationEntry(
                asset_id=asset.id,
                period_year=period_year,
                period_month=period_month,
                opening_book_value=asset.net_book_value,
                depreciation_amount=depreciation_amount,
                closing_book_value=asset.net_book_value - depreciation_amount,
                depreciation_method=asset.depreciation_method,
                depreciation_rate=asset.depreciation_rate,
                posted_by_id=posted_by_id,
                posted_at=datetime.utcnow(),
            )
            
            self.db.add(entry)
            
            # Update asset
            asset.accumulated_depreciation += depreciation_amount
            asset.last_depreciation_date = date.today()
            
            entries_created += 1
            total_depreciation += depreciation_amount
        
        await self.db.commit()
        
        return {
            "period": f"{period_year}/{period_month}" if period_month else str(period_year),
            "entries_created": entries_created,
            "total_depreciation": float(total_depreciation),
            "skipped": skipped,
            "message": f"Posted {entries_created} depreciation entries totaling ₦{total_depreciation:,.2f}",
        }
    
    async def _check_depreciation_exists(
        self,
        asset_id: uuid.UUID,
        period_year: int,
        period_month: Optional[int],
    ) -> bool:
        """Check if depreciation already posted for period."""
        query = select(DepreciationEntry).where(
            DepreciationEntry.asset_id == asset_id,
            DepreciationEntry.period_year == period_year,
        )
        
        if period_month is not None:
            query = query.where(DepreciationEntry.period_month == period_month)
        else:
            query = query.where(DepreciationEntry.period_month.is_(None))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    # ===========================================
    # DISPOSAL & CAPITAL GAINS
    # ===========================================
    
    async def dispose_asset(
        self,
        asset_id: uuid.UUID,
        disposal_date: date,
        disposal_type: DisposalType,
        disposal_amount: Decimal,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispose of an asset and calculate capital gain/loss.
        
        Under 2026 law, capital gains are taxed at CIT rate (30% for large companies).
        """
        asset = await self.get_asset_by_id(asset_id)
        if not asset:
            raise ValueError("Asset not found")
        
        if asset.status == AssetStatus.DISPOSED:
            raise ValueError("Asset already disposed")
        
        # Calculate capital gain/loss
        net_book_value = asset.net_book_value
        capital_gain = disposal_amount - net_book_value
        
        # Update asset
        asset.status = AssetStatus.DISPOSED
        asset.disposal_date = disposal_date
        asset.disposal_type = disposal_type
        asset.disposal_amount = disposal_amount
        asset.disposal_notes = notes
        
        await self.db.commit()
        
        return {
            "asset_code": asset.asset_code,
            "asset_name": asset.name,
            "disposal_date": disposal_date.isoformat(),
            "disposal_type": disposal_type.value,
            "acquisition_cost": float(asset.acquisition_cost),
            "accumulated_depreciation": float(asset.accumulated_depreciation),
            "net_book_value": float(net_book_value),
            "disposal_proceeds": float(disposal_amount),
            "capital_gain_loss": float(capital_gain),
            "is_gain": capital_gain > 0,
            "tax_note": "Capital gains are now taxed at the flat CIT rate under 2026 law",
        }
    
    # ===========================================
    # REPORTING
    # ===========================================
    
    async def get_asset_register_summary(
        self,
        entity_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get summary of fixed assets for the entity."""
        # Get all assets
        result = await self.db.execute(
            select(FixedAsset).where(FixedAsset.entity_id == entity_id)
        )
        assets = list(result.scalars().all())
        
        # Calculate totals
        total_cost = sum(a.acquisition_cost for a in assets)
        total_depreciation = sum(a.accumulated_depreciation for a in assets)
        total_nbv = sum(a.net_book_value for a in assets)
        
        # Group by category
        by_category = {}
        for asset in assets:
            cat = asset.category.value
            if cat not in by_category:
                by_category[cat] = {
                    "count": 0,
                    "cost": Decimal("0"),
                    "depreciation": Decimal("0"),
                    "nbv": Decimal("0"),
                }
            by_category[cat]["count"] += 1
            by_category[cat]["cost"] += asset.acquisition_cost
            by_category[cat]["depreciation"] += asset.accumulated_depreciation
            by_category[cat]["nbv"] += asset.net_book_value
        
        # Convert to float for JSON
        for cat in by_category:
            by_category[cat]["cost"] = float(by_category[cat]["cost"])
            by_category[cat]["depreciation"] = float(by_category[cat]["depreciation"])
            by_category[cat]["nbv"] = float(by_category[cat]["nbv"])
        
        # Active vs disposed
        active_count = sum(1 for a in assets if a.status == AssetStatus.ACTIVE)
        disposed_count = sum(1 for a in assets if a.status == AssetStatus.DISPOSED)
        
        # VAT recovery status
        vat_recoverable = sum(
            a.vat_amount for a in assets 
            if a.vendor_irn and not a.vat_recovered
        )
        vat_recovered = sum(a.vat_amount for a in assets if a.vat_recovered)
        
        return {
            "total_assets": len(assets),
            "active_assets": active_count,
            "disposed_assets": disposed_count,
            "total_acquisition_cost": float(total_cost),
            "total_accumulated_depreciation": float(total_depreciation),
            "total_net_book_value": float(total_nbv),
            "by_category": by_category,
            "vat_recovery": {
                "recoverable_pending": float(vat_recoverable),
                "already_recovered": float(vat_recovered),
                "note": "2026 law allows VAT recovery on capital assets with valid vendor IRN",
            },
            "development_levy_note": f"Total NBV of ₦{total_nbv:,.2f} counts toward ₦250M fixed assets threshold for Development Levy exemption",
        }
    
    async def get_depreciation_schedule(
        self,
        entity_id: uuid.UUID,
        fiscal_year: int,
    ) -> List[Dict[str, Any]]:
        """Get depreciation schedule for fiscal year."""
        result = await self.db.execute(
            select(FixedAsset)
            .where(FixedAsset.entity_id == entity_id)
            .where(FixedAsset.status == AssetStatus.ACTIVE)
            .order_by(FixedAsset.category, FixedAsset.asset_code)
        )
        assets = list(result.scalars().all())
        
        schedule = []
        for asset in assets:
            annual_dep = asset.calculate_annual_depreciation()
            schedule.append({
                "asset_code": asset.asset_code,
                "name": asset.name,
                "category": asset.category.value,
                "acquisition_cost": float(asset.acquisition_cost),
                "opening_nbv": float(asset.net_book_value),
                "depreciation_rate": float(asset.depreciation_rate),
                "annual_depreciation": float(annual_dep),
                "closing_nbv": float(asset.net_book_value - annual_dep),
                "method": asset.depreciation_method.value,
            })
        
        return schedule
    
    async def get_capital_gains_report(
        self,
        entity_id: uuid.UUID,
        fiscal_year: int,
    ) -> Dict[str, Any]:
        """Get capital gains/losses for disposed assets in fiscal year."""
        result = await self.db.execute(
            select(FixedAsset)
            .where(FixedAsset.entity_id == entity_id)
            .where(FixedAsset.status == AssetStatus.DISPOSED)
            .where(extract("year", FixedAsset.disposal_date) == fiscal_year)
        )
        assets = list(result.scalars().all())
        
        disposals = []
        total_gains = Decimal("0")
        total_losses = Decimal("0")
        
        for asset in assets:
            gain = asset.capital_gain_on_disposal or Decimal("0")
            disposals.append({
                "asset_code": asset.asset_code,
                "name": asset.name,
                "disposal_date": asset.disposal_date.isoformat() if asset.disposal_date else None,
                "disposal_type": asset.disposal_type.value if asset.disposal_type else None,
                "proceeds": float(asset.disposal_amount or 0),
                "nbv_at_disposal": float(asset.acquisition_cost - asset.accumulated_depreciation),
                "gain_loss": float(gain),
            })
            
            if gain > 0:
                total_gains += gain
            else:
                total_losses += abs(gain)
        
        net_position = total_gains - total_losses
        
        return {
            "fiscal_year": fiscal_year,
            "disposals": disposals,
            "total_gains": float(total_gains),
            "total_losses": float(total_losses),
            "net_position": float(net_position),
            "tax_treatment": "Capital gains are taxed at the flat CIT rate (30% for large companies) under 2026 law",
        }
    
    async def update_entity_fixed_assets_total(
        self,
        entity_id: uuid.UUID,
    ) -> Decimal:
        """
        Update the entity's total fixed assets value.
        
        Used for Development Levy exemption threshold calculation.
        """
        # Sum all active assets' net book value
        result = await self.db.execute(
            select(func.sum(
                FixedAsset.acquisition_cost - FixedAsset.accumulated_depreciation
            ))
            .where(FixedAsset.entity_id == entity_id)
            .where(FixedAsset.status == AssetStatus.ACTIVE)
        )
        total_nbv = result.scalar() or Decimal("0")
        
        # Update entity
        entity_result = await self.db.execute(
            select(BusinessEntity).where(BusinessEntity.id == entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        
        if entity:
            entity.fixed_assets_value = total_nbv
            
            # Check Development Levy exemption
            turnover = entity.annual_turnover or Decimal("0")
            entity.is_development_levy_exempt = (
                turnover <= Decimal("100000000") and
                total_nbv <= Decimal("250000000")
            )
            
            await self.db.commit()
        
        return total_nbv
