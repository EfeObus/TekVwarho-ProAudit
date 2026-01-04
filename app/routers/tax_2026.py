"""
TekVwarho ProAudit - 2026 Tax Reform Router

API endpoints for the 2026 Nigerian Tax Administration Act compliance:
- 72-Hour Buyer Review Module
- Advanced Input VAT Recovery
- Development Levy (4%)
- PIT Relief Documents
- Business Type Toggle (PIT vs CIT)
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.entity import BusinessType
from app.models.invoice import BuyerStatus
from app.models.tax_2026 import VATRecoveryType, ReliefType, ReliefStatus, CreditNoteStatus
from app.services.buyer_review_service import BuyerReviewService
from app.services.vat_recovery_service import VATRecoveryService
from app.services.development_levy_service import DevelopmentLevyService
from app.services.pit_relief_service import PITReliefService
from app.services.entity_service import EntityService
from app.services.tin_validation_service import (
    TINValidationService,
    TINEntityType,
    TINValidationStatus,
    TINValidationResult,
)
from app.schemas.auth import MessageResponse


router = APIRouter()


# ===========================================
# SCHEMAS
# ===========================================

# Buyer Review Schemas
class BuyerResponseRequest(BaseModel):
    """Request to process buyer response."""
    accepted: bool
    rejection_reason: Optional[str] = None


class InvoiceBuyerStatusResponse(BaseModel):
    """Invoice buyer status response."""
    invoice_id: UUID
    invoice_number: str
    buyer_status: str
    dispute_deadline: Optional[str] = None
    buyer_response_at: Optional[str] = None
    credit_note_id: Optional[UUID] = None


class CreditNoteResponse(BaseModel):
    """Credit note response."""
    id: UUID
    credit_note_number: str
    original_invoice_id: Optional[UUID]
    issue_date: date
    reason: str
    subtotal: float
    vat_amount: float
    total_amount: float
    status: str
    nrs_irn: Optional[str] = None


# VAT Recovery Schemas
class VATRecoveryRequest(BaseModel):
    """Request to record VAT recovery."""
    transaction_id: Optional[UUID] = None
    vat_amount: Decimal = Field(..., gt=0)
    recovery_type: VATRecoveryType
    vendor_irn: Optional[str] = None
    transaction_date: date
    description: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_tin: Optional[str] = None


class VATRecoveryResponse(BaseModel):
    """VAT recovery record response."""
    id: UUID
    vat_amount: float
    recovery_type: str
    is_recoverable: bool
    non_recovery_reason: Optional[str]
    vendor_irn: Optional[str]
    has_valid_irn: bool
    transaction_date: date


class VATRecoverySummaryResponse(BaseModel):
    """VAT recovery summary response."""
    year: int
    month: int
    total_recoverable: float
    total_non_recoverable: float
    total_input_vat: float
    by_type: dict


# Development Levy Schemas
class DevelopmentLevyRequest(BaseModel):
    """Request to calculate Development Levy."""
    fiscal_year: int
    assessable_profit: Decimal = Field(..., ge=0)
    turnover: Optional[Decimal] = None
    fixed_assets: Optional[Decimal] = None


class DevelopmentLevyResponse(BaseModel):
    """Development Levy calculation response."""
    fiscal_year: int
    assessable_profit: float
    levy_rate_percentage: str
    levy_amount: float
    is_exempt: bool
    exemption_reason: Optional[str]


# PIT Relief Schemas
class PITReliefRequest(BaseModel):
    """Request to create PIT relief document."""
    relief_type: ReliefType
    fiscal_year: int
    claimed_amount: Decimal = Field(..., ge=0)
    annual_rent: Optional[Decimal] = None  # Required for RENT type


class PITReliefResponse(BaseModel):
    """PIT relief document response."""
    id: UUID
    relief_type: str
    fiscal_year: int
    claimed_amount: float
    allowed_amount: Optional[float]
    status: str
    document_url: Optional[str]
    is_verified: bool


class PITReliefVerifyRequest(BaseModel):
    """Request to verify a relief document."""
    approved: bool
    notes: Optional[str] = None


# Business Type Schemas
class BusinessTypeUpdateRequest(BaseModel):
    """Request to update business type."""
    business_type: BusinessType
    annual_turnover: Optional[Decimal] = None
    fixed_assets_value: Optional[Decimal] = None


class BusinessTypeResponse(BaseModel):
    """Business type response with tax implications."""
    entity_id: UUID
    entity_name: str
    business_type: str
    tax_regime: str  # "PIT" or "CIT"
    annual_turnover: Optional[float]
    fixed_assets_value: Optional[float]
    is_development_levy_exempt: bool
    tax_implications: dict


# ===========================================
# HELPER FUNCTIONS
# ===========================================

async def verify_entity_access(
    entity_id: UUID,
    current_user: User,
    db: AsyncSession,
):
    """Verify user has access to entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )
    
    # Check user has access
    has_access = any(
        access.entity_id == entity_id
        for access in current_user.entity_access
    )
    
    if not has_access and current_user.organization_id != entity.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this entity",
        )
    
    return entity


# ===========================================
# BUYER REVIEW ENDPOINTS (72-Hour Window)
# ===========================================

@router.get(
    "/{entity_id}/buyer-review/pending",
    response_model=List[InvoiceBuyerStatusResponse],
    summary="Get invoices pending buyer review",
    tags=["2026 Reform - Buyer Review"],
)
async def get_pending_reviews(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get all invoices awaiting buyer confirmation within 72-hour window."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    invoices = await service.get_invoices_pending_review(entity_id)
    
    return [
        InvoiceBuyerStatusResponse(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            buyer_status=inv.buyer_status.value if inv.buyer_status else "unknown",
            dispute_deadline=inv.dispute_deadline.isoformat() if inv.dispute_deadline else None,
            buyer_response_at=inv.buyer_response_at.isoformat() if inv.buyer_response_at else None,
            credit_note_id=inv.credit_note_id,
        )
        for inv in invoices
    ]


@router.get(
    "/{entity_id}/buyer-review/overdue",
    response_model=List[InvoiceBuyerStatusResponse],
    summary="Get overdue buyer reviews",
    tags=["2026 Reform - Buyer Review"],
)
async def get_overdue_reviews(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get invoices where 72-hour review window has expired."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    invoices = await service.get_overdue_reviews(entity_id)
    
    return [
        InvoiceBuyerStatusResponse(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            buyer_status=inv.buyer_status.value if inv.buyer_status else "unknown",
            dispute_deadline=inv.dispute_deadline.isoformat() if inv.dispute_deadline else None,
        )
        for inv in invoices
    ]


@router.get(
    "/{entity_id}/buyer-review/auto-accepted",
    response_model=List[InvoiceBuyerStatusResponse],
    summary="Get auto-accepted invoices",
    tags=["2026 Reform - Buyer Review"],
)
async def get_auto_accepted_invoices(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get invoices auto-accepted after 72-hour window expired without buyer response."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    invoices = await service.get_auto_accepted_invoices(entity_id)
    
    return [
        InvoiceBuyerStatusResponse(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            buyer_status=inv.buyer_status.value if inv.buyer_status else "unknown",
            dispute_deadline=inv.dispute_deadline.isoformat() if inv.dispute_deadline else None,
            buyer_response_at=inv.buyer_response_at.isoformat() if inv.buyer_response_at else None,
        )
        for inv in invoices
    ]


@router.post(
    "/{entity_id}/buyer-review/{invoice_id}/respond",
    summary="Process buyer response",
    tags=["2026 Reform - Buyer Review"],
)
async def process_buyer_response(
    entity_id: UUID,
    invoice_id: UUID,
    request: BuyerResponseRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Process buyer's acceptance or rejection of invoice.
    
    If rejected, automatically creates a Credit Note.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    
    try:
        result = await service.process_buyer_response(
            invoice_id=invoice_id,
            accepted=request.accepted,
            rejection_reason=request.rejection_reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{entity_id}/buyer-review/poll-nrs",
    summary="Poll NRS for buyer responses",
    tags=["2026 Reform - Buyer Review"],
)
async def poll_nrs_responses(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Poll NRS API for buyer responses on pending invoices."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    results = await service.poll_nrs_for_responses(entity_id)
    
    return {
        "processed": len(results),
        "results": results,
    }


@router.get(
    "/{entity_id}/credit-notes",
    response_model=List[CreditNoteResponse],
    summary="Get credit notes",
    tags=["2026 Reform - Buyer Review"],
)
async def get_credit_notes(
    entity_id: UUID,
    status: Optional[CreditNoteStatus] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get all credit notes for an entity."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    notes = await service.get_credit_notes(entity_id, status)
    
    return [
        CreditNoteResponse(
            id=note.id,
            credit_note_number=note.credit_note_number,
            original_invoice_id=note.original_invoice_id,
            issue_date=note.issue_date,
            reason=note.reason,
            subtotal=float(note.subtotal),
            vat_amount=float(note.vat_amount),
            total_amount=float(note.total_amount),
            status=note.status.value,
            nrs_irn=note.nrs_irn,
        )
        for note in notes
    ]


@router.post(
    "/{entity_id}/credit-notes/{credit_note_id}/submit-nrs",
    summary="Submit credit note to NRS",
    tags=["2026 Reform - Buyer Review"],
)
async def submit_credit_note_to_nrs(
    entity_id: UUID,
    credit_note_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Submit a credit note to NRS for processing."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = BuyerReviewService(db)
    
    try:
        result = await service.submit_credit_note_to_nrs(credit_note_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================
# VAT RECOVERY ENDPOINTS (Advanced 2026)
# ===========================================

@router.post(
    "/{entity_id}/vat-recovery",
    response_model=VATRecoveryResponse,
    summary="Record VAT recovery",
    tags=["2026 Reform - VAT Recovery"],
)
async def record_vat_recovery(
    entity_id: UUID,
    request: VATRecoveryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record an input VAT recovery entry.
    
    Under 2026 Act:
    - Services VAT is now recoverable
    - Capital assets VAT is now recoverable
    - MUST have valid vendor IRN for recovery
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = VATRecoveryService(db)
    record = await service.record_vat_recovery(
        entity_id=entity_id,
        transaction_id=request.transaction_id,
        vat_amount=request.vat_amount,
        recovery_type=request.recovery_type,
        vendor_irn=request.vendor_irn,
        transaction_date=request.transaction_date,
        description=request.description,
        vendor_name=request.vendor_name,
        vendor_tin=request.vendor_tin,
    )
    
    return VATRecoveryResponse(
        id=record.id,
        vat_amount=float(record.vat_amount),
        recovery_type=record.recovery_type.value,
        is_recoverable=record.is_recoverable,
        non_recovery_reason=record.non_recovery_reason,
        vendor_irn=record.vendor_irn,
        has_valid_irn=record.has_valid_irn,
        transaction_date=record.transaction_date,
    )


@router.get(
    "/{entity_id}/vat-recovery/summary/{year}/{month}",
    response_model=VATRecoverySummaryResponse,
    summary="Get VAT recovery summary",
    tags=["2026 Reform - VAT Recovery"],
)
async def get_vat_recovery_summary(
    entity_id: UUID,
    year: int = Path(..., ge=2020, le=2100),
    month: int = Path(..., ge=1, le=12),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get VAT recovery summary for a period.
    
    Shows breakdown by type (stock, services, capital) and
    recoverable vs non-recoverable amounts.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = VATRecoveryService(db)
    summary = await service.get_recovery_summary(entity_id, year, month)
    
    return VATRecoverySummaryResponse(**summary)


@router.get(
    "/{entity_id}/vat-recovery/non-recoverable",
    summary="Get non-recoverable VAT records",
    tags=["2026 Reform - VAT Recovery"],
)
async def get_non_recoverable_vat(
    entity_id: UUID,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get all VAT flagged as non-recoverable (missing vendor IRN)."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = VATRecoveryService(db)
    records = await service.get_non_recoverable_records(entity_id, year, month)
    
    return [
        VATRecoveryResponse(
            id=r.id,
            vat_amount=float(r.vat_amount),
            recovery_type=r.recovery_type.value,
            is_recoverable=r.is_recoverable,
            non_recovery_reason=r.non_recovery_reason,
            vendor_irn=r.vendor_irn,
            has_valid_irn=r.has_valid_irn,
            transaction_date=r.transaction_date,
        )
        for r in records
    ]


@router.get(
    "/{entity_id}/vat-recovery/vendors-without-irn/{year}",
    summary="Get vendors without NRS e-invoices",
    tags=["2026 Reform - VAT Recovery"],
)
async def get_vendors_without_irn(
    entity_id: UUID,
    year: int = Path(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get list of vendors who didn't provide NRS e-invoices.
    
    Helps identify non-compliant vendors causing lost VAT recovery.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = VATRecoveryService(db)
    vendors = await service.get_vendors_without_irn(entity_id, year)
    
    return {
        "year": year,
        "vendors": vendors,
        "recommendation": "Request NRS-compliant e-invoices from these vendors to recover input VAT",
    }


# ===========================================
# ZERO-RATED VAT ENDPOINTS (2026 Reform)
# ===========================================

class ZeroRatedVATSaleRequest(BaseModel):
    """Request to record zero-rated sale."""
    sale_amount: float = Field(..., gt=0, description="Sale amount")
    category: str = Field(..., description="Zero-rated category")
    transaction_date: date
    description: Optional[str] = None


class ZeroRatedVATInputRequest(BaseModel):
    """Request to record input VAT for refund."""
    purchase_amount: float = Field(..., gt=0)
    vat_amount: float = Field(..., gt=0)
    transaction_date: date
    vendor_tin: str
    vendor_irn: Optional[str] = None
    description: Optional[str] = None


@router.get(
    "/zero-rated/categories",
    summary="Get zero-rated VAT categories",
    tags=["2026 Reform - Zero-Rated VAT"],
)
async def get_zero_rated_categories(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get list of zero-rated VAT categories.
    
    Zero-rated supplies have 0% VAT but allow input VAT refund claims.
    """
    from app.services.tax_calculators.minimum_etr_cgt_service import ZeroRatedVATTracker
    
    return {
        "categories": ZeroRatedVATTracker.ZERO_RATED_CATEGORIES,
        "note": "Zero-rated supplies allow sellers to claim input VAT refunds",
    }


@router.post(
    "/{entity_id}/zero-rated/record-sale",
    summary="Record zero-rated sale",
    tags=["2026 Reform - Zero-Rated VAT"],
)
async def record_zero_rated_sale(
    entity_id: UUID,
    request: ZeroRatedVATSaleRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record a zero-rated sale for VAT refund tracking.
    
    Zero-rated supplies (basic food, education, healthcare, exports)
    have 0% VAT but allow input VAT refund claims.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.tax_calculators.minimum_etr_cgt_service import ZeroRatedVATTracker
    
    tracker = ZeroRatedVATTracker()
    
    record = tracker.record_zero_rated_sale(
        sale_amount=Decimal(str(request.sale_amount)),
        category=request.category,
        date=request.transaction_date,
        description=request.description or "",
    )
    
    return {
        "entity_id": str(entity_id),
        **{k: float(v) if isinstance(v, Decimal) else v for k, v in record.items()},
    }


@router.post(
    "/{entity_id}/zero-rated/record-input",
    summary="Record input VAT for refund",
    tags=["2026 Reform - Zero-Rated VAT"],
)
async def record_zero_rated_input(
    entity_id: UUID,
    request: ZeroRatedVATInputRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record input VAT paid for potential refund.
    
    Only purchases with valid vendor IRN qualify for refund.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.tax_calculators.minimum_etr_cgt_service import ZeroRatedVATTracker
    
    tracker = ZeroRatedVATTracker()
    
    record = tracker.record_input_vat(
        purchase_amount=Decimal(str(request.purchase_amount)),
        vat_amount=Decimal(str(request.vat_amount)),
        date=request.transaction_date,
        vendor_tin=request.vendor_tin,
        vendor_irn=request.vendor_irn,
        description=request.description or "",
    )
    
    return {
        "entity_id": str(entity_id),
        **{k: float(v) if isinstance(v, Decimal) else v for k, v in record.items()},
    }


@router.get(
    "/{entity_id}/zero-rated/refund-claim",
    summary="Calculate VAT refund claim",
    tags=["2026 Reform - Zero-Rated VAT"],
)
async def calculate_refund_claim(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate VAT refund claim for zero-rated supplier.
    
    Zero-rated suppliers can claim back input VAT paid on purchases.
    Only purchases with valid NRS IRN are eligible for refund.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.tax_calculators.minimum_etr_cgt_service import ZeroRatedVATTracker
    
    tracker = ZeroRatedVATTracker()
    claim = tracker.calculate_refund_claim()
    
    return {
        "entity_id": str(entity_id),
        **claim,
    }


# ===========================================
# MINIMUM ETR ENDPOINTS (15% Large Companies)
# ===========================================

class MinimumETRRequest(BaseModel):
    """Request for Minimum ETR calculation."""
    annual_turnover: float = Field(..., gt=0, description="Annual turnover in NGN")
    assessable_profit: float = Field(..., ge=0, description="Assessable profit in NGN")
    regular_tax_paid: float = Field(..., ge=0, description="Regular CIT/taxes already calculated")
    is_mne_constituent: bool = Field(default=False, description="Part of MNE group with €750M+ revenue")
    mne_group_revenue_eur: Optional[float] = Field(None, description="MNE group revenue in EUR (if applicable)")


@router.get(
    "/minimum-etr/thresholds",
    summary="Get Minimum ETR thresholds",
    tags=["2026 Reform - Minimum ETR"],
)
async def get_minimum_etr_thresholds(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get Minimum ETR thresholds and applicability criteria.
    
    Under Section 57 of the 2026 NTAA:
    - Companies with turnover >= ₦50 billion are subject to 15% minimum ETR
    - MNE constituents with group revenue >= €750 million are also subject
    """
    from app.services.tax_calculators.minimum_etr_cgt_service import (
        MINIMUM_ETR_RATE, TURNOVER_THRESHOLD_NGN, MNE_REVENUE_THRESHOLD_EUR
    )
    
    return {
        "minimum_etr_rate": "15%",
        "turnover_threshold_ngn": float(TURNOVER_THRESHOLD_NGN),
        "turnover_threshold_formatted": "₦50,000,000,000 (₦50 billion)",
        "mne_revenue_threshold_eur": float(MNE_REVENUE_THRESHOLD_EUR),
        "mne_revenue_threshold_formatted": "€750,000,000 (€750 million)",
        "applicability": [
            "Companies with annual turnover >= ₦50 billion",
            "Constituents of MNE groups with aggregate revenue >= €750 million",
        ],
        "compliance_note": "If a company's effective tax rate is below 15%, a top-up tax is required to reach 15%",
        "legislation": "Section 57, Nigeria Tax Administration Act 2026",
    }


@router.post(
    "/minimum-etr/check-applicability",
    summary="Check if subject to Minimum ETR",
    tags=["2026 Reform - Minimum ETR"],
)
async def check_minimum_etr_applicability(
    annual_turnover: float = Query(..., gt=0, description="Annual turnover in NGN"),
    is_mne_constituent: bool = Query(default=False, description="Part of MNE group"),
    mne_group_revenue_eur: Optional[float] = Query(None, description="MNE group revenue in EUR"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Check if a company is subject to Minimum ETR without full calculation.
    
    Quick check based on turnover and MNE status.
    """
    from app.services.tax_calculators.minimum_etr_cgt_service import MinimumETRCalculator
    
    calculator = MinimumETRCalculator()
    is_subject, reason = calculator.check_minimum_etr_applicability(
        annual_turnover=Decimal(str(annual_turnover)),
        is_mne_constituent=is_mne_constituent,
        mne_group_revenue_eur=Decimal(str(mne_group_revenue_eur)) if mne_group_revenue_eur else None,
    )
    
    return {
        "is_subject_to_minimum_etr": is_subject,
        "reason": reason,
        "annual_turnover": annual_turnover,
        "threshold": 50_000_000_000,
    }


@router.post(
    "/{entity_id}/minimum-etr/calculate",
    summary="Calculate Minimum ETR and top-up tax",
    tags=["2026 Reform - Minimum ETR"],
)
async def calculate_minimum_etr(
    entity_id: UUID,
    request: MinimumETRRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate Minimum ETR and any required top-up tax.
    
    For companies subject to the 15% Minimum ETR rule, this calculates:
    - Current effective tax rate
    - ETR shortfall (if below 15%)
    - Top-up tax required to reach 15%
    
    Top-up tax = (15% × Assessable Profit) - Regular Tax Paid
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.tax_calculators.minimum_etr_cgt_service import MinimumETRCalculator
    
    calculator = MinimumETRCalculator()
    result = calculator.calculate_minimum_etr(
        annual_turnover=Decimal(str(request.annual_turnover)),
        assessable_profit=Decimal(str(request.assessable_profit)),
        regular_tax_paid=Decimal(str(request.regular_tax_paid)),
        is_mne_constituent=request.is_mne_constituent,
        mne_group_revenue_eur=Decimal(str(request.mne_group_revenue_eur)) if request.mne_group_revenue_eur else None,
    )
    
    formatted = calculator.format_result(result)
    
    return {
        "entity_id": str(entity_id),
        **formatted,
    }


# ===========================================
# CAPITAL GAINS TAX (CGT) ENDPOINTS (30%)
# ===========================================

class CGTCalculationRequest(BaseModel):
    """Request for CGT calculation."""
    asset_cost: float = Field(..., gt=0, description="Original cost of asset")
    sale_proceeds: float = Field(..., gt=0, description="Sale proceeds")
    annual_turnover: float = Field(..., gt=0, description="Company's annual turnover")
    fixed_assets_value: float = Field(..., ge=0, description="Company's total fixed assets value")
    acquisition_date: Optional[date] = Field(None, description="Date asset was acquired")
    disposal_date: Optional[date] = Field(None, description="Date asset was disposed")
    apply_indexation: bool = Field(default=True, description="Apply inflation indexation allowance")


@router.get(
    "/cgt/thresholds",
    summary="Get CGT thresholds and rates",
    tags=["2026 Reform - Capital Gains Tax"],
)
async def get_cgt_thresholds(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get CGT rates and small company exemption thresholds.
    
    Under the 2026 reform:
    - CGT rate for large companies: 30%
    - Small company exemption: Turnover ≤ ₦100M AND Fixed Assets ≤ ₦250M
    """
    from app.services.tax_calculators.minimum_etr_cgt_service import (
        CGT_RATE_LARGE, SMALL_COMPANY_TURNOVER, SMALL_COMPANY_ASSETS
    )
    
    return {
        "cgt_rate_large_companies": "30%",
        "cgt_rate_numeric": float(CGT_RATE_LARGE),
        "small_company_exemption": {
            "turnover_threshold": float(SMALL_COMPANY_TURNOVER),
            "turnover_formatted": "₦100,000,000 (₦100 million)",
            "assets_threshold": float(SMALL_COMPANY_ASSETS),
            "assets_formatted": "₦250,000,000 (₦250 million)",
            "note": "Both conditions must be met for exemption (turnover ≤ ₦100M AND assets ≤ ₦250M)",
        },
        "indexation_allowance": "Available for assets held > 1 year",
        "legislation": "Capital Gains Tax (Amendment) Act 2026",
    }


@router.post(
    "/cgt/check-exemption",
    summary="Check small company CGT exemption",
    tags=["2026 Reform - Capital Gains Tax"],
)
async def check_cgt_exemption(
    annual_turnover: float = Query(..., gt=0, description="Annual turnover in NGN"),
    fixed_assets_value: float = Query(..., ge=0, description="Fixed assets value in NGN"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Check if company qualifies for small company CGT exemption.
    
    Small companies (turnover ≤ ₦100M AND fixed assets ≤ ₦250M) are exempt.
    """
    from app.services.tax_calculators.minimum_etr_cgt_service import (
        CGTCalculator, CompanyClassification
    )
    
    calculator = CGTCalculator()
    classification = calculator.classify_company(
        annual_turnover=Decimal(str(annual_turnover)),
        fixed_assets_value=Decimal(str(fixed_assets_value)),
    )
    
    is_exempt = classification == CompanyClassification.SMALL
    
    return {
        "is_exempt": is_exempt,
        "company_classification": classification.value,
        "annual_turnover": annual_turnover,
        "fixed_assets_value": fixed_assets_value,
        "exemption_reason": (
            "Small company exemption: Turnover ≤ ₦100M and Fixed Assets ≤ ₦250M"
            if is_exempt
            else "Company exceeds small company thresholds - subject to 30% CGT"
        ),
    }


@router.post(
    "/{entity_id}/cgt/calculate",
    summary="Calculate Capital Gains Tax on asset disposal",
    tags=["2026 Reform - Capital Gains Tax"],
)
async def calculate_cgt(
    entity_id: UUID,
    request: CGTCalculationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate Capital Gains Tax on asset disposal.
    
    For large companies (turnover > ₦100M OR assets > ₦250M):
    - CGT rate is 30% on capital gains
    - Indexation allowance available for inflation adjustment
    
    For small companies:
    - CGT exemption applies (0% rate)
    """
    await verify_entity_access(entity_id, current_user, db)
    
    from app.services.tax_calculators.minimum_etr_cgt_service import CGTCalculator
    
    calculator = CGTCalculator()
    result = calculator.calculate_cgt(
        asset_cost=Decimal(str(request.asset_cost)),
        sale_proceeds=Decimal(str(request.sale_proceeds)),
        annual_turnover=Decimal(str(request.annual_turnover)),
        fixed_assets_value=Decimal(str(request.fixed_assets_value)),
        acquisition_date=request.acquisition_date,
        disposal_date=request.disposal_date,
        apply_indexation=request.apply_indexation,
    )
    
    formatted = calculator.format_result(result)
    
    return {
        "entity_id": str(entity_id),
        **formatted,
    }


# ===========================================
# PROGRESSIVE PAYE ENDPOINTS (2026 Tax Bands)
# ===========================================

class PAYEQuickCalculateRequest(BaseModel):
    """Request for quick PAYE calculation."""
    gross_annual_income: float = Field(..., gt=0, description="Gross annual income in NGN")
    basic_salary: Optional[float] = Field(None, description="Basic salary for NHF calculation")
    pension_percentage: float = Field(default=8.0, ge=0, le=20, description="Pension contribution %")
    other_reliefs: float = Field(default=0, ge=0, description="Other tax reliefs")


@router.get(
    "/paye/bands",
    summary="Get 2026 PAYE tax bands",
    tags=["2026 Reform - Progressive PAYE"],
)
async def get_paye_bands(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the 2026 Nigeria PAYE tax bands.
    
    2026 Tax Reform introduced progressive rates with ₦800,000 tax-free threshold:
    - ₦0 - ₦800,000: 0%
    - ₦800,001 - ₦2,400,000: 15%
    - ₦2,400,001 - ₦4,800,000: 20%
    - ₦4,800,001 - ₦7,200,000: 25%
    - Above ₦7,200,000: 30%
    """
    return {
        "bands": [
            {"lower": 0, "upper": 800_000, "rate": "0%", "description": "Tax-free threshold"},
            {"lower": 800_001, "upper": 2_400_000, "rate": "15%", "description": "First taxable band"},
            {"lower": 2_400_001, "upper": 4_800_000, "rate": "20%", "description": "Second band"},
            {"lower": 4_800_001, "upper": 7_200_000, "rate": "25%", "description": "Third band"},
            {"lower": 7_200_001, "upper": None, "rate": "30%", "description": "Top band (no limit)"},
        ],
        "reliefs": {
            "cra": "₦200,000 + 20% of gross income",
            "pension": "Up to 8% of gross income (employee contribution)",
            "nhf": "2.5% of basic salary",
        },
        "tax_free_threshold": 800_000,
        "tax_free_threshold_formatted": "₦800,000",
        "legislation": "Personal Income Tax (Amendment) Act 2026",
        "effective_date": "January 1, 2026",
    }


@router.post(
    "/paye/quick-calculate",
    summary="Quick PAYE calculation",
    tags=["2026 Reform - Progressive PAYE"],
)
async def quick_calculate_paye(
    request: PAYEQuickCalculateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Quick PAYE calculation with automatic reliefs.
    
    Automatically applies:
    - Consolidated Relief Allowance (CRA): ₦200,000 + 20% of gross
    - Pension contribution relief (default 8%)
    - NHF relief (2.5% of basic salary if provided)
    """
    from app.services.tax_calculators.paye_service import PAYECalculator
    
    calculator = PAYECalculator()
    result = calculator.calculate_paye(
        gross_annual_income=Decimal(str(request.gross_annual_income)),
        basic_salary=Decimal(str(request.basic_salary)) if request.basic_salary else None,
        pension_percentage=Decimal(str(request.pension_percentage)),
        other_reliefs=Decimal(str(request.other_reliefs)),
    )
    
    return result


@router.get(
    "/paye/threshold-check",
    summary="Check if income is below tax-free threshold",
    tags=["2026 Reform - Progressive PAYE"],
)
async def check_paye_threshold(
    gross_annual_income: float = Query(..., gt=0, description="Gross annual income in NGN"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Check if income falls below the ₦800,000 tax-free threshold.
    
    After applying CRA (₦200,000 + 20% of gross), if taxable income
    is below ₦800,000, no PAYE tax is due.
    """
    from app.services.tax_calculators.paye_service import PAYECalculator
    
    calculator = PAYECalculator()
    cra = calculator.calculate_cra(Decimal(str(gross_annual_income)))
    taxable_income = max(Decimal("0"), Decimal(str(gross_annual_income)) - cra)
    
    is_exempt = taxable_income <= Decimal("800000")
    
    return {
        "gross_annual_income": gross_annual_income,
        "consolidated_relief": float(cra),
        "taxable_income": float(taxable_income),
        "tax_free_threshold": 800_000,
        "is_tax_exempt": is_exempt,
        "message": (
            "Income is below ₦800,000 tax-free threshold - no PAYE due"
            if is_exempt
            else f"Taxable income (₦{float(taxable_income):,.2f}) exceeds ₦800,000 threshold"
        ),
        "monthly_gross": gross_annual_income / 12,
    }


@router.get(
    "/paye/monthly-breakdown",
    summary="Get monthly PAYE breakdown",
    tags=["2026 Reform - Progressive PAYE"],
)
async def get_monthly_paye_breakdown(
    gross_annual_income: float = Query(..., gt=0, description="Gross annual income"),
    pension_percentage: float = Query(default=8.0, ge=0, le=20),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calculate PAYE with monthly breakdown for payroll.
    
    Useful for employers to understand monthly deductions.
    """
    from app.services.tax_calculators.paye_service import PAYECalculator
    
    calculator = PAYECalculator()
    result = calculator.calculate_paye(
        gross_annual_income=Decimal(str(gross_annual_income)),
        pension_percentage=Decimal(str(pension_percentage)),
    )
    
    annual_tax = result.get("annual_paye_tax", 0)
    monthly_tax = annual_tax / 12
    monthly_gross = gross_annual_income / 12
    monthly_net = monthly_gross - monthly_tax - (gross_annual_income * pension_percentage / 100 / 12)
    
    return {
        **result,
        "monthly_breakdown": {
            "gross_monthly_salary": round(monthly_gross, 2),
            "monthly_paye_deduction": round(monthly_tax, 2),
            "monthly_pension_deduction": round(gross_annual_income * pension_percentage / 100 / 12, 2),
            "estimated_net_monthly": round(monthly_net, 2),
        },
    }


# ===========================================
# DEVELOPMENT LEVY ENDPOINTS (4% Consolidated)
# ===========================================

@router.post(
    "/{entity_id}/development-levy/calculate",
    response_model=DevelopmentLevyResponse,
    summary="Calculate Development Levy",
    tags=["2026 Reform - Development Levy"],
)
async def calculate_development_levy(
    entity_id: UUID,
    request: DevelopmentLevyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Calculate 4% Development Levy for a fiscal year.
    
    Consolidates TET, Police Fund, and other levies.
    Exempt if: turnover <= ₦100M AND fixed assets <= ₦250M
    """
    await verify_entity_access(entity_id, current_user, db)
    
    service = DevelopmentLevyService(db)
    result = await service.calculate_development_levy(
        entity_id=entity_id,
        fiscal_year=request.fiscal_year,
        assessable_profit=request.assessable_profit,
        turnover=request.turnover,
        fixed_assets=request.fixed_assets,
    )
    
    return DevelopmentLevyResponse(
        fiscal_year=result["fiscal_year"],
        assessable_profit=result["assessable_profit"],
        levy_rate_percentage=result["levy_rate_percentage"],
        levy_amount=result["levy_amount"],
        is_exempt=result["is_exempt"],
        exemption_reason=result["exemption_reason"],
    )


@router.post(
    "/{entity_id}/development-levy/save",
    summary="Save Development Levy record",
    tags=["2026 Reform - Development Levy"],
)
async def save_development_levy(
    entity_id: UUID,
    request: DevelopmentLevyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Save a Development Levy calculation for filing."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = DevelopmentLevyService(db)
    record = await service.save_development_levy_record(
        entity_id=entity_id,
        fiscal_year=request.fiscal_year,
        assessable_profit=request.assessable_profit,
        turnover=request.turnover,
        fixed_assets=request.fixed_assets,
    )
    
    return {
        "id": str(record.id),
        "fiscal_year": record.fiscal_year,
        "levy_amount": float(record.levy_amount),
        "is_exempt": record.is_exempt,
        "is_filed": record.is_filed,
    }


@router.get(
    "/{entity_id}/development-levy/{fiscal_year}",
    summary="Get Development Levy record",
    tags=["2026 Reform - Development Levy"],
)
async def get_development_levy(
    entity_id: UUID,
    fiscal_year: int = Path(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get Development Levy record for a fiscal year."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = DevelopmentLevyService(db)
    record = await service.get_development_levy_record(entity_id, fiscal_year)
    
    if not record:
        raise HTTPException(status_code=404, detail="Development Levy record not found")
    
    return {
        "id": str(record.id),
        "fiscal_year": record.fiscal_year,
        "assessable_profit": float(record.assessable_profit),
        "levy_rate": f"{float(record.levy_rate) * 100}%",
        "levy_amount": float(record.levy_amount),
        "is_exempt": record.is_exempt,
        "exemption_reason": record.exemption_reason,
        "is_filed": record.is_filed,
        "filed_at": record.filed_at.isoformat() if record.filed_at else None,
    }


@router.get(
    "/{entity_id}/development-levy/compare-old-regime",
    summary="Compare to old tax regime",
    tags=["2026 Reform - Development Levy"],
)
async def compare_development_levy_regimes(
    entity_id: UUID,
    assessable_profit: Decimal = Query(..., ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Compare Development Levy to old separate TET and Police Fund."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = DevelopmentLevyService(db)
    comparison = service.compare_to_old_regime(assessable_profit)
    
    return comparison


# ===========================================
# PIT RELIEF ENDPOINTS (CRA Abolished)
# ===========================================

@router.post(
    "/{entity_id}/pit-reliefs",
    response_model=PITReliefResponse,
    summary="Create PIT relief document",
    tags=["2026 Reform - PIT Reliefs"],
)
async def create_pit_relief(
    entity_id: UUID,
    request: PITReliefRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a PIT relief document.
    
    Under 2026 reforms, CRA is abolished. All reliefs require documentary proof.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    # Validate rent relief requires annual_rent
    if request.relief_type == ReliefType.RENT and not request.annual_rent:
        raise HTTPException(
            status_code=400,
            detail="annual_rent is required for Rent Relief type",
        )
    
    service = PITReliefService(db)
    document = await service.create_relief_document(
        entity_id=entity_id,
        user_id=current_user.id,
        relief_type=request.relief_type,
        fiscal_year=request.fiscal_year,
        claimed_amount=request.claimed_amount,
        annual_rent=request.annual_rent,
    )
    
    return PITReliefResponse(
        id=document.id,
        relief_type=document.relief_type.value,
        fiscal_year=document.fiscal_year,
        claimed_amount=float(document.claimed_amount),
        allowed_amount=float(document.allowed_amount) if document.allowed_amount else None,
        status=document.status.value,
        document_url=document.document_url,
        is_verified=document.is_verified,
    )


@router.post(
    "/{entity_id}/pit-reliefs/{relief_id}/upload",
    summary="Upload relief supporting document",
    tags=["2026 Reform - PIT Reliefs"],
)
async def upload_relief_document(
    entity_id: UUID,
    relief_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload supporting document for a PIT relief claim."""
    await verify_entity_access(entity_id, current_user, db)
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: PDF, JPEG, PNG",
        )
    
    content = await file.read()
    
    service = PITReliefService(db)
    document = await service.upload_document(
        relief_id=relief_id,
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    
    return {
        "success": True,
        "document_url": document.document_url,
        "document_name": document.document_name,
    }


@router.post(
    "/{entity_id}/pit-reliefs/{relief_id}/verify",
    summary="Verify relief document",
    tags=["2026 Reform - PIT Reliefs"],
)
async def verify_pit_relief(
    entity_id: UUID,
    relief_id: UUID,
    request: PITReliefVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Verify/approve a PIT relief document."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = PITReliefService(db)
    
    try:
        document = await service.verify_relief(
            relief_id=relief_id,
            verified_by=current_user.id,
            approved=request.approved,
            notes=request.notes,
        )
        
        return {
            "success": True,
            "status": document.status.value,
            "verified_at": document.verified_at.isoformat() if document.verified_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{entity_id}/pit-reliefs/my-reliefs",
    response_model=List[PITReliefResponse],
    summary="Get my relief documents",
    tags=["2026 Reform - PIT Reliefs"],
)
async def get_my_pit_reliefs(
    entity_id: UUID,
    fiscal_year: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get current user's PIT relief documents."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = PITReliefService(db)
    documents = await service.get_user_reliefs(entity_id, current_user.id, fiscal_year)
    
    return [
        PITReliefResponse(
            id=doc.id,
            relief_type=doc.relief_type.value,
            fiscal_year=doc.fiscal_year,
            claimed_amount=float(doc.claimed_amount),
            allowed_amount=float(doc.allowed_amount) if doc.allowed_amount else None,
            status=doc.status.value,
            document_url=doc.document_url,
            is_verified=doc.is_verified,
        )
        for doc in documents
    ]


@router.get(
    "/{entity_id}/pit-reliefs/summary/{fiscal_year}",
    summary="Get relief summary",
    tags=["2026 Reform - PIT Reliefs"],
)
async def get_pit_relief_summary(
    entity_id: UUID,
    fiscal_year: int = Path(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get PIT relief summary for a fiscal year."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = PITReliefService(db)
    summary = await service.get_relief_summary(entity_id, current_user.id, fiscal_year)
    
    return summary


@router.get(
    "/{entity_id}/pit-reliefs/pending-verification",
    response_model=List[PITReliefResponse],
    summary="Get pending verifications",
    tags=["2026 Reform - PIT Reliefs"],
)
async def get_pending_verifications(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get all relief documents pending verification (for admins)."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = PITReliefService(db)
    documents = await service.get_pending_verifications(entity_id)
    
    return [
        PITReliefResponse(
            id=doc.id,
            relief_type=doc.relief_type.value,
            fiscal_year=doc.fiscal_year,
            claimed_amount=float(doc.claimed_amount),
            allowed_amount=float(doc.allowed_amount) if doc.allowed_amount else None,
            status=doc.status.value,
            document_url=doc.document_url,
            is_verified=doc.is_verified,
        )
        for doc in documents
    ]


@router.get(
    "/pit-reliefs/types",
    summary="Get relief types info",
    tags=["2026 Reform - PIT Reliefs"],
)
async def get_relief_types():
    """Get information about available PIT relief types."""
    service = PITReliefService(None)
    return service.get_relief_types_info()


# ===========================================
# BUSINESS TYPE ENDPOINTS (PIT vs CIT Toggle)
# ===========================================

@router.get(
    "/{entity_id}/business-type",
    response_model=BusinessTypeResponse,
    summary="Get business type and tax implications",
    tags=["2026 Reform - Business Type"],
)
async def get_business_type(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get entity's business type and its tax regime implications.
    
    Business Name = Personal Income Tax (PIT)
    Limited Company = Company Income Tax (CIT)
    """
    entity = await verify_entity_access(entity_id, current_user, db)
    
    is_pit = entity.business_type == BusinessType.BUSINESS_NAME
    
    tax_implications = {
        "tax_type": "PIT (Personal Income Tax)" if is_pit else "CIT (Company Income Tax)",
        "rates": (
            "0%/15%/20%/25%/30% progressive bands" if is_pit
            else "0%/20%/30% based on company size"
        ),
        "development_levy": "Not applicable" if is_pit else (
            "Exempt" if entity.is_development_levy_exempt else "4% of assessable profit"
        ),
        "reliefs": (
            "Document-backed reliefs (Rent, Insurance, NHF, Pension, etc.)" if is_pit
            else "Capital allowances, business expenses"
        ),
        "filing_deadline": (
            "31st March (individuals)" if is_pit
            else "Within 6 months of accounting year end"
        ),
    }
    
    return BusinessTypeResponse(
        entity_id=entity.id,
        entity_name=entity.name,
        business_type=entity.business_type.value,
        tax_regime="PIT" if is_pit else "CIT",
        annual_turnover=float(entity.annual_turnover) if entity.annual_turnover else None,
        fixed_assets_value=float(entity.fixed_assets_value) if entity.fixed_assets_value else None,
        is_development_levy_exempt=entity.is_development_levy_exempt,
        tax_implications=tax_implications,
    )


@router.patch(
    "/{entity_id}/business-type",
    response_model=BusinessTypeResponse,
    summary="Update business type",
    tags=["2026 Reform - Business Type"],
)
async def update_business_type(
    entity_id: UUID,
    request: BusinessTypeUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update entity's business type.
    
    This affects whether PIT or CIT rules apply.
    """
    entity = await verify_entity_access(entity_id, current_user, db)
    
    # Update business type
    entity.business_type = request.business_type
    
    if request.annual_turnover is not None:
        entity.annual_turnover = request.annual_turnover
    if request.fixed_assets_value is not None:
        entity.fixed_assets_value = request.fixed_assets_value
    
    # Recalculate Development Levy exemption
    dev_service = DevelopmentLevyService(db)
    await dev_service.update_entity_thresholds(
        entity_id=entity_id,
        annual_turnover=entity.annual_turnover,
        fixed_assets_value=entity.fixed_assets_value,
    )
    
    await db.refresh(entity)
    
    is_pit = entity.business_type == BusinessType.BUSINESS_NAME
    
    tax_implications = {
        "tax_type": "PIT (Personal Income Tax)" if is_pit else "CIT (Company Income Tax)",
        "rates": (
            "0%/15%/20%/25%/30% progressive bands" if is_pit
            else "0%/20%/30% based on company size"
        ),
        "development_levy": "Not applicable" if is_pit else (
            "Exempt" if entity.is_development_levy_exempt else "4% of assessable profit"
        ),
    }
    
    return BusinessTypeResponse(
        entity_id=entity.id,
        entity_name=entity.name,
        business_type=entity.business_type.value,
        tax_regime="PIT" if is_pit else "CIT",
        annual_turnover=float(entity.annual_turnover) if entity.annual_turnover else None,
        fixed_assets_value=float(entity.fixed_assets_value) if entity.fixed_assets_value else None,
        is_development_levy_exempt=entity.is_development_levy_exempt,
        tax_implications=tax_implications,
    )


@router.get(
    "/business-types/comparison",
    summary="Compare Business Name vs Limited Company",
    tags=["2026 Reform - Business Type"],
)
async def compare_business_types():
    """
    Get comparison between Business Name and Limited Company tax treatment.
    
    Helps users decide which structure suits their business.
    """
    return {
        "business_name": {
            "registration": "CAC Business Name registration",
            "tax_type": "Personal Income Tax (PIT)",
            "rates": {
                "first_₦800,000": "0%",
                "next_₦2,400,000": "15%",
                "next_₦4,000,000": "20%",
                "next_₦7,000,000": "25%",
                "above_₦14,200,000": "30%",
            },
            "development_levy": "Not applicable",
            "liability": "Unlimited personal liability",
            "suitable_for": "Freelancers, small traders, sole proprietors",
        },
        "limited_company": {
            "registration": "CAC Company registration",
            "tax_type": "Company Income Tax (CIT)",
            "rates": {
                "turnover_≤₦25M": "0% (Small company)",
                "turnover_₦25M-₦100M": "20% (Medium company)",
                "turnover_>₦100M": "30% (Large company)",
            },
            "development_levy": "4% of assessable profit (exempt if turnover ≤ ₦100M AND assets ≤ ₦250M)",
            "liability": "Limited to share capital",
            "suitable_for": "Growing businesses, those seeking investment, contractors",
        },
        "2026_reform_note": "The 2026 reforms introduced clearer distinctions and simplified compliance for both structures.",
    }


# ===========================================
# TIN VALIDATION ENDPOINTS (NRS TaxID Portal)
# ===========================================

class TINValidationRequest(BaseModel):
    """Request to validate a TIN."""
    tin: str = Field(..., min_length=10, max_length=18, description="Tax Identification Number to validate")
    entity_type: Optional[str] = Field(
        None, 
        description="Type of entity: individual, business_name, company, incorporated_trustee, limited_partnership, llp"
    )
    search_term: Optional[str] = Field(
        None,
        description="NIN for individuals, or business name for corporate entities"
    )


class TINValidationResponse(BaseModel):
    """Response from TIN validation."""
    is_valid: bool
    tin: str
    status: str
    entity_type: Optional[str] = None
    registered_name: Optional[str] = None
    rc_number: Optional[str] = None
    registration_date: Optional[str] = None
    address: Optional[str] = None
    tax_office: Optional[str] = None
    vat_registered: Optional[bool] = None
    message: str
    validated_at: Optional[str] = None


class BulkTINValidationRequest(BaseModel):
    """Request to validate multiple TINs."""
    tins: List[str] = Field(..., min_length=1, max_length=50, description="List of TINs to validate")


class BulkTINValidationResponse(BaseModel):
    """Response from bulk TIN validation."""
    total: int
    valid_count: int
    invalid_count: int
    results: List[TINValidationResponse]


@router.post(
    "/tin/validate",
    response_model=TINValidationResponse,
    summary="Validate a TIN",
    tags=["2026 Reform - TIN Validation"],
)
async def validate_tin(
    request: TINValidationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Validate a Tax Identification Number (TIN) via NRS TaxID Portal.
    
    2026 Compliance Requirement:
    - Mandatory TIN validation for all individuals and businesses
    - All vendors/suppliers must have valid TINs before contracts
    - Failure to validate can result in ₦5,000,000 penalty
    
    Portal: https://taxid.nrs.gov.ng/
    """
    service = TINValidationService(db)
    
    # Convert entity_type string to enum if provided
    entity_type = None
    if request.entity_type:
        try:
            entity_type = TINEntityType(request.entity_type)
        except ValueError:
            pass  # Invalid entity type, proceed without it
    
    result = await service.validate_tin(
        tin=request.tin,
        entity_type=entity_type,
        search_term=request.search_term,
    )
    
    return TINValidationResponse(
        is_valid=result.is_valid,
        tin=result.tin,
        status=result.status.value,
        entity_type=result.entity_type.value if result.entity_type else None,
        registered_name=result.registered_name,
        rc_number=result.rc_number,
        registration_date=result.registration_date,
        address=result.address,
        tax_office=result.tax_office,
        vat_registered=result.vat_registered,
        message=result.message,
        validated_at=result.validated_at.isoformat() if result.validated_at else None,
    )


@router.post(
    "/tin/validate-bulk",
    response_model=BulkTINValidationResponse,
    summary="Bulk validate TINs",
    tags=["2026 Reform - TIN Validation"],
)
async def validate_tins_bulk(
    request: BulkTINValidationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Validate multiple TINs in a single request.
    
    Useful for bulk vendor/customer onboarding.
    Maximum 50 TINs per request.
    """
    service = TINValidationService(db)
    
    results = []
    valid_count = 0
    invalid_count = 0
    
    for tin in request.tins:
        result = await service.validate_tin(tin=tin)
        
        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1
        
        results.append(TINValidationResponse(
            is_valid=result.is_valid,
            tin=result.tin,
            status=result.status.value,
            entity_type=result.entity_type.value if result.entity_type else None,
            registered_name=result.registered_name,
            rc_number=result.rc_number,
            registration_date=result.registration_date,
            address=result.address,
            tax_office=result.tax_office,
            vat_registered=result.vat_registered,
            message=result.message,
            validated_at=result.validated_at.isoformat() if result.validated_at else None,
        ))
    
    return BulkTINValidationResponse(
        total=len(request.tins),
        valid_count=valid_count,
        invalid_count=invalid_count,
        results=results,
    )


@router.get(
    "/tin/entity-types",
    summary="Get TIN entity types",
    tags=["2026 Reform - TIN Validation"],
)
async def get_tin_entity_types():
    """
    Get list of entity types supported for TIN validation.
    
    Each entity type has different validation requirements:
    - Individual: Requires NIN (National Identification Number)
    - Corporate: Requires CAC registration details
    """
    return {
        "entity_types": [
            {
                "value": "individual",
                "label": "Individual",
                "description": "Individual taxpayer with NIN",
                "requires": "NIN (National Identification Number)",
            },
            {
                "value": "business_name",
                "label": "Business Name",
                "description": "Sole Proprietorship registered with CAC",
                "requires": "Business Name registration number",
            },
            {
                "value": "company",
                "label": "Limited Liability Company",
                "description": "Company registered with CAC",
                "requires": "RC Number",
            },
            {
                "value": "incorporated_trustee",
                "label": "Incorporated Trustee",
                "description": "NGOs, Churches, Associations",
                "requires": "IT Number",
            },
            {
                "value": "limited_partnership",
                "label": "Limited Partnership",
                "description": "Partnership with limited liability partners",
                "requires": "LP Number",
            },
            {
                "value": "llp",
                "label": "Limited Liability Partnership",
                "description": "Professional partnership with LLP registration",
                "requires": "LLP Number",
            },
        ],
        "portal_url": "https://taxid.nrs.gov.ng/",
        "compliance_note": "2026 NTAA requires TIN validation for all business transactions above ₦100,000",
    }
