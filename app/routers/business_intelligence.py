"""
API Router for Business Intelligence & Inventory Management

Provides endpoints for:
- BIK (Benefit-in-Kind) calculations
- NIBSS Pension payment file generation
- Growth Radar & tax threshold alerts
- Inventory write-off with VAT adjustment
- Multi-location inventory transfers
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_entity_id
from app.models.user import User


router = APIRouter(prefix="/api/v1/business-intelligence", tags=["Business Intelligence"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

# BIK Schemas
class VehicleBenefit(BaseModel):
    type: str = Field(default="saloon_car", description="Vehicle type")
    cost: float = Field(..., description="Vehicle cost in Naira")
    months: int = Field(default=12, description="Months vehicle was available")
    private_use: float = Field(default=100, description="Private use percentage")
    has_driver: bool = Field(default=False, description="Company provides driver")


class AccommodationBenefit(BaseModel):
    type: str = Field(default="rented_unfurnished", description="Accommodation type")
    rent: Optional[float] = Field(None, description="Annual rent paid by employer")
    months: int = Field(default=12, description="Months occupied")
    furnished: bool = Field(default=False, description="Is furnished")
    furniture_value: Optional[float] = Field(None, description="Furniture value if separate")


class UtilityBenefit(BaseModel):
    type: str = Field(default="electricity", description="Utility type")
    amount: float = Field(..., description="Annual amount")
    months: int = Field(default=12, description="Months provided")


class DomesticStaffBenefit(BaseModel):
    count: int = Field(default=1, description="Number of staff")
    months: int = Field(default=12, description="Months employed")


class GeneratorBenefit(BaseModel):
    cost: float = Field(..., description="Generator cost")
    months: int = Field(default=12, description="Months available")
    fuel: Optional[float] = Field(None, description="Annual fuel allowance")


class BIKCalculationRequest(BaseModel):
    employee_id: UUID
    tax_year: int = Field(default=2026)
    vehicle: Optional[VehicleBenefit] = None
    accommodation: Optional[AccommodationBenefit] = None
    utilities: Optional[List[UtilityBenefit]] = None
    domestic_staff: Optional[DomesticStaffBenefit] = None
    generator: Optional[GeneratorBenefit] = None


# Pension NIBSS Schemas
class PensionPaymentRequest(BaseModel):
    payroll_period: date
    originator_bank_code: str = Field(..., description="Employer's bank code")
    originator_account: str = Field(..., description="Employer's bank account")
    payment_date: Optional[date] = None


# Write-off Schemas
class WriteOffItemRequest(BaseModel):
    item_id: UUID
    quantity: float
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None


class WriteOffRequest(BaseModel):
    reason: str = Field(..., description="expired, damaged, obsolete, theft, spoilage, etc.")
    items: List[WriteOffItemRequest]
    justification: str
    supporting_documents: Optional[List[str]] = None


# Transfer Schemas
class TransferItemRequest(BaseModel):
    item_id: UUID
    quantity: float
    batch_number: Optional[str] = None


class TransferRequest(BaseModel):
    transfer_type: str = Field(default="warehouse_to_warehouse")
    source_location_id: UUID
    source_location_name: str
    source_state: Optional[str] = None
    destination_location_id: UUID
    destination_location_name: str
    destination_state: Optional[str] = None
    items: List[TransferItemRequest]
    notes: Optional[str] = None


class ReceiveTransferRequest(BaseModel):
    received_quantities: List[Dict[str, Any]]


# ============================================================================
# BIK Endpoints
# ============================================================================

@router.post("/bik/calculate")
async def calculate_bik(
    request: BIKCalculationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """
    Calculate Benefit-in-Kind for an employee.
    
    Calculates taxable values for executive compensation benefits
    including vehicles, accommodation, utilities, and domestic staff.
    """
    from app.services.bik_automator import bik_automator_service
    
    # Build benefits dictionary
    benefits = {}
    if request.vehicle:
        benefits["vehicle"] = request.vehicle.model_dump()
    if request.accommodation:
        benefits["accommodation"] = request.accommodation.model_dump()
    if request.utilities:
        benefits["utilities"] = [u.model_dump() for u in request.utilities]
    if request.domestic_staff:
        benefits["domestic_staff"] = request.domestic_staff.model_dump()
    if request.generator:
        benefits["generator"] = request.generator.model_dump()
    
    try:
        summary = await bik_automator_service.generate_employee_bik_summary(
            db=db,
            employee_id=request.employee_id,
            tax_year=request.tax_year,
            benefits=benefits,
        )
        return bik_automator_service.bik_summary_to_dict(summary)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/bik/rates")
async def get_bik_rates(
    current_user: User = Depends(get_current_user),
):
    """Get current BIK rates for 2026."""
    from app.services.bik_automator import BIK_RATES_2026, BIK_CAPS
    
    return {
        "tax_year": 2026,
        "rates": {
            "vehicle": {k.value: float(v) for k, v in BIK_RATES_2026["vehicle"].items()},
            "accommodation": {k.value: float(v) for k, v in BIK_RATES_2026["accommodation"].items()},
            "driver_annual": float(BIK_RATES_2026["driver"]),
            "domestic_staff_annual": float(BIK_RATES_2026["domestic_staff"]),
            "furniture_rate": float(BIK_RATES_2026["furniture"]),
            "generator_rate": float(BIK_RATES_2026["generator"]),
        },
        "caps": {k: float(v) for k, v in BIK_CAPS.items()},
    }


# ============================================================================
# NIBSS Pension Endpoints
# ============================================================================

@router.post("/pension/generate-nibss-file")
async def generate_nibss_pension_file(
    request: PensionPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """
    Generate NIBSS-compliant XML file for bulk pension payments.
    
    Creates a bank-ready XML file that can be submitted to NIBSS
    for processing pension payments to all PFAs.
    """
    from app.services.nibss_pension import nibss_pension_service
    
    try:
        payment_file = await nibss_pension_service.generate_pension_payment_file(
            db=db,
            entity_id=entity_id,
            payroll_period=request.payroll_period,
            originator_bank_code=request.originator_bank_code,
            originator_account=request.originator_account,
            payment_date=request.payment_date,
        )
        
        return {
            "summary": nibss_pension_service.generate_summary_report(payment_file),
            "xml_content": payment_file.xml_content,
            "file_reference": payment_file.file_reference,
            "download_filename": f"NIBSS_PENSION_{payment_file.file_reference}.xml",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/pension/generate-nibss-file/download")
async def download_nibss_pension_file(
    request: PensionPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """Download NIBSS pension file as XML."""
    from app.services.nibss_pension import nibss_pension_service
    
    try:
        payment_file = await nibss_pension_service.generate_pension_payment_file(
            db=db,
            entity_id=entity_id,
            payroll_period=request.payroll_period,
            originator_bank_code=request.originator_bank_code,
            originator_account=request.originator_account,
            payment_date=request.payment_date,
        )
        
        return Response(
            content=payment_file.xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="NIBSS_PENSION_{payment_file.file_reference}.xml"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/pension/pfa-list")
async def get_pfa_list(
    current_user: User = Depends(get_current_user),
):
    """Get list of licensed Pension Fund Administrators."""
    from app.services.nibss_pension import PFACode, PFA_BANK_DETAILS
    
    pfas = []
    for pfa_code in PFACode:
        details = PFA_BANK_DETAILS.get(pfa_code, {})
        pfas.append({
            "code": pfa_code.value,
            "name": details.get("name", f"{pfa_code.value} PFA"),
            "bank_code": details.get("bank_code"),
            "pfc": details.get("pfc"),
        })
    
    return {"pfas": pfas, "count": len(pfas)}


@router.post("/pension/validate-rsapin")
async def validate_rsapin(
    rsapin: str = Query(..., description="RSA PIN to validate"),
    current_user: User = Depends(get_current_user),
):
    """Validate Nigerian RSA PIN format."""
    from app.services.nibss_pension import nibss_pension_service
    
    is_valid, error = nibss_pension_service.validate_rsapin(rsapin)
    return {
        "rsapin": rsapin,
        "is_valid": is_valid,
        "error": error,
        "format": "PEN + 12 digits (e.g., PEN123456789012)",
    }


# ============================================================================
# Growth Radar Endpoints
# ============================================================================

@router.get("/growth-radar")
async def get_growth_radar(
    fiscal_year: int = Query(default=2026, description="Fiscal year for analysis"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """
    Get comprehensive Growth Radar analysis.
    
    Provides tax threshold monitoring, growth projections,
    and transition planning recommendations.
    """
    from app.services.growth_radar import growth_radar_service
    
    try:
        summary = await growth_radar_service.generate_growth_radar_summary(
            db=db,
            entity_id=entity_id,
            fiscal_year=fiscal_year,
        )
        return growth_radar_service.summary_to_dict(summary)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/growth-radar/thresholds")
async def get_tax_thresholds(
    current_user: User = Depends(get_current_user),
):
    """Get 2026 Nigerian tax thresholds."""
    from app.services.growth_radar import TAX_THRESHOLDS_2026, TAX_RATES_2026, ThresholdType, TaxBracket
    
    return {
        "tax_year": 2026,
        "thresholds": {
            t.value: {
                "amount": float(v),
                "description": {
                    ThresholdType.CIT_SMALL_MEDIUM: "CIT liability begins (0% -> 20%)",
                    ThresholdType.CIT_MEDIUM_LARGE: "Higher CIT + Dev Levy + TET (20% -> 30%)",
                    ThresholdType.VAT_THRESHOLD: "VAT registration mandatory",
                }.get(t, "Tax threshold"),
            }
            for t, v in TAX_THRESHOLDS_2026.items()
        },
        "brackets": {
            b.value: {
                "cit": float(rates["cit"]),
                "dev_levy": float(rates["dev_levy"]),
                "tet": float(rates["tet"]),
            }
            for b, rates in TAX_RATES_2026.items()
        },
    }


@router.get("/growth-radar/projection")
async def get_growth_projection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """Get growth projection based on historical data."""
    from app.services.growth_radar import growth_radar_service
    
    projection = await growth_radar_service.calculate_growth_projection(
        db=db,
        entity_id=entity_id,
    )
    
    return {
        "current_monthly_revenue": float(projection.current_monthly_revenue),
        "average_monthly_growth_rate": float(projection.average_monthly_growth_rate),
        "projected_annual_revenue": float(projection.projected_annual_revenue),
        "months_to_small_threshold": projection.months_to_small_threshold,
        "months_to_medium_threshold": projection.months_to_medium_threshold,
        "projected_tax_bracket": projection.projected_tax_bracket.value,
        "projected_taxes": {
            "cit": float(projection.projected_cit),
            "dev_levy": float(projection.projected_dev_levy),
            "tet": float(projection.projected_tet),
            "total": float(projection.projected_total_tax),
        },
        "confidence": projection.confidence_level,
    }


# ============================================================================
# Inventory Write-off Endpoints
# ============================================================================

@router.post("/inventory/write-off")
async def create_write_off_request(
    request: WriteOffRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """
    Create inventory write-off request.
    
    Handles expired/damaged goods write-off with automatic
    VAT input adjustment documentation.
    """
    from app.services.inventory_management import (
        inventory_write_off_service,
        WriteOffReason,
    )
    
    try:
        reason = WriteOffReason(request.reason)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid write-off reason: {request.reason}"
        )
    
    items = [
        {
            "item_id": item.item_id,
            "quantity": item.quantity,
            "batch_number": item.batch_number,
            "expiry_date": item.expiry_date,
            "location_id": item.location_id,
            "location_name": item.location_name,
        }
        for item in request.items
    ]
    
    try:
        write_off = await inventory_write_off_service.create_write_off_request(
            db=db,
            entity_id=entity_id,
            reason=reason,
            items=items,
            justification=request.justification,
            requested_by=current_user.id,
            supporting_documents=request.supporting_documents,
        )
        return inventory_write_off_service.write_off_request_to_dict(write_off)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/inventory/write-off/reasons")
async def get_write_off_reasons(
    current_user: User = Depends(get_current_user),
):
    """Get available write-off reasons."""
    from app.services.inventory_management import WriteOffReason
    
    return {
        "reasons": [
            {
                "code": r.value,
                "name": r.value.replace("_", " ").title(),
                "vat_adjustment": r in [
                    WriteOffReason.EXPIRED,
                    WriteOffReason.DAMAGED,
                    WriteOffReason.THEFT,
                    WriteOffReason.SPOILAGE,
                    WriteOffReason.SAMPLE_GIVEN,
                ],
            }
            for r in WriteOffReason
        ]
    }


@router.post("/inventory/write-off/{write_off_id}/vat-adjustment-doc")
async def generate_vat_adjustment_document(
    write_off_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """Generate VAT input adjustment documentation for FIRS."""
    from app.services.inventory_management import inventory_write_off_service
    from app.models.entity import BusinessEntity
    
    # Get entity details
    from sqlalchemy import select
    result = await db.execute(
        select(BusinessEntity).where(BusinessEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # In a real implementation, you'd fetch the write-off from database
    # For now, return a sample structure
    return {
        "message": "VAT adjustment document would be generated here",
        "entity_tin": entity.tin,
        "entity_name": entity.name,
        "write_off_id": str(write_off_id),
        "documentation_required": [
            "Stock count sheet",
            "Write-off approval form",
            "Photos of damaged/expired goods",
            "Certificate of destruction (if applicable)",
        ],
    }


# ============================================================================
# Inventory Transfer Endpoints
# ============================================================================

@router.post("/inventory/transfer")
async def create_transfer(
    request: TransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id),
):
    """
    Create inventory transfer between locations.
    
    Supports interstate transfers with automatic levy calculation.
    """
    from app.services.inventory_management import (
        inventory_transfer_service,
        TransferType,
        NigerianState,
    )
    
    try:
        transfer_type = TransferType(request.transfer_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transfer type: {request.transfer_type}"
        )
    
    source_state = None
    dest_state = None
    if request.source_state:
        try:
            source_state = NigerianState(request.source_state)
        except ValueError:
            pass
    if request.destination_state:
        try:
            dest_state = NigerianState(request.destination_state)
        except ValueError:
            pass
    
    items = [
        {
            "item_id": item.item_id,
            "quantity": item.quantity,
            "batch_number": item.batch_number,
        }
        for item in request.items
    ]
    
    try:
        transfer = await inventory_transfer_service.create_transfer(
            db=db,
            entity_id=entity_id,
            transfer_type=transfer_type,
            source_location_id=request.source_location_id,
            source_location_name=request.source_location_name,
            source_state=source_state,
            destination_location_id=request.destination_location_id,
            destination_location_name=request.destination_location_name,
            destination_state=dest_state,
            items=items,
            initiated_by=current_user.id,
            notes=request.notes,
        )
        return inventory_transfer_service.transfer_to_dict(transfer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/inventory/transfer/states")
async def get_nigerian_states(
    current_user: User = Depends(get_current_user),
):
    """Get list of Nigerian states for transfers."""
    from app.services.inventory_management import NigerianState, INTERSTATE_LEVY_RATE
    
    return {
        "states": [{"code": s.name, "name": s.value} for s in NigerianState],
        "interstate_levy_rate": float(INTERSTATE_LEVY_RATE),
        "levy_description": "0.5% levy on interstate movement of certain goods",
    }


@router.get("/inventory/transfer/types")
async def get_transfer_types(
    current_user: User = Depends(get_current_user),
):
    """Get available transfer types."""
    from app.services.inventory_management import TransferType
    
    return {
        "types": [
            {
                "code": t.value,
                "name": t.value.replace("_", " ").title(),
            }
            for t in TransferType
        ]
    }
