"""
TekVwarho ProAudit - Invoice Service

Business logic for invoice management with NRS e-invoicing support.
"""

import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus, VATTreatment
from app.models.customer import Customer
from app.models.entity import BusinessEntity


class InvoiceService:
    """Service for invoice operations."""
    
    # NRS dispute window (72 hours)
    DISPUTE_WINDOW_HOURS = 72
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # INVOICE NUMBER GENERATION
    # ===========================================
    
    async def generate_invoice_number(self, entity_id: uuid.UUID) -> str:
        """
        Generate unique invoice number for entity.
        
        Format: INV-YYYYMM-NNNN (e.g., INV-202601-0001)
        """
        today = date.today()
        prefix = f"INV-{today.year}{today.month:02d}"
        
        # Get count of invoices for this month
        result = await self.db.execute(
            select(func.count(Invoice.id))
            .where(Invoice.entity_id == entity_id)
            .where(Invoice.invoice_number.like(f"{prefix}%"))
        )
        count = result.scalar() or 0
        
        # Generate next number
        next_number = count + 1
        return f"{prefix}-{next_number:04d}"
    
    # ===========================================
    # CRUD OPERATIONS
    # ===========================================
    
    async def get_invoices_for_entity(
        self,
        entity_id: uuid.UUID,
        status: Optional[InvoiceStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        is_overdue: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Invoice], int]:
        """Get invoices for an entity with filters."""
        query = (
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.line_items),
            )
            .where(Invoice.entity_id == entity_id)
        )
        
        # Apply filters
        if status:
            query = query.where(Invoice.status == status)
        
        if customer_id:
            query = query.where(Invoice.customer_id == customer_id)
        
        if start_date:
            query = query.where(Invoice.invoice_date >= start_date)
        
        if end_date:
            query = query.where(Invoice.invoice_date <= end_date)
        
        if is_overdue is True:
            today = date.today()
            query = query.where(
                and_(
                    Invoice.due_date < today,
                    Invoice.status.not_in([InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
                )
            )
        
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Invoice.invoice_number.ilike(search_term),
                    Invoice.notes.ilike(search_term),
                )
            )
        
        # Count total
        count_query = (
            select(func.count(Invoice.id))
            .where(Invoice.entity_id == entity_id)
        )
        if status:
            count_query = count_query.where(Invoice.status == status)
        if customer_id:
            count_query = count_query.where(Invoice.customer_id == customer_id)
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
        query = query.limit(page_size).offset(offset)
        
        result = await self.db.execute(query)
        invoices = list(result.scalars().all())
        
        return invoices, total
    
    async def get_invoice_by_id(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> Optional[Invoice]:
        """Get invoice by ID."""
        result = await self.db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.line_items),
            )
            .where(Invoice.id == invoice_id)
            .where(Invoice.entity_id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def get_invoice_by_number(
        self,
        invoice_number: str,
        entity_id: uuid.UUID,
    ) -> Optional[Invoice]:
        """Get invoice by invoice number."""
        result = await self.db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.line_items),
            )
            .where(Invoice.invoice_number == invoice_number)
            .where(Invoice.entity_id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def create_invoice(
        self,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        invoice_date: date,
        due_date: date,
        line_items_data: List[dict],
        customer_id: Optional[uuid.UUID] = None,
        vat_treatment: VATTreatment = VATTreatment.STANDARD,
        vat_rate: float = 7.5,
        discount_amount: float = 0,
        notes: Optional[str] = None,
        terms: Optional[str] = None,
    ) -> Invoice:
        """Create a new invoice with line items."""
        # Generate invoice number
        invoice_number = await self.generate_invoice_number(entity_id)
        
        # Calculate totals
        subtotal = Decimal("0")
        total_vat = Decimal("0")
        
        for item in line_items_data:
            item_subtotal = Decimal(str(item['quantity'])) * Decimal(str(item['unit_price']))
            item_vat = Decimal("0")
            
            if vat_treatment == VATTreatment.STANDARD:
                item_vat = item_subtotal * (Decimal(str(item.get('vat_rate', vat_rate))) / 100)
            
            subtotal += item_subtotal
            total_vat += item_vat
        
        total_amount = subtotal + total_vat - Decimal(str(discount_amount))
        
        # Create invoice
        invoice = Invoice(
            entity_id=entity_id,
            invoice_number=invoice_number,
            customer_id=customer_id,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            vat_amount=total_vat,
            discount_amount=Decimal(str(discount_amount)),
            total_amount=total_amount,
            vat_treatment=vat_treatment,
            vat_rate=Decimal(str(vat_rate)),
            status=InvoiceStatus.DRAFT,
            notes=notes,
            terms=terms,
            created_by=user_id,
            updated_by=user_id,
        )
        
        self.db.add(invoice)
        await self.db.flush()  # Get the invoice ID
        
        # Create line items
        for idx, item_data in enumerate(line_items_data):
            item_subtotal = Decimal(str(item_data['quantity'])) * Decimal(str(item_data['unit_price']))
            item_vat = Decimal("0")
            
            if vat_treatment == VATTreatment.STANDARD:
                item_vat = item_subtotal * (Decimal(str(item_data.get('vat_rate', vat_rate))) / 100)
            
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                description=item_data['description'],
                quantity=Decimal(str(item_data['quantity'])),
                unit_price=Decimal(str(item_data['unit_price'])),
                subtotal=item_subtotal,
                vat_amount=item_vat,
                total=item_subtotal + item_vat,
                sort_order=idx,
            )
            self.db.add(line_item)
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        # Load relationships
        return await self.get_invoice_by_id(invoice.id, entity_id)
    
    async def update_invoice(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        **update_data,
    ) -> Optional[Invoice]:
        """Update an invoice (only if in DRAFT status)."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            return None
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only update invoices in DRAFT status")
        
        # Update fields
        allowed_fields = [
            'customer_id', 'invoice_date', 'due_date',
            'vat_treatment', 'vat_rate', 'discount_amount',
            'notes', 'terms'
        ]
        
        for field in allowed_fields:
            if field in update_data and update_data[field] is not None:
                setattr(invoice, field, update_data[field])
        
        invoice.updated_by = user_id
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    async def delete_invoice(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> bool:
        """Delete an invoice (only if in DRAFT status)."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            return False
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only delete invoices in DRAFT status")
        
        await self.db.delete(invoice)
        await self.db.commit()
        
        return True
    
    # ===========================================
    # LINE ITEM OPERATIONS
    # ===========================================
    
    async def add_line_item(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        description: str,
        quantity: float,
        unit_price: float,
        vat_rate: float = 7.5,
    ) -> Invoice:
        """Add a line item to an invoice."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only modify invoices in DRAFT status")
        
        # Calculate line item totals
        item_subtotal = Decimal(str(quantity)) * Decimal(str(unit_price))
        item_vat = Decimal("0")
        
        if invoice.vat_treatment == VATTreatment.STANDARD:
            item_vat = item_subtotal * (Decimal(str(vat_rate)) / 100)
        
        # Get next sort order
        max_order = max([li.sort_order for li in invoice.line_items], default=-1)
        
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            description=description,
            quantity=Decimal(str(quantity)),
            unit_price=Decimal(str(unit_price)),
            subtotal=item_subtotal,
            vat_amount=item_vat,
            total=item_subtotal + item_vat,
            sort_order=max_order + 1,
        )
        
        self.db.add(line_item)
        
        # Recalculate invoice totals
        await self._recalculate_invoice_totals(invoice, user_id)
        
        return await self.get_invoice_by_id(invoice_id, entity_id)
    
    async def remove_line_item(
        self,
        invoice_id: uuid.UUID,
        line_item_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Invoice:
        """Remove a line item from an invoice."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only modify invoices in DRAFT status")
        
        if len(invoice.line_items) <= 1:
            raise ValueError("Invoice must have at least one line item")
        
        # Find and remove line item
        line_item = next(
            (li for li in invoice.line_items if li.id == line_item_id),
            None
        )
        
        if not line_item:
            raise ValueError("Line item not found")
        
        await self.db.delete(line_item)
        
        # Recalculate invoice totals
        await self._recalculate_invoice_totals(invoice, user_id)
        
        return await self.get_invoice_by_id(invoice_id, entity_id)
    
    async def _recalculate_invoice_totals(
        self,
        invoice: Invoice,
        user_id: uuid.UUID,
    ):
        """Recalculate invoice totals from line items."""
        await self.db.flush()
        
        # Reload line items
        result = await self.db.execute(
            select(InvoiceLineItem)
            .where(InvoiceLineItem.invoice_id == invoice.id)
        )
        line_items = list(result.scalars().all())
        
        subtotal = sum(li.subtotal for li in line_items)
        vat_amount = sum(li.vat_amount for li in line_items)
        total_amount = subtotal + vat_amount - invoice.discount_amount
        
        invoice.subtotal = subtotal
        invoice.vat_amount = vat_amount
        invoice.total_amount = total_amount
        invoice.updated_by = user_id
        
        await self.db.commit()
    
    # ===========================================
    # STATUS MANAGEMENT
    # ===========================================
    
    async def finalize_invoice(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Invoice:
        """Finalize a draft invoice (move to PENDING status)."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only finalize DRAFT invoices")
        
        invoice.status = InvoiceStatus.PENDING
        invoice.updated_by = user_id
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    async def cancel_invoice(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> Invoice:
        """Cancel an invoice."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            raise ValueError("Cannot cancel a PAID or already CANCELLED invoice")
        
        invoice.status = InvoiceStatus.CANCELLED
        if reason:
            invoice.notes = f"{invoice.notes or ''}\n\nCancelled: {reason}".strip()
        invoice.updated_by = user_id
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    # ===========================================
    # PAYMENT RECORDING
    # ===========================================
    
    async def record_payment(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        amount: float,
        payment_date: date,
        payment_method: str = "bank_transfer",
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Invoice:
        """Record a payment against an invoice."""
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValueError("Cannot record payment on cancelled invoice")
        
        if invoice.status == InvoiceStatus.DRAFT:
            raise ValueError("Cannot record payment on draft invoice")
        
        payment_amount = Decimal(str(amount))
        new_amount_paid = invoice.amount_paid + payment_amount
        
        if new_amount_paid > invoice.total_amount:
            raise ValueError("Payment amount exceeds invoice balance")
        
        invoice.amount_paid = new_amount_paid
        
        # Update status based on payment
        if new_amount_paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        elif new_amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        
        # Add payment note
        payment_note = f"Payment received: ₦{amount:,.2f} on {payment_date} via {payment_method}"
        if reference:
            payment_note += f" (Ref: {reference})"
        invoice.notes = f"{invoice.notes or ''}\n\n{payment_note}".strip()
        
        invoice.updated_by = user_id
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return invoice
    
    # ===========================================
    # NRS E-INVOICING
    # ===========================================
    
    async def submit_to_nrs(
        self,
        invoice_id: uuid.UUID,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Submit invoice to NRS for IRN generation.
        
        Uses the NRS API client to submit the invoice and obtain an IRN.
        """
        from app.services.nrs_service import get_nrs_client
        
        invoice = await self.get_invoice_by_id(invoice_id, entity_id)
        
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status not in [InvoiceStatus.PENDING, InvoiceStatus.REJECTED]:
            raise ValueError("Can only submit PENDING or REJECTED invoices to NRS")
        
        # Get entity details for seller information
        entity_result = await self.db.execute(
            select(BusinessEntity).where(BusinessEntity.id == entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        
        if not entity:
            raise ValueError("Business entity not found")
        
        if not entity.tin:
            raise ValueError("Business entity TIN is required for NRS submission")
        
        # Validate B2B requirements
        buyer_tin = None
        buyer_name = "Walk-in Customer"
        buyer_address = None
        
        if invoice.customer:
            buyer_name = invoice.customer.name
            buyer_address = invoice.customer.address
            
            if invoice.customer.is_business:
                if not invoice.customer.tin:
                    raise ValueError("B2B invoices require customer TIN for NRS submission")
                buyer_tin = invoice.customer.tin
        
        # Prepare line items
        line_items = [
            {
                "description": li.description,
                "quantity": float(li.quantity),
                "unit_price": float(li.unit_price),
                "vat_amount": float(li.vat_amount),
                "total": float(li.total),
            }
            for li in invoice.line_items
        ]
        
        # Build seller address
        seller_address = ", ".join(filter(None, [
            entity.address_line1,
            entity.address_line2,
            entity.city,
            entity.state,
            entity.country,
        ]))
        
        # Submit to NRS
        nrs_client = get_nrs_client()
        result = await nrs_client.submit_invoice(
            seller_tin=entity.tin,
            seller_name=entity.legal_name or entity.name,
            seller_address=seller_address or "Nigeria",
            buyer_name=buyer_name,
            buyer_tin=buyer_tin,
            buyer_address=buyer_address,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date.strftime("%Y-%m-%d"),
            subtotal=float(invoice.subtotal),
            vat_amount=float(invoice.vat_amount),
            total_amount=float(invoice.total_amount),
            line_items=line_items,
            vat_rate=float(invoice.vat_rate),
        )
        
        if result.success:
            invoice.status = InvoiceStatus.SUBMITTED
            invoice.nrs_irn = result.irn
            invoice.nrs_qr_code_data = result.qr_code_data
            invoice.nrs_submitted_at = result.submission_timestamp
            invoice.dispute_deadline = result.dispute_deadline
            invoice.nrs_response = json.dumps(result.raw_response) if result.raw_response else None
            invoice.updated_by = user_id
            
            await self.db.commit()
            await self.db.refresh(invoice)
            
            return {
                "success": True,
                "invoice_id": str(invoice.id),
                "nrs_irn": result.irn,
                "qr_code_data": result.qr_code_data,
                "message": result.message,
                "submitted_at": result.submission_timestamp,
                "dispute_deadline": result.dispute_deadline,
            }
        else:
            # Mark as rejected if submission failed
            invoice.status = InvoiceStatus.REJECTED
            invoice.nrs_response = json.dumps(result.raw_response) if result.raw_response else result.message
            invoice.updated_by = user_id
            
            await self.db.commit()
            
            return {
                "success": False,
                "invoice_id": str(invoice.id),
                "message": result.message,
                "error_code": result.response_code,
            }
    
    # ===========================================
    # STATISTICS & REPORTING
    # ===========================================
    
    async def get_invoice_summary(
        self,
        entity_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get invoice summary statistics."""
        today = date.today()
        
        # Base query
        base_query = select(Invoice).where(Invoice.entity_id == entity_id)
        
        if start_date:
            base_query = base_query.where(Invoice.invoice_date >= start_date)
        if end_date:
            base_query = base_query.where(Invoice.invoice_date <= end_date)
        
        result = await self.db.execute(base_query)
        invoices = list(result.scalars().all())
        
        # Calculate statistics
        summary = {
            "total_invoices": len(invoices),
            "total_draft": 0,
            "total_pending": 0,
            "total_submitted": 0,
            "total_accepted": 0,
            "total_paid": 0,
            "total_overdue": 0,
            "total_invoiced": Decimal("0"),
            "total_collected": Decimal("0"),
            "total_outstanding": Decimal("0"),
            "total_vat_collected": Decimal("0"),
            "period_start": start_date,
            "period_end": end_date,
        }
        
        for inv in invoices:
            # Count by status
            if inv.status == InvoiceStatus.DRAFT:
                summary["total_draft"] += 1
            elif inv.status == InvoiceStatus.PENDING:
                summary["total_pending"] += 1
            elif inv.status == InvoiceStatus.SUBMITTED:
                summary["total_submitted"] += 1
            elif inv.status == InvoiceStatus.ACCEPTED:
                summary["total_accepted"] += 1
            elif inv.status == InvoiceStatus.PAID:
                summary["total_paid"] += 1
            
            # Check overdue
            if inv.due_date < today and inv.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
                summary["total_overdue"] += 1
            
            # Financial totals (exclude drafts and cancelled)
            if inv.status not in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
                summary["total_invoiced"] += inv.total_amount
                summary["total_collected"] += inv.amount_paid
                summary["total_outstanding"] += (inv.total_amount - inv.amount_paid)
                
                # VAT from paid invoices
                if inv.status == InvoiceStatus.PAID:
                    summary["total_vat_collected"] += inv.vat_amount
        
        # Convert Decimals to floats for JSON serialization
        summary["total_invoiced"] = float(summary["total_invoiced"])
        summary["total_collected"] = float(summary["total_collected"])
        summary["total_outstanding"] = float(summary["total_outstanding"])
        summary["total_vat_collected"] = float(summary["total_vat_collected"])
        
        return summary
