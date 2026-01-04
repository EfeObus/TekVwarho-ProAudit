"""
TekVwarho ProAudit - Invoices Router

API endpoints for invoice management with NRS e-invoicing support.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.invoice import InvoiceStatus, VATTreatment
from app.services.invoice_service import InvoiceService
from app.services.entity_service import EntityService
from app.schemas.auth import MessageResponse


router = APIRouter()


# ===========================================
# REQUEST/RESPONSE SCHEMAS
# ===========================================

class InvoiceLineItemRequest(BaseModel):
    """Schema for invoice line item in request."""
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    vat_rate: float = Field(7.5, ge=0, le=100)


class InvoiceCreateRequest(BaseModel):
    """Schema for creating an invoice."""
    customer_id: Optional[UUID] = None
    invoice_date: date
    due_date: date
    vat_treatment: str = "standard"
    vat_rate: float = Field(7.5, ge=0, le=100)
    line_items: List[InvoiceLineItemRequest] = Field(..., min_length=1)
    discount_amount: float = Field(0, ge=0)
    notes: Optional[str] = None
    terms: Optional[str] = None


class InvoiceUpdateRequest(BaseModel):
    """Schema for updating an invoice."""
    customer_id: Optional[UUID] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    vat_treatment: Optional[str] = None
    vat_rate: Optional[float] = Field(None, ge=0, le=100)
    discount_amount: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    terms: Optional[str] = None


class PaymentRecordRequest(BaseModel):
    """Schema for recording a payment."""
    amount: float = Field(..., gt=0)
    payment_date: date
    payment_method: str = "bank_transfer"
    reference: Optional[str] = None
    notes: Optional[str] = None


class AddLineItemRequest(BaseModel):
    """Schema for adding a line item."""
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    vat_rate: float = Field(7.5, ge=0, le=100)


class LineItemResponse(BaseModel):
    """Schema for line item response."""
    id: UUID
    description: str
    quantity: float
    unit_price: float
    subtotal: float
    vat_amount: float
    total: float
    sort_order: int
    
    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""
    id: UUID
    entity_id: UUID
    invoice_number: str
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    invoice_date: date
    due_date: date
    subtotal: float
    vat_amount: float
    discount_amount: float
    total_amount: float
    amount_paid: float
    balance_due: float
    vat_treatment: str
    vat_rate: float
    status: str
    is_overdue: bool
    nrs_irn: Optional[str] = None
    nrs_qr_code_data: Optional[str] = None
    nrs_submitted_at: Optional[datetime] = None
    dispute_deadline: Optional[datetime] = None
    is_disputed: bool
    notes: Optional[str] = None
    terms: Optional[str] = None
    pdf_url: Optional[str] = None
    line_items: List[LineItemResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Schema for invoice list response."""
    invoices: List[InvoiceResponse]
    total: int
    page: int
    page_size: int


class InvoiceSummaryResponse(BaseModel):
    """Schema for invoice summary response."""
    total_invoices: int
    total_draft: int
    total_pending: int
    total_submitted: int
    total_accepted: int
    total_paid: int
    total_overdue: int
    total_invoiced: float
    total_collected: float
    total_outstanding: float
    total_vat_collected: float
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class NRSSubmissionResponse(BaseModel):
    """Schema for NRS submission response."""
    success: bool
    invoice_id: str
    nrs_irn: Optional[str] = None
    qr_code_data: Optional[str] = None
    message: str
    submitted_at: Optional[datetime] = None
    dispute_deadline: Optional[datetime] = None


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def invoice_to_response(invoice) -> InvoiceResponse:
    """Convert Invoice model to response schema."""
    today = date.today()
    is_overdue = (
        invoice.due_date < today and 
        invoice.status.value not in ["paid", "cancelled"]
    )
    
    line_items = [
        LineItemResponse(
            id=li.id,
            description=li.description,
            quantity=float(li.quantity),
            unit_price=float(li.unit_price),
            subtotal=float(li.subtotal),
            vat_amount=float(li.vat_amount),
            total=float(li.total),
            sort_order=li.sort_order,
        )
        for li in sorted(invoice.line_items, key=lambda x: x.sort_order)
    ]
    
    return InvoiceResponse(
        id=invoice.id,
        entity_id=invoice.entity_id,
        invoice_number=invoice.invoice_number,
        customer_id=invoice.customer_id,
        customer_name=invoice.customer.name if invoice.customer else None,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        subtotal=float(invoice.subtotal),
        vat_amount=float(invoice.vat_amount),
        discount_amount=float(invoice.discount_amount),
        total_amount=float(invoice.total_amount),
        amount_paid=float(invoice.amount_paid),
        balance_due=float(invoice.balance_due),
        vat_treatment=invoice.vat_treatment.value,
        vat_rate=float(invoice.vat_rate),
        status=invoice.status.value,
        is_overdue=is_overdue,
        nrs_irn=invoice.nrs_irn,
        nrs_qr_code_data=invoice.nrs_qr_code_data,
        nrs_submitted_at=invoice.nrs_submitted_at,
        dispute_deadline=invoice.dispute_deadline,
        is_disputed=invoice.is_disputed,
        notes=invoice.notes,
        terms=invoice.terms,
        pdf_url=invoice.pdf_url,
        line_items=line_items,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


async def verify_entity_access(
    entity_id: UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Verify user has access to the entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, user)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business entity not found or access denied",
        )


# ===========================================
# ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
)
async def list_invoices(
    entity_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    is_overdue: Optional[bool] = Query(None, description="Filter overdue invoices"),
    search: Optional[str] = Query(None, description="Search invoice number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List all invoices for a business entity.
    
    Supports filtering by status, customer, date range, and search.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    # Convert status string to enum
    status_enum = None
    if status:
        try:
            status_enum = InvoiceStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )
    
    invoices, total = await invoice_service.get_invoices_for_entity(
        entity_id=entity_id,
        status=status_enum,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        is_overdue=is_overdue,
        search=search,
        page=page,
        page_size=page_size,
    )
    
    return InvoiceListResponse(
        invoices=[invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{entity_id}/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice",
)
async def create_invoice(
    entity_id: UUID,
    request: InvoiceCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new invoice.
    
    Invoice is created in DRAFT status and can be edited until finalized.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    # Convert vat_treatment string to enum
    try:
        vat_treatment = VATTreatment(request.vat_treatment)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid VAT treatment: {request.vat_treatment}",
        )
    
    # Convert line items to dicts
    line_items_data = [
        {
            "description": li.description,
            "quantity": li.quantity,
            "unit_price": li.unit_price,
            "vat_rate": li.vat_rate,
        }
        for li in request.line_items
    ]
    
    invoice = await invoice_service.create_invoice(
        entity_id=entity_id,
        user_id=current_user.id,
        invoice_date=request.invoice_date,
        due_date=request.due_date,
        line_items_data=line_items_data,
        customer_id=request.customer_id,
        vat_treatment=vat_treatment,
        vat_rate=request.vat_rate,
        discount_amount=request.discount_amount,
        notes=request.notes,
        terms=request.terms,
    )
    
    return invoice_to_response(invoice)


@router.get(
    "/{entity_id}/invoices/summary",
    response_model=InvoiceSummaryResponse,
    summary="Get invoice summary",
)
async def get_invoice_summary(
    entity_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get invoice summary statistics for a business entity.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    summary = await invoice_service.get_invoice_summary(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return InvoiceSummaryResponse(**summary)


@router.get(
    "/{entity_id}/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice",
)
async def get_invoice(
    entity_id: UUID,
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get a specific invoice by ID.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    invoice = await invoice_service.get_invoice_by_id(invoice_id, entity_id)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    
    return invoice_to_response(invoice)


@router.patch(
    "/{entity_id}/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice",
)
async def update_invoice(
    entity_id: UUID,
    invoice_id: UUID,
    request: InvoiceUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update an invoice (only DRAFT invoices can be updated).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    update_data = request.model_dump(exclude_unset=True)
    
    # Convert vat_treatment string to enum if present
    if "vat_treatment" in update_data and update_data["vat_treatment"]:
        try:
            update_data["vat_treatment"] = VATTreatment(update_data["vat_treatment"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid VAT treatment: {update_data['vat_treatment']}",
            )
    
    try:
        invoice = await invoice_service.update_invoice(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
            **update_data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    
    return invoice_to_response(invoice)


@router.delete(
    "/{entity_id}/invoices/{invoice_id}",
    response_model=MessageResponse,
    summary="Delete invoice",
)
async def delete_invoice(
    entity_id: UUID,
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Delete an invoice (only DRAFT invoices can be deleted).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        deleted = await invoice_service.delete_invoice(invoice_id, entity_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    
    return MessageResponse(message="Invoice deleted successfully")


# ===========================================
# LINE ITEM ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/invoices/{invoice_id}/line-items",
    response_model=InvoiceResponse,
    summary="Add line item",
)
async def add_line_item(
    entity_id: UUID,
    invoice_id: UUID,
    request: AddLineItemRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Add a line item to an invoice (only DRAFT invoices).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        invoice = await invoice_service.add_line_item(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
            description=request.description,
            quantity=request.quantity,
            unit_price=request.unit_price,
            vat_rate=request.vat_rate,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return invoice_to_response(invoice)


@router.delete(
    "/{entity_id}/invoices/{invoice_id}/line-items/{line_item_id}",
    response_model=InvoiceResponse,
    summary="Remove line item",
)
async def remove_line_item(
    entity_id: UUID,
    invoice_id: UUID,
    line_item_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Remove a line item from an invoice (only DRAFT invoices, must have at least one item).
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        invoice = await invoice_service.remove_line_item(
            invoice_id=invoice_id,
            line_item_id=line_item_id,
            entity_id=entity_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return invoice_to_response(invoice)


# ===========================================
# STATUS MANAGEMENT ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/invoices/{invoice_id}/finalize",
    response_model=InvoiceResponse,
    summary="Finalize invoice",
)
async def finalize_invoice(
    entity_id: UUID,
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Finalize a DRAFT invoice (moves to PENDING status).
    
    Once finalized, the invoice cannot be edited, only cancelled.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        invoice = await invoice_service.finalize_invoice(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return invoice_to_response(invoice)


@router.post(
    "/{entity_id}/invoices/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel invoice",
)
async def cancel_invoice(
    entity_id: UUID,
    invoice_id: UUID,
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Cancel an invoice.
    
    Cannot cancel PAID or already CANCELLED invoices.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        invoice = await invoice_service.cancel_invoice(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return invoice_to_response(invoice)


# ===========================================
# PAYMENT ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/invoices/{invoice_id}/payments",
    response_model=InvoiceResponse,
    summary="Record payment",
)
async def record_payment(
    entity_id: UUID,
    invoice_id: UUID,
    request: PaymentRecordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record a payment against an invoice.
    
    Automatically updates invoice status to PAID or PARTIALLY_PAID.
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        invoice = await invoice_service.record_payment(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
            amount=request.amount,
            payment_date=request.payment_date,
            payment_method=request.payment_method,
            reference=request.reference,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return invoice_to_response(invoice)


# ===========================================
# NRS E-INVOICING ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/invoices/{invoice_id}/submit-nrs",
    response_model=NRSSubmissionResponse,
    summary="Submit to NRS",
)
async def submit_to_nrs(
    entity_id: UUID,
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Submit invoice to NRS (FIRS) for IRN generation.
    
    This is a placeholder endpoint. Full NRS integration will be implemented in Segment 14.
    
    Requirements for NRS submission:
    - Invoice must be in PENDING or REJECTED status
    - B2B invoices require customer TIN
    """
    await verify_entity_access(entity_id, current_user, db)
    
    invoice_service = InvoiceService(db)
    
    try:
        result = await invoice_service.submit_to_nrs(
            invoice_id=invoice_id,
            entity_id=entity_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return NRSSubmissionResponse(
        success=result["success"],
        invoice_id=result["invoice_id"],
        nrs_irn=result.get("nrs_irn"),
        qr_code_data=result.get("qr_code_data"),
        message=result["message"],
        submitted_at=result.get("submitted_at"),
        dispute_deadline=result.get("dispute_deadline"),
    )
