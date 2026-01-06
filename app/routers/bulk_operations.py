"""
Bulk Operations Router

Provides endpoints for bulk import and export of transactions, vendors,
customers, and inventory items.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel
import csv
import io

from app.database import get_async_session
from app.dependencies import get_current_active_user, verify_entity_access
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.models.vendor import Vendor
from app.models.customer import Customer
from app.models.inventory import InventoryItem

router = APIRouter(
    prefix="/api/v1/{entity_id}/bulk",
    tags=["Bulk Operations"],
)


# ===========================================
# RESPONSE SCHEMAS
# ===========================================

class BulkImportResult(BaseModel):
    """Result of a bulk import operation."""
    total_rows: int
    successful: int
    failed: int
    errors: List[dict]


class BulkExportInfo(BaseModel):
    """Information about an export."""
    record_count: int
    format: str
    filename: str


# ===========================================
# TRANSACTIONS BULK OPERATIONS
# ===========================================

@router.post(
    "/transactions/import",
    response_model=BulkImportResult,
    summary="Bulk import transactions",
    description="Import multiple transactions from a CSV file.",
)
async def bulk_import_transactions(
    entity_id: UUID,
    file: UploadFile = File(..., description="CSV file with transactions"),
    skip_errors: bool = Query(False, description="Continue on errors"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Import transactions from CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
        total_rows += 1
        try:
            # Parse and validate row
            transaction = Transaction(
                entity_id=entity_id,
                transaction_date=date.fromisoformat(row.get('date', '')),
                description=row.get('description', ''),
                amount=float(row.get('amount', 0)),
                transaction_type=TransactionType(row.get('type', 'expense')),
                reference=row.get('reference'),
                created_by_id=current_user.id,
            )
            db.add(transaction)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row,
            })
            if not skip_errors:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error on row {row_num}: {str(e)}",
                )
    
    if successful > 0:
        await db.commit()
    
    return BulkImportResult(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],  # Limit errors returned
    )


@router.get(
    "/transactions/export",
    summary="Export transactions to CSV",
    description="Export all transactions for the entity to a CSV file.",
)
async def export_transactions(
    entity_id: UUID,
    start_date: Optional[date] = Query(None, description="Filter start date"),
    end_date: Optional[date] = Query(None, description="Filter end date"),
    transaction_type: Optional[str] = Query(None, description="Filter by type"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export transactions to CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    query = select(Transaction).where(Transaction.entity_id == entity_id)
    
    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)
    if transaction_type:
        query = query.where(Transaction.transaction_type == TransactionType(transaction_type))
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['date', 'description', 'amount', 'type', 'reference', 'category'])
    
    for txn in transactions:
        writer.writerow([
            txn.transaction_date.isoformat(),
            txn.description,
            float(txn.amount),
            txn.transaction_type.value,
            txn.reference or '',
            txn.category.name if txn.category else '',
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=transactions_{entity_id}_{date.today().isoformat()}.csv"
        }
    )


# ===========================================
# VENDORS BULK OPERATIONS
# ===========================================

@router.post(
    "/vendors/import",
    response_model=BulkImportResult,
    summary="Bulk import vendors",
    description="Import multiple vendors from a CSV file.",
)
async def bulk_import_vendors(
    entity_id: UUID,
    file: UploadFile = File(..., description="CSV file with vendors"),
    skip_errors: bool = Query(False, description="Continue on errors"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Import vendors from CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            vendor = Vendor(
                entity_id=entity_id,
                name=row.get('name', ''),
                email=row.get('email'),
                phone=row.get('phone'),
                address=row.get('address'),
                tin=row.get('tin'),
                contact_person=row.get('contact_person'),
            )
            db.add(vendor)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row,
            })
            if not skip_errors:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error on row {row_num}: {str(e)}",
                )
    
    if successful > 0:
        await db.commit()
    
    return BulkImportResult(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
    )


@router.get(
    "/vendors/export",
    summary="Export vendors to CSV",
    description="Export all vendors for the entity to a CSV file.",
)
async def export_vendors(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export vendors to CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    query = select(Vendor).where(Vendor.entity_id == entity_id)
    result = await db.execute(query)
    vendors = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'email', 'phone', 'address', 'tin', 'contact_person'])
    
    for v in vendors:
        writer.writerow([
            v.name,
            v.email or '',
            v.phone or '',
            v.address or '',
            v.tin or '',
            v.contact_person or '',
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=vendors_{entity_id}_{date.today().isoformat()}.csv"
        }
    )


# ===========================================
# CUSTOMERS BULK OPERATIONS
# ===========================================

@router.post(
    "/customers/import",
    response_model=BulkImportResult,
    summary="Bulk import customers",
    description="Import multiple customers from a CSV file.",
)
async def bulk_import_customers(
    entity_id: UUID,
    file: UploadFile = File(..., description="CSV file with customers"),
    skip_errors: bool = Query(False, description="Continue on errors"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Import customers from CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            customer = Customer(
                entity_id=entity_id,
                name=row.get('name', ''),
                email=row.get('email'),
                phone=row.get('phone'),
                address=row.get('address'),
                tin=row.get('tin'),
                contact_person=row.get('contact_person'),
            )
            db.add(customer)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row,
            })
            if not skip_errors:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error on row {row_num}: {str(e)}",
                )
    
    if successful > 0:
        await db.commit()
    
    return BulkImportResult(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
    )


@router.get(
    "/customers/export",
    summary="Export customers to CSV",
    description="Export all customers for the entity to a CSV file.",
)
async def export_customers(
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export customers to CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    query = select(Customer).where(Customer.entity_id == entity_id)
    result = await db.execute(query)
    customers = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'email', 'phone', 'address', 'tin', 'contact_person'])
    
    for c in customers:
        writer.writerow([
            c.name,
            c.email or '',
            c.phone or '',
            c.address or '',
            c.tin or '',
            c.contact_person or '',
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=customers_{entity_id}_{date.today().isoformat()}.csv"
        }
    )


# ===========================================
# INVENTORY BULK OPERATIONS
# ===========================================

@router.post(
    "/inventory/import",
    response_model=BulkImportResult,
    summary="Bulk import inventory items",
    description="Import multiple inventory items from a CSV file.",
)
async def bulk_import_inventory(
    entity_id: UUID,
    file: UploadFile = File(..., description="CSV file with inventory items"),
    skip_errors: bool = Query(False, description="Continue on errors"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Import inventory items from CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )
    
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        total_rows += 1
        try:
            item = InventoryItem(
                entity_id=entity_id,
                name=row.get('name', ''),
                sku=row.get('sku'),
                description=row.get('description'),
                quantity=int(row.get('quantity', 0)),
                unit_price=float(row.get('unit_price', 0)),
                reorder_level=int(row.get('reorder_level', 10)),
            )
            db.add(item)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "error": str(e),
                "data": row,
            })
            if not skip_errors:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error on row {row_num}: {str(e)}",
                )
    
    if successful > 0:
        await db.commit()
    
    return BulkImportResult(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors[:100],
    )


@router.get(
    "/inventory/export",
    summary="Export inventory to CSV",
    description="Export all inventory items for the entity to a CSV file.",
)
async def export_inventory(
    entity_id: UUID,
    low_stock_only: bool = Query(False, description="Only export items below reorder level"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Export inventory to CSV."""
    await verify_entity_access(entity_id, current_user, db)
    
    query = select(InventoryItem).where(InventoryItem.entity_id == entity_id)
    
    if low_stock_only:
        query = query.where(InventoryItem.quantity <= InventoryItem.reorder_level)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'sku', 'description', 'quantity', 'unit_price', 'reorder_level'])
    
    for item in items:
        writer.writerow([
            item.name,
            item.sku or '',
            item.description or '',
            item.quantity,
            float(item.unit_price),
            item.reorder_level,
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=inventory_{entity_id}_{date.today().isoformat()}.csv"
        }
    )


# ===========================================
# BULK TEMPLATE DOWNLOADS
# ===========================================

@router.get(
    "/templates/{resource_type}",
    summary="Download import template",
    description="Download a CSV template for bulk importing a specific resource type.",
)
async def download_template(
    entity_id: UUID,
    resource_type: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Download CSV template for bulk import."""
    await verify_entity_access(entity_id, current_user, db)
    
    templates = {
        "transactions": ['date', 'description', 'amount', 'type', 'reference'],
        "vendors": ['name', 'email', 'phone', 'address', 'tin', 'contact_person'],
        "customers": ['name', 'email', 'phone', 'address', 'tin', 'contact_person'],
        "inventory": ['name', 'sku', 'description', 'quantity', 'unit_price', 'reorder_level'],
    }
    
    if resource_type not in templates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown resource type. Available: {', '.join(templates.keys())}",
        )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(templates[resource_type])
    # Add sample row
    if resource_type == "transactions":
        writer.writerow(['2025-01-01', 'Sample expense', '1000.00', 'expense', 'REF-001'])
    elif resource_type == "vendors":
        writer.writerow(['Vendor Name', 'vendor@email.com', '+234123456789', '123 Main St', '12345678-0001', 'John Doe'])
    elif resource_type == "customers":
        writer.writerow(['Customer Name', 'customer@email.com', '+234987654321', '456 High St', '87654321-0001', 'Jane Doe'])
    elif resource_type == "inventory":
        writer.writerow(['Product Name', 'SKU-001', 'Product description', '100', '500.00', '10'])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={resource_type}_template.csv"
        }
    )
