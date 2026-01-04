"""
TekVwarho ProAudit - Sales Router

API endpoints for sales recording with inventory integration.
Provides:
- Product lookup for POS-style sales
- Customer search and quick-add
- Sale recording with automatic stock deduction
- Sales reports and analytics
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.invoice import VATTreatment
from app.services.sales_service import SalesService, SaleLineItem
from app.services.entity_service import EntityService


router = APIRouter()


# ===========================================
# SCHEMAS
# ===========================================

class ProductSearchResult(BaseModel):
    """Product search result for dropdown."""
    id: str
    sku: str
    name: str
    description: Optional[str]
    category: Optional[str]
    unit_price: float
    unit_cost: float
    quantity_available: int
    unit_of_measure: str
    barcode: Optional[str]
    is_low_stock: bool


class CustomerSearchResult(BaseModel):
    """Customer search result for dropdown."""
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    tin: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    is_vat_registered: bool
    payment_terms_days: int
    credit_limit: Optional[float]
    outstanding_balance: float
    is_business: bool


class QuickCustomerCreate(BaseModel):
    """Schema for quick customer creation during sales."""
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    phone: Optional[str] = None
    tin: Optional[str] = None
    address: Optional[str] = None


class QuickCustomerResponse(BaseModel):
    """Response for quick customer creation."""
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    tin: Optional[str]


class SaleLineItemRequest(BaseModel):
    """Line item in a sale."""
    inventory_item_id: Optional[UUID] = None
    description: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    vat_rate: float = Field(7.5, ge=0, le=100)
    discount_percent: float = Field(0, ge=0, le=100)


class RecordSaleRequest(BaseModel):
    """Request to record a sale."""
    customer_id: Optional[UUID] = None
    line_items: List[SaleLineItemRequest] = Field(..., min_length=1)
    sale_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    create_invoice: bool = True
    vat_treatment: str = "standard"


class SaleResponse(BaseModel):
    """Response after recording a sale."""
    success: bool
    invoice_id: Optional[str]
    invoice_number: Optional[str]
    total_amount: float
    vat_amount: float
    message: str


class SalesSummaryResponse(BaseModel):
    """Sales summary for dashboard."""
    total_sales: float
    total_vat_collected: float
    total_discount_given: float
    sales_count: int
    top_products: List[dict]
    top_customers: List[dict]


class RecentSaleResponse(BaseModel):
    """Recent sale for list display."""
    id: str
    invoice_number: str
    customer_name: str
    invoice_date: str
    total_amount: float
    status: str
    payment_status: str


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
    entity = await entity_service.get_entity_by_id(entity_id, user)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business entity not found or access denied",
        )


# ===========================================
# PRODUCT ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/sales/products",
    response_model=List[ProductSearchResult],
    summary="Search products for sale",
    description="Search inventory items for POS-style product selection",
)
async def search_products(
    entity_id: UUID,
    search: Optional[str] = Query(None, description="Search by name, SKU, or barcode"),
    category: Optional[str] = Query(None),
    in_stock_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Search products available for sale."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    items = await service.get_sellable_items(
        entity_id=entity_id,
        search=search,
        category=category,
        in_stock_only=in_stock_only,
        limit=limit,
    )
    
    return items


@router.get(
    "/{entity_id}/sales/products/barcode/{barcode}",
    response_model=ProductSearchResult,
    summary="Get product by barcode",
    description="Lookup product by barcode scan",
)
async def get_product_by_barcode(
    entity_id: UUID,
    barcode: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get product by barcode for POS scanning."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    item = await service.get_item_by_barcode(entity_id, barcode)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product found with barcode: {barcode}",
        )
    
    return item


@router.get(
    "/{entity_id}/sales/categories",
    response_model=List[str],
    summary="Get product categories",
)
async def get_categories(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get all product categories for filtering."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    return await service.get_inventory_categories(entity_id)


# ===========================================
# CUSTOMER ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/sales/customers",
    response_model=List[CustomerSearchResult],
    summary="Search customers for sale",
    description="Search customers for invoice selection",
)
async def search_customers(
    entity_id: UUID,
    search: Optional[str] = Query(None, description="Search by name, email, phone, or TIN"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Search customers for sales dropdown."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    customers = await service.get_customers_for_dropdown(
        entity_id=entity_id,
        search=search,
        limit=limit,
    )
    
    return customers


@router.post(
    "/{entity_id}/sales/customers/quick",
    response_model=QuickCustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Quick-add customer",
    description="Quickly create a customer during checkout",
)
async def quick_add_customer(
    entity_id: UUID,
    request: QuickCustomerCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Quickly create a customer during sales process."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    customer = await service.quick_create_customer(
        entity_id=entity_id,
        name=request.name,
        email=request.email,
        phone=request.phone,
        tin=request.tin,
        address=request.address,
    )
    
    await db.commit()
    
    return QuickCustomerResponse(
        id=str(customer.id),
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        tin=customer.tin,
    )


# ===========================================
# SALES RECORDING ENDPOINTS
# ===========================================

@router.post(
    "/{entity_id}/sales/record",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a sale",
    description="Record a sale with automatic inventory deduction and invoice creation",
)
async def record_sale(
    entity_id: UUID,
    request: RecordSaleRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Record a sale.
    
    This endpoint:
    - Creates an invoice (if create_invoice=True)
    - Deducts inventory stock
    - Records stock movements
    - Creates income transaction
    """
    await verify_entity_access(entity_id, current_user, db)
    
    # Convert request to SaleLineItem objects
    line_items = [
        SaleLineItem(
            inventory_item_id=item.inventory_item_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=Decimal(str(item.unit_price)),
            vat_rate=Decimal(str(item.vat_rate)),
            discount_percent=Decimal(str(item.discount_percent)),
        )
        for item in request.line_items
    ]
    
    # Convert VAT treatment
    try:
        vat_treatment = VATTreatment(request.vat_treatment)
    except ValueError:
        vat_treatment = VATTreatment.STANDARD
    
    service = SalesService(db)
    
    try:
        invoice, transactions = await service.record_sale(
            entity_id=entity_id,
            user_id=current_user.id,
            customer_id=request.customer_id,
            line_items=line_items,
            sale_date=request.sale_date,
            payment_method=request.payment_method,
            reference=request.reference,
            notes=request.notes,
            create_invoice=request.create_invoice,
            vat_treatment=vat_treatment,
        )
        
        total_amount = sum(item.total for item in line_items)
        vat_amount = sum(item.vat_amount for item in line_items) if vat_treatment == VATTreatment.STANDARD else Decimal("0")
        
        return SaleResponse(
            success=True,
            invoice_id=str(invoice.id) if invoice else None,
            invoice_number=invoice.invoice_number if invoice else None,
            total_amount=float(total_amount),
            vat_amount=float(vat_amount),
            message="Sale recorded successfully",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to record sale: {str(e)}",
        )


# ===========================================
# SALES REPORTS ENDPOINTS
# ===========================================

@router.get(
    "/{entity_id}/sales/summary",
    response_model=SalesSummaryResponse,
    summary="Get sales summary",
)
async def get_sales_summary(
    entity_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get sales summary for a date range."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    summary = await service.get_sales_summary(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return SalesSummaryResponse(
        total_sales=float(summary.total_sales),
        total_vat_collected=float(summary.total_vat_collected),
        total_discount_given=float(summary.total_discount_given),
        sales_count=summary.sales_count,
        top_products=summary.top_products,
        top_customers=summary.top_customers,
    )


@router.get(
    "/{entity_id}/sales/recent",
    response_model=List[RecentSaleResponse],
    summary="Get recent sales",
)
async def get_recent_sales(
    entity_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent sales for dashboard display."""
    await verify_entity_access(entity_id, current_user, db)
    
    service = SalesService(db)
    sales = await service.get_recent_sales(entity_id, limit)
    
    return sales
