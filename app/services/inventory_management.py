"""
Smart Inventory Management: Stock Write-off & Multi-Location Transfer System

This module provides comprehensive inventory management for Nigerian businesses:

1. Expired/Damaged Goods Write-off Workflow
   - Stock-to-Tax linking for VAT input adjustment
   - Automated documentation for FIRS compliance
   - Write-off approval workflow

2. Multi-Location (Warehouse) Inventory Transfers
   - Interstate transfer tracking
   - 2026 Interstate Levy calculations
   - Movement documentation

3. Anti-Leakage Controls
   - Variance detection
   - Shrinkage tracking
   - Audit trail
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import logging

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Enumerations
# ============================================================================

class WriteOffReason(str, Enum):
    """Reasons for inventory write-off"""
    EXPIRED = "expired"
    DAMAGED = "damaged"
    OBSOLETE = "obsolete"
    THEFT = "theft"
    SPOILAGE = "spoilage"
    QUALITY_FAILURE = "quality_failure"
    RECALL = "recall"
    SAMPLE_GIVEN = "sample_given"
    OTHER = "other"


class WriteOffStatus(str, Enum):
    """Status of write-off request"""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSED = "processed"
    CANCELLED = "cancelled"


class TransferType(str, Enum):
    """Types of inventory transfers"""
    WAREHOUSE_TO_WAREHOUSE = "warehouse_to_warehouse"
    WAREHOUSE_TO_STORE = "warehouse_to_store"
    STORE_TO_WAREHOUSE = "store_to_warehouse"
    STORE_TO_STORE = "store_to_store"
    INTERSTATE = "interstate"
    CONSIGNMENT_OUT = "consignment_out"
    CONSIGNMENT_IN = "consignment_in"


class TransferStatus(str, Enum):
    """Status of inventory transfer"""
    INITIATED = "initiated"
    IN_TRANSIT = "in_transit"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    DISCREPANCY = "discrepancy"
    CANCELLED = "cancelled"


class NigerianState(str, Enum):
    """Nigerian states for interstate transfers"""
    ABIA = "Abia"
    ADAMAWA = "Adamawa"
    AKWA_IBOM = "Akwa Ibom"
    ANAMBRA = "Anambra"
    BAUCHI = "Bauchi"
    BAYELSA = "Bayelsa"
    BENUE = "Benue"
    BORNO = "Borno"
    CROSS_RIVER = "Cross River"
    DELTA = "Delta"
    EBONYI = "Ebonyi"
    EDO = "Edo"
    EKITI = "Ekiti"
    ENUGU = "Enugu"
    FCT = "FCT"
    GOMBE = "Gombe"
    IMO = "Imo"
    JIGAWA = "Jigawa"
    KADUNA = "Kaduna"
    KANO = "Kano"
    KATSINA = "Katsina"
    KEBBI = "Kebbi"
    KOGI = "Kogi"
    KWARA = "Kwara"
    LAGOS = "Lagos"
    NASARAWA = "Nasarawa"
    NIGER = "Niger"
    OGUN = "Ogun"
    ONDO = "Ondo"
    OSUN = "Osun"
    OYO = "Oyo"
    PLATEAU = "Plateau"
    RIVERS = "Rivers"
    SOKOTO = "Sokoto"
    TARABA = "Taraba"
    YOBE = "Yobe"
    ZAMFARA = "Zamfara"


# 2026 Interstate Levy (percentage of goods value)
INTERSTATE_LEVY_RATE = Decimal("0.005")  # 0.5% for certain goods

# VAT Rate for input adjustment
VAT_RATE = Decimal("0.075")  # 7.5%


@dataclass
class WriteOffItem:
    """Individual item in a write-off request"""
    item_id: UUID
    item_name: str
    sku: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    vat_input_claimed: Decimal
    vat_adjustment_required: Decimal
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None


@dataclass
class WriteOffRequest:
    """Complete write-off request"""
    id: UUID
    entity_id: UUID
    request_number: str
    reason: WriteOffReason
    status: WriteOffStatus
    items: List[WriteOffItem]
    total_cost: Decimal
    total_vat_adjustment: Decimal
    justification: str
    supporting_documents: List[str]
    requested_by: UUID
    requested_at: datetime
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


@dataclass
class VATInputAdjustment:
    """VAT input adjustment documentation for FIRS"""
    adjustment_id: str
    entity_tin: str
    entity_name: str
    period: date
    write_off_reference: str
    reason: WriteOffReason
    items: List[Dict[str, Any]]
    total_goods_value: Decimal
    total_vat_input_claimed: Decimal
    total_vat_adjustment: Decimal
    net_vat_input_after_adjustment: Decimal
    declaration: str
    prepared_by: str
    prepared_date: datetime


@dataclass
class TransferItem:
    """Individual item in a transfer"""
    item_id: UUID
    item_name: str
    sku: str
    quantity_sent: Decimal
    quantity_received: Decimal
    unit_cost: Decimal
    total_value: Decimal
    batch_number: Optional[str] = None
    variance: Decimal = Decimal("0")
    variance_reason: Optional[str] = None


@dataclass
class InventoryTransfer:
    """Complete inventory transfer record"""
    id: UUID
    entity_id: UUID
    transfer_number: str
    transfer_type: TransferType
    status: TransferStatus
    
    # Locations
    source_location_id: UUID
    source_location_name: str
    source_state: Optional[NigerianState]
    destination_location_id: UUID
    destination_location_name: str
    destination_state: Optional[NigerianState]
    
    # Items
    items: List[TransferItem]
    total_value: Decimal
    
    # Interstate levy
    is_interstate: bool
    interstate_levy: Decimal
    
    # Dates
    initiated_at: datetime
    shipped_at: Optional[datetime]
    received_at: Optional[datetime]
    
    # Personnel
    initiated_by: UUID
    shipped_by: Optional[UUID]
    received_by: Optional[UUID]
    
    # Documentation
    waybill_number: Optional[str]
    driver_name: Optional[str]
    vehicle_number: Optional[str]
    notes: Optional[str]


class InventoryWriteOffService:
    """
    Inventory Write-off Service
    
    Handles expired/damaged goods write-off with proper
    VAT input adjustment documentation for FIRS compliance.
    """
    
    def __init__(self):
        self.vat_rate = VAT_RATE
    
    def generate_request_number(self) -> str:
        """Generate unique write-off request number."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique_id = uuid4().hex[:6].upper()
        return f"WO-{timestamp}-{unique_id}"
    
    def calculate_vat_adjustment(
        self,
        item_cost: Decimal,
        vat_input_claimed: Decimal,
        reason: WriteOffReason,
    ) -> Decimal:
        """
        Calculate VAT input adjustment required for write-off.
        
        VAT input must be reversed when goods are:
        - Not used for taxable supplies
        - Lost, stolen, or destroyed
        - Given away free
        """
        # Full reversal required for most write-off reasons
        full_reversal_reasons = [
            WriteOffReason.EXPIRED,
            WriteOffReason.DAMAGED,
            WriteOffReason.THEFT,
            WriteOffReason.SPOILAGE,
            WriteOffReason.SAMPLE_GIVEN,
        ]
        
        if reason in full_reversal_reasons:
            return vat_input_claimed
        
        # Partial or no reversal for some reasons
        if reason == WriteOffReason.RECALL:
            # If recalled by manufacturer and refunded, may not need reversal
            return Decimal("0")
        
        if reason == WriteOffReason.QUALITY_FAILURE:
            # If replaced by supplier, may not need reversal
            return Decimal("0")
        
        # Default to full reversal
        return vat_input_claimed
    
    async def create_write_off_request(
        self,
        db: AsyncSession,
        entity_id: UUID,
        reason: WriteOffReason,
        items: List[Dict[str, Any]],
        justification: str,
        requested_by: UUID,
        supporting_documents: List[str] = None,
    ) -> WriteOffRequest:
        """
        Create a new inventory write-off request.
        
        Args:
            db: Database session
            entity_id: Business entity ID
            reason: Reason for write-off
            items: List of items to write off
            justification: Detailed justification
            requested_by: User creating the request
            supporting_documents: List of document references
        """
        from app.models.inventory import InventoryItem
        
        write_off_items = []
        total_cost = Decimal("0")
        total_vat_adj = Decimal("0")
        
        for item_data in items:
            item_id = item_data["item_id"]
            quantity = Decimal(str(item_data["quantity"]))
            
            # Get inventory item details
            result = await db.execute(
                select(InventoryItem).where(InventoryItem.id == item_id)
            )
            inv_item = result.scalar_one_or_none()
            
            if not inv_item:
                raise ValueError(f"Inventory item {item_id} not found")
            
            unit_cost = Decimal(str(inv_item.unit_cost or 0))
            item_total = unit_cost * quantity
            
            # Calculate VAT that was claimed (assuming all purchases had VAT)
            vat_claimed = (item_total * self.vat_rate / (Decimal("1") + self.vat_rate)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            
            vat_adj = self.calculate_vat_adjustment(item_total, vat_claimed, reason)
            
            write_off_items.append(WriteOffItem(
                item_id=UUID(str(item_id)),
                item_name=inv_item.name,
                sku=inv_item.sku or "",
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=item_total,
                vat_input_claimed=vat_claimed,
                vat_adjustment_required=vat_adj,
                batch_number=item_data.get("batch_number"),
                expiry_date=item_data.get("expiry_date"),
                location_id=item_data.get("location_id"),
                location_name=item_data.get("location_name"),
            ))
            
            total_cost += item_total
            total_vat_adj += vat_adj
        
        request = WriteOffRequest(
            id=uuid4(),
            entity_id=entity_id,
            request_number=self.generate_request_number(),
            reason=reason,
            status=WriteOffStatus.PENDING_APPROVAL,
            items=write_off_items,
            total_cost=total_cost,
            total_vat_adjustment=total_vat_adj,
            justification=justification,
            supporting_documents=supporting_documents or [],
            requested_by=requested_by,
            requested_at=datetime.utcnow(),
        )
        
        logger.info(
            f"Write-off request {request.request_number} created: "
            f"{len(items)} items, N{total_cost:,.2f} value, N{total_vat_adj:,.2f} VAT adjustment"
        )
        
        return request
    
    def generate_vat_adjustment_document(
        self,
        request: WriteOffRequest,
        entity_tin: str,
        entity_name: str,
        preparer_name: str,
    ) -> VATInputAdjustment:
        """
        Generate VAT input adjustment documentation for FIRS.
        
        This document is required when reversing VAT input claims
        due to inventory write-offs.
        """
        items_detail = []
        for item in request.items:
            items_detail.append({
                "description": item.item_name,
                "sku": item.sku,
                "quantity": float(item.quantity),
                "unit_cost": float(item.unit_cost),
                "total_cost": float(item.total_cost),
                "vat_claimed": float(item.vat_input_claimed),
                "vat_adjustment": float(item.vat_adjustment_required),
                "batch_number": item.batch_number,
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
            })
        
        total_vat_claimed = sum(item.vat_input_claimed for item in request.items)
        
        declaration = (
            f"We hereby declare that the goods listed above with total value of "
            f"N{request.total_cost:,.2f} have been written off due to {request.reason.value}. "
            f"The VAT input credit of N{total_vat_claimed:,.2f} previously claimed is being "
            f"adjusted by N{request.total_vat_adjustment:,.2f} in accordance with Section 17 "
            f"of the Value Added Tax Act as amended."
        )
        
        return VATInputAdjustment(
            adjustment_id=f"VATADJ-{request.request_number}",
            entity_tin=entity_tin,
            entity_name=entity_name,
            period=date.today().replace(day=1),
            write_off_reference=request.request_number,
            reason=request.reason,
            items=items_detail,
            total_goods_value=request.total_cost,
            total_vat_input_claimed=total_vat_claimed,
            total_vat_adjustment=request.total_vat_adjustment,
            net_vat_input_after_adjustment=total_vat_claimed - request.total_vat_adjustment,
            declaration=declaration,
            prepared_by=preparer_name,
            prepared_date=datetime.utcnow(),
        )
    
    async def process_approved_write_off(
        self,
        db: AsyncSession,
        request: WriteOffRequest,
    ) -> Dict[str, Any]:
        """
        Process an approved write-off by updating inventory quantities.
        """
        from app.models.inventory import InventoryItem
        
        processed_items = []
        
        for item in request.items:
            # Update inventory quantity
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == item.item_id)
                .values(quantity=InventoryItem.quantity - item.quantity)
            )
            
            processed_items.append({
                "item_id": str(item.item_id),
                "item_name": item.item_name,
                "quantity_written_off": float(item.quantity),
                "value_written_off": float(item.total_cost),
            })
        
        await db.commit()
        
        return {
            "request_number": request.request_number,
            "status": "processed",
            "items_processed": len(processed_items),
            "total_value_written_off": float(request.total_cost),
            "vat_adjustment": float(request.total_vat_adjustment),
            "processed_at": datetime.utcnow().isoformat(),
            "items": processed_items,
        }
    
    def write_off_request_to_dict(self, request: WriteOffRequest) -> Dict[str, Any]:
        """Convert write-off request to dictionary for API response."""
        return {
            "id": str(request.id),
            "entity_id": str(request.entity_id),
            "request_number": request.request_number,
            "reason": request.reason.value,
            "status": request.status.value,
            "items": [
                {
                    "item_id": str(item.item_id),
                    "item_name": item.item_name,
                    "sku": item.sku,
                    "quantity": float(item.quantity),
                    "unit_cost": float(item.unit_cost),
                    "total_cost": float(item.total_cost),
                    "vat_input_claimed": float(item.vat_input_claimed),
                    "vat_adjustment_required": float(item.vat_adjustment_required),
                    "batch_number": item.batch_number,
                    "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                    "location": item.location_name,
                }
                for item in request.items
            ],
            "totals": {
                "total_cost": float(request.total_cost),
                "total_vat_adjustment": float(request.total_vat_adjustment),
            },
            "justification": request.justification,
            "supporting_documents": request.supporting_documents,
            "requested_by": str(request.requested_by),
            "requested_at": request.requested_at.isoformat(),
            "approved_by": str(request.approved_by) if request.approved_by else None,
            "approved_at": request.approved_at.isoformat() if request.approved_at else None,
        }


class InventoryTransferService:
    """
    Inventory Transfer Service
    
    Handles multi-location inventory transfers including
    interstate movement with 2026 levy calculations.
    """
    
    def __init__(self):
        self.interstate_levy_rate = INTERSTATE_LEVY_RATE
    
    def generate_transfer_number(self) -> str:
        """Generate unique transfer number."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
        unique_id = uuid4().hex[:4].upper()
        return f"TRF-{timestamp}-{unique_id}"
    
    def generate_waybill_number(self) -> str:
        """Generate waybill number for transfer."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique_id = uuid4().hex[:8].upper()
        return f"WB-{timestamp}-{unique_id}"
    
    def is_interstate_transfer(
        self,
        source_state: Optional[NigerianState],
        destination_state: Optional[NigerianState],
    ) -> bool:
        """Check if transfer crosses state boundaries."""
        if source_state is None or destination_state is None:
            return False
        return source_state != destination_state
    
    def calculate_interstate_levy(
        self,
        goods_value: Decimal,
        source_state: NigerianState,
        destination_state: NigerianState,
    ) -> Decimal:
        """
        Calculate interstate levy for goods movement.
        
        Note: In 2026, some states have bilateral agreements
        that exempt certain goods from interstate levies.
        """
        if source_state == destination_state:
            return Decimal("0")
        
        # Standard interstate levy
        levy = (goods_value * self.interstate_levy_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        logger.info(
            f"Interstate levy calculated: {source_state.value} -> {destination_state.value}, "
            f"Value: N{goods_value:,.2f}, Levy: N{levy:,.2f}"
        )
        
        return levy
    
    async def create_transfer(
        self,
        db: AsyncSession,
        entity_id: UUID,
        transfer_type: TransferType,
        source_location_id: UUID,
        source_location_name: str,
        source_state: Optional[NigerianState],
        destination_location_id: UUID,
        destination_location_name: str,
        destination_state: Optional[NigerianState],
        items: List[Dict[str, Any]],
        initiated_by: UUID,
        notes: Optional[str] = None,
    ) -> InventoryTransfer:
        """
        Create a new inventory transfer.
        """
        from app.models.inventory import InventoryItem
        
        transfer_items = []
        total_value = Decimal("0")
        
        for item_data in items:
            item_id = item_data["item_id"]
            quantity = Decimal(str(item_data["quantity"]))
            
            # Get inventory item details
            result = await db.execute(
                select(InventoryItem).where(InventoryItem.id == item_id)
            )
            inv_item = result.scalar_one_or_none()
            
            if not inv_item:
                raise ValueError(f"Inventory item {item_id} not found")
            
            # Check sufficient quantity
            if inv_item.quantity < quantity:
                raise ValueError(
                    f"Insufficient quantity for {inv_item.name}: "
                    f"requested {quantity}, available {inv_item.quantity}"
                )
            
            unit_cost = Decimal(str(inv_item.unit_cost or 0))
            item_value = unit_cost * quantity
            
            transfer_items.append(TransferItem(
                item_id=UUID(str(item_id)),
                item_name=inv_item.name,
                sku=inv_item.sku or "",
                quantity_sent=quantity,
                quantity_received=Decimal("0"),  # Updated on receipt
                unit_cost=unit_cost,
                total_value=item_value,
                batch_number=item_data.get("batch_number"),
            ))
            
            total_value += item_value
        
        # Check if interstate
        is_interstate = self.is_interstate_transfer(source_state, destination_state)
        
        # Calculate interstate levy
        interstate_levy = Decimal("0")
        if is_interstate and source_state and destination_state:
            interstate_levy = self.calculate_interstate_levy(
                total_value, source_state, destination_state
            )
        
        transfer = InventoryTransfer(
            id=uuid4(),
            entity_id=entity_id,
            transfer_number=self.generate_transfer_number(),
            transfer_type=transfer_type,
            status=TransferStatus.INITIATED,
            source_location_id=source_location_id,
            source_location_name=source_location_name,
            source_state=source_state,
            destination_location_id=destination_location_id,
            destination_location_name=destination_location_name,
            destination_state=destination_state,
            items=transfer_items,
            total_value=total_value,
            is_interstate=is_interstate,
            interstate_levy=interstate_levy,
            initiated_at=datetime.utcnow(),
            shipped_at=None,
            received_at=None,
            initiated_by=initiated_by,
            shipped_by=None,
            received_by=None,
            waybill_number=None,
            driver_name=None,
            vehicle_number=None,
            notes=notes,
        )
        
        logger.info(
            f"Transfer {transfer.transfer_number} created: "
            f"{source_location_name} -> {destination_location_name}, "
            f"{len(items)} items, N{total_value:,.2f}"
        )
        
        return transfer
    
    async def ship_transfer(
        self,
        db: AsyncSession,
        transfer: InventoryTransfer,
        shipped_by: UUID,
        driver_name: Optional[str] = None,
        vehicle_number: Optional[str] = None,
    ) -> InventoryTransfer:
        """
        Mark transfer as shipped and deduct from source inventory.
        """
        from app.models.inventory import InventoryItem
        
        # Generate waybill
        transfer.waybill_number = self.generate_waybill_number()
        transfer.status = TransferStatus.IN_TRANSIT
        transfer.shipped_at = datetime.utcnow()
        transfer.shipped_by = shipped_by
        transfer.driver_name = driver_name
        transfer.vehicle_number = vehicle_number
        
        # Deduct from source inventory
        for item in transfer.items:
            await db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == item.item_id)
                .values(quantity=InventoryItem.quantity - item.quantity_sent)
            )
        
        await db.commit()
        
        logger.info(f"Transfer {transfer.transfer_number} shipped, waybill: {transfer.waybill_number}")
        
        return transfer
    
    async def receive_transfer(
        self,
        db: AsyncSession,
        transfer: InventoryTransfer,
        received_by: UUID,
        received_quantities: List[Dict[str, Any]],
    ) -> InventoryTransfer:
        """
        Receive transfer at destination and update inventory.
        
        received_quantities: List of {"item_id": UUID, "quantity_received": Decimal, "variance_reason": str}
        """
        from app.models.inventory import InventoryItem
        
        has_discrepancy = False
        
        for received in received_quantities:
            item_id = received["item_id"]
            qty_received = Decimal(str(received["quantity_received"]))
            variance_reason = received.get("variance_reason")
            
            # Find matching transfer item
            for item in transfer.items:
                if str(item.item_id) == str(item_id):
                    item.quantity_received = qty_received
                    item.variance = item.quantity_sent - qty_received
                    item.variance_reason = variance_reason
                    
                    if item.variance != Decimal("0"):
                        has_discrepancy = True
                    
                    # Add to destination inventory
                    # Note: In a real system, you'd handle location-specific inventory
                    await db.execute(
                        update(InventoryItem)
                        .where(InventoryItem.id == item.item_id)
                        .values(quantity=InventoryItem.quantity + qty_received)
                    )
                    break
        
        transfer.status = TransferStatus.DISCREPANCY if has_discrepancy else TransferStatus.RECEIVED
        transfer.received_at = datetime.utcnow()
        transfer.received_by = received_by
        
        await db.commit()
        
        logger.info(
            f"Transfer {transfer.transfer_number} received: "
            f"status={transfer.status.value}, discrepancy={has_discrepancy}"
        )
        
        return transfer
    
    def generate_transfer_documentation(
        self,
        transfer: InventoryTransfer,
        entity_name: str,
        entity_tin: str,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive transfer documentation including waybill.
        """
        return {
            "document_type": "INVENTORY_TRANSFER_WAYBILL",
            "transfer_number": transfer.transfer_number,
            "waybill_number": transfer.waybill_number,
            "date": transfer.initiated_at.strftime("%Y-%m-%d"),
            
            "shipper": {
                "name": entity_name,
                "tin": entity_tin,
                "location": transfer.source_location_name,
                "state": transfer.source_state.value if transfer.source_state else None,
            },
            
            "consignee": {
                "name": entity_name,  # Same entity for internal transfers
                "location": transfer.destination_location_name,
                "state": transfer.destination_state.value if transfer.destination_state else None,
            },
            
            "transport": {
                "driver_name": transfer.driver_name,
                "vehicle_number": transfer.vehicle_number,
                "shipped_date": transfer.shipped_at.isoformat() if transfer.shipped_at else None,
            },
            
            "items": [
                {
                    "description": item.item_name,
                    "sku": item.sku,
                    "quantity": float(item.quantity_sent),
                    "unit_value": float(item.unit_cost),
                    "total_value": float(item.total_value),
                    "batch_number": item.batch_number,
                }
                for item in transfer.items
            ],
            
            "summary": {
                "total_items": len(transfer.items),
                "total_quantity": float(sum(i.quantity_sent for i in transfer.items)),
                "total_value": float(transfer.total_value),
                "currency": "NGN",
            },
            
            "interstate_levy": {
                "applicable": transfer.is_interstate,
                "amount": float(transfer.interstate_levy),
                "rate": float(self.interstate_levy_rate),
            } if transfer.is_interstate else None,
            
            "status": transfer.status.value,
            "notes": transfer.notes,
            
            "declaration": (
                f"I hereby certify that the goods described above are being transferred "
                f"from {transfer.source_location_name} to {transfer.destination_location_name} "
                f"for legitimate business purposes."
            ),
        }
    
    def transfer_to_dict(self, transfer: InventoryTransfer) -> Dict[str, Any]:
        """Convert transfer to dictionary for API response."""
        return {
            "id": str(transfer.id),
            "entity_id": str(transfer.entity_id),
            "transfer_number": transfer.transfer_number,
            "transfer_type": transfer.transfer_type.value,
            "status": transfer.status.value,
            "source": {
                "location_id": str(transfer.source_location_id),
                "location_name": transfer.source_location_name,
                "state": transfer.source_state.value if transfer.source_state else None,
            },
            "destination": {
                "location_id": str(transfer.destination_location_id),
                "location_name": transfer.destination_location_name,
                "state": transfer.destination_state.value if transfer.destination_state else None,
            },
            "items": [
                {
                    "item_id": str(item.item_id),
                    "item_name": item.item_name,
                    "sku": item.sku,
                    "quantity_sent": float(item.quantity_sent),
                    "quantity_received": float(item.quantity_received),
                    "unit_cost": float(item.unit_cost),
                    "total_value": float(item.total_value),
                    "batch_number": item.batch_number,
                    "variance": float(item.variance),
                    "variance_reason": item.variance_reason,
                }
                for item in transfer.items
            ],
            "total_value": float(transfer.total_value),
            "is_interstate": transfer.is_interstate,
            "interstate_levy": float(transfer.interstate_levy),
            "waybill_number": transfer.waybill_number,
            "transport": {
                "driver_name": transfer.driver_name,
                "vehicle_number": transfer.vehicle_number,
            },
            "dates": {
                "initiated_at": transfer.initiated_at.isoformat(),
                "shipped_at": transfer.shipped_at.isoformat() if transfer.shipped_at else None,
                "received_at": transfer.received_at.isoformat() if transfer.received_at else None,
            },
            "notes": transfer.notes,
        }


# Singleton instances
inventory_write_off_service = InventoryWriteOffService()
inventory_transfer_service = InventoryTransferService()
