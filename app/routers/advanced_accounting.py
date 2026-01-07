"""
Advanced Accounting API Router
Routes for 2026 Tax Reform advanced features

Endpoints:
- Tax Intelligence (ETR, Forecasting, Scenarios)
- 3-Way Matching (PO, GRN, Invoice)
- WHT Credit Vault
- Approval Workflows
- Audit Reports
- AI Transaction Labelling
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies import get_current_user, get_current_entity_id
from app.models.user import User

router = APIRouter(prefix="/api/v1/advanced", tags=["Advanced Accounting"])


# ============================================================================
# Schemas
# ============================================================================

class ETRRequest(BaseModel):
    """ETR calculation request"""
    revenue: Decimal
    expenses: Decimal
    capex: Optional[Decimal] = Decimal("0")
    prior_year_losses: Optional[Decimal] = Decimal("0")


class CashFlowForecastRequest(BaseModel):
    """Cash flow forecast request"""
    months_ahead: int = Field(default=12, ge=1, le=24)


class ScenarioRequest(BaseModel):
    """Scenario analysis request"""
    scenario_type: str = Field(..., description="Type: salary_increase, new_hires, revenue_growth")
    parameters: dict


class PurchaseOrderCreate(BaseModel):
    """Create PO request"""
    vendor_id: UUID
    po_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    items: List[dict]


class GRNCreate(BaseModel):
    """Create GRN request"""
    po_id: UUID
    received_date: Optional[date] = None
    received_by: Optional[str] = None
    delivery_note_number: Optional[str] = None
    notes: Optional[str] = None
    items: List[dict]


class MatchInvoiceRequest(BaseModel):
    """Match invoice request"""
    invoice_id: UUID
    po_id: UUID
    grn_id: Optional[UUID] = None


class WHTCreditNoteCreate(BaseModel):
    """Create WHT credit note request"""
    credit_note_number: str
    issue_date: date
    issuer_name: str
    issuer_tin: str
    issuer_address: Optional[str] = None
    gross_amount: Decimal
    wht_rate: Optional[Decimal] = None
    wht_amount: Optional[Decimal] = None
    wht_type: str
    tax_year: Optional[int] = None
    description: Optional[str] = None


class ApprovalWorkflowCreate(BaseModel):
    """Create approval workflow request"""
    workflow_type: str
    name: str
    approvers: List[dict]
    config: Optional[dict] = None


class ApprovalSubmitRequest(BaseModel):
    """Submit for approval request"""
    workflow_type: str
    resource_type: str
    resource_id: UUID
    amount: Optional[Decimal] = None
    context: Optional[dict] = None


class ApprovalDecisionRequest(BaseModel):
    """Approval decision request"""
    comments: Optional[str] = None


class TransactionPredictRequest(BaseModel):
    """AI transaction labelling request"""
    description: str
    amount: Decimal
    vendor_name: Optional[str] = None


# ============================================================================
# Tax Intelligence Endpoints
# ============================================================================

@router.post("/tax-intelligence/etr")
async def calculate_etr(
    request: ETRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Calculate Effective Tax Rate with breakdown"""
    from app.services.tax_intelligence import tax_intelligence_service
    
    result = tax_intelligence_service.calculate_etr(
        revenue=request.revenue,
        expenses=request.expenses,
        capex=request.capex,
        prior_year_losses=request.prior_year_losses
    )
    
    return result


@router.post("/tax-intelligence/cash-flow-forecast")
async def forecast_cash_flow(
    request: CashFlowForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Generate cash flow forecast"""
    from app.services.tax_intelligence import tax_intelligence_service
    
    result = await tax_intelligence_service.forecast_cash_flow(
        db=db,
        entity_id=entity_id,
        months_ahead=request.months_ahead
    )
    
    return result


@router.post("/tax-intelligence/scenario")
async def run_scenario(
    request: ScenarioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Run what-if scenario analysis"""
    from app.services.tax_intelligence import tax_intelligence_service
    
    result = await tax_intelligence_service.run_scenario(
        db=db,
        entity_id=entity_id,
        scenario_type=request.scenario_type,
        params=request.parameters
    )
    
    return result


@router.get("/tax-intelligence/sensitivity")
async def tax_sensitivity_analysis(
    current_revenue: Decimal = Query(...),
    current_expenses: Decimal = Query(...),
    capex_values: str = Query(default="0,500000,1000000,2000000"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyze tax impact of different CAPEX levels"""
    from app.services.tax_intelligence import tax_intelligence_service
    
    capex_list = [Decimal(v.strip()) for v in capex_values.split(",")]
    
    result = tax_intelligence_service.tax_sensitivity_analysis(
        current_revenue=current_revenue,
        current_expenses=current_expenses,
        capex_values=capex_list
    )
    
    return result


# ============================================================================
# 3-Way Matching Endpoints
# ============================================================================

@router.post("/purchase-orders")
async def create_purchase_order(
    request: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Create a new Purchase Order"""
    from app.services.three_way_matching import three_way_matching_service
    
    po = await three_way_matching_service.create_purchase_order(
        db=db,
        entity_id=entity_id,
        vendor_id=request.vendor_id,
        po_data=request.dict(exclude={"vendor_id", "items"}),
        items=request.items,
        created_by=current_user.id
    )
    
    return {
        "id": str(po.id),
        "po_number": po.po_number,
        "status": po.status,
        "total_amount": str(po.total_amount)
    }


@router.post("/purchase-orders/{po_id}/approve")
async def approve_purchase_order(
    po_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a Purchase Order"""
    from app.services.three_way_matching import three_way_matching_service
    
    po = await three_way_matching_service.approve_purchase_order(
        db=db,
        po_id=po_id,
        approved_by=current_user.id
    )
    
    return {"id": str(po.id), "status": po.status}


@router.post("/grn")
async def create_goods_received_note(
    request: GRNCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Create a Goods Received Note"""
    from app.services.three_way_matching import three_way_matching_service
    
    grn = await three_way_matching_service.create_goods_received_note(
        db=db,
        entity_id=entity_id,
        po_id=request.po_id,
        grn_data=request.dict(exclude={"po_id", "items"}),
        items=request.items,
        created_by=current_user.id
    )
    
    return {
        "id": str(grn.id),
        "grn_number": grn.grn_number,
        "status": grn.status
    }


@router.post("/matching/match")
async def match_invoice(
    request: MatchInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Perform 3-way matching for an invoice"""
    from app.services.three_way_matching import three_way_matching_service
    
    match = await three_way_matching_service.match_invoice_to_po_grn(
        db=db,
        entity_id=entity_id,
        invoice_id=request.invoice_id,
        po_id=request.po_id,
        grn_id=request.grn_id
    )
    
    return {
        "id": str(match.id),
        "status": match.status.value,
        "discrepancies": match.discrepancies
    }


@router.post("/matching/auto-match")
async def auto_match_invoices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Auto-match unmatched invoices to POs"""
    from app.services.three_way_matching import three_way_matching_service
    
    result = await three_way_matching_service.auto_match_invoices(
        db=db,
        entity_id=entity_id
    )
    
    return result


@router.get("/matching/summary")
async def get_matching_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get 3-way matching summary"""
    from app.services.three_way_matching import three_way_matching_service
    
    return await three_way_matching_service.get_matching_summary(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date
    )


# ============================================================================
# WHT Credit Vault Endpoints
# ============================================================================

@router.post("/wht-credits")
async def record_wht_credit(
    request: WHTCreditNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Record a new WHT credit note"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    cn = await wht_credit_vault_service.record_credit_note(
        db=db,
        entity_id=entity_id,
        credit_note_data=request.dict(),
        created_by=current_user.id
    )
    
    return {
        "id": str(cn.id),
        "credit_note_number": cn.credit_note_number,
        "wht_amount": str(cn.wht_amount),
        "status": cn.status.value
    }


@router.get("/wht-credits")
async def list_wht_credits(
    status: Optional[str] = None,
    tax_year: Optional[int] = None,
    issuer_tin: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """List WHT credit notes"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    return await wht_credit_vault_service.get_credit_notes(
        db=db,
        entity_id=entity_id,
        status=status,
        tax_year=tax_year,
        issuer_tin=issuer_tin
    )


@router.get("/wht-credits/summary")
async def get_wht_vault_summary(
    tax_year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get WHT credit vault summary"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    return await wht_credit_vault_service.get_vault_summary(
        db=db,
        entity_id=entity_id,
        tax_year=tax_year
    )


@router.post("/wht-credits/auto-match")
async def auto_match_wht_credits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Auto-match credit notes to receivables"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    return await wht_credit_vault_service.auto_match_to_receivables(
        db=db,
        entity_id=entity_id
    )


@router.post("/wht-credits/{credit_id}/apply")
async def apply_wht_credit(
    credit_id: UUID,
    tax_payment_reference: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Apply credit note to tax liability"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    cn = await wht_credit_vault_service.apply_credit_to_tax(
        db=db,
        credit_note_id=credit_id,
        tax_payment_reference=tax_payment_reference,
        applied_by=current_user.id
    )
    
    return {
        "id": str(cn.id),
        "status": cn.status.value,
        "applied_tax_reference": cn.applied_tax_reference
    }


@router.get("/wht-credits/tax-offset-report")
async def get_tax_offset_report(
    tax_year: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Generate WHT tax offset report"""
    from app.services.wht_credit_vault import wht_credit_vault_service
    
    return await wht_credit_vault_service.generate_tax_offset_report(
        db=db,
        entity_id=entity_id,
        tax_year=tax_year
    )


# ============================================================================
# Approval Workflow Endpoints
# ============================================================================

@router.post("/workflows")
async def create_workflow(
    request: ApprovalWorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Create an approval workflow"""
    from app.services.approval_workflow import approval_workflow_service
    
    workflow = await approval_workflow_service.create_workflow(
        db=db,
        entity_id=entity_id,
        workflow_type=request.workflow_type,
        name=request.name,
        approvers=request.approvers,
        config=request.config,
        created_by=current_user.id
    )
    
    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "workflow_type": workflow.workflow_type,
        "required_approvers": workflow.required_approvers
    }


@router.post("/approvals/submit")
async def submit_for_approval(
    request: ApprovalSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Submit a resource for approval"""
    from app.services.approval_workflow import approval_workflow_service
    
    approval_request = await approval_workflow_service.submit_for_approval(
        db=db,
        entity_id=entity_id,
        workflow_type=request.workflow_type,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        amount=request.amount,
        submitted_by=current_user.id,
        context=request.context
    )
    
    return {
        "id": str(approval_request.id),
        "status": approval_request.status.value,
        "expires_at": approval_request.expires_at.isoformat()
    }


@router.get("/approvals/pending")
async def get_pending_approvals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get pending approvals for current user"""
    from app.services.approval_workflow import approval_workflow_service
    
    return await approval_workflow_service.get_pending_approvals(
        db=db,
        entity_id=entity_id,
        approver_id=current_user.id
    )


@router.post("/approvals/{request_id}/approve")
async def approve_request(
    request_id: UUID,
    decision: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve an approval request"""
    from app.services.approval_workflow import approval_workflow_service
    
    approval_decision = await approval_workflow_service.approve(
        db=db,
        request_id=request_id,
        approver_id=current_user.id,
        comments=decision.comments
    )
    
    return {
        "decision": approval_decision.decision,
        "decided_at": approval_decision.decided_at.isoformat()
    }


@router.post("/approvals/{request_id}/reject")
async def reject_request(
    request_id: UUID,
    reason: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject an approval request"""
    from app.services.approval_workflow import approval_workflow_service
    
    decision = await approval_workflow_service.reject(
        db=db,
        request_id=request_id,
        approver_id=current_user.id,
        reason=reason
    )
    
    return {
        "decision": decision.decision,
        "decided_at": decision.decided_at.isoformat()
    }


@router.get("/approvals/history")
async def get_approval_history(
    start_date: date = Query(...),
    end_date: date = Query(...),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get approval history"""
    from app.services.approval_workflow import approval_workflow_service
    
    return await approval_workflow_service.get_approval_history(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        status=status
    )


# ============================================================================
# Audit Reports Endpoints
# ============================================================================

@router.get("/reports/audit-trail")
async def get_audit_trail(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get audit trail report"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_audit_trail(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        resource_type=resource_type
    )


@router.get("/reports/nrs-reconciliation")
async def get_nrs_reconciliation(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get NRS reconciliation report"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_nrs_reconciliation(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/reports/payroll-statutory")
async def get_payroll_statutory_schedule(
    year: int = Query(...),
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get payroll statutory schedule"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_payroll_statutory_schedule(
        db=db,
        entity_id=entity_id,
        year=year,
        month=month
    )


@router.get("/reports/aging")
async def get_aging_report(
    report_type: str = Query(default="receivable", pattern="^(receivable|payable)$"),
    as_of_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get AR/AP aging report"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_aging_report(
        db=db,
        entity_id=entity_id,
        report_type=report_type,
        as_of_date=as_of_date
    )


@router.get("/reports/budget-variance")
async def get_budget_variance(
    budget_id: UUID = Query(...),
    through_month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get budget vs actual variance analysis"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_budget_variance(
        db=db,
        entity_id=entity_id,
        budget_id=budget_id,
        through_month=through_month
    )


@router.get("/reports/dimensional")
async def get_dimensional_report(
    dimension_type: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    report_type: str = Query(default="profitability"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get dimensional/segment P&L report"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_dimensional_report(
        db=db,
        entity_id=entity_id,
        dimension_type=dimension_type,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type
    )


@router.get("/reports/input-vat")
async def get_input_vat_schedule(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get input VAT recovery schedule"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_input_vat_schedule(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/reports/wht-tracker")
async def get_wht_tracker(
    tax_year: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Get WHT credit note tracker"""
    from app.services.audit_reporting import audit_reporting_service
    
    return await audit_reporting_service.generate_wht_tracker(
        db=db,
        entity_id=entity_id,
        tax_year=tax_year
    )


# ============================================================================
# AI Transaction Labelling Endpoints
# ============================================================================

@router.post("/ai/predict-category")
async def predict_transaction_category(
    request: TransactionPredictRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Predict category and GL account for a transaction"""
    from app.services.ai_labelling import ai_labelling_service
    
    prediction = await ai_labelling_service.predict_category(
        description=request.description,
        amount=request.amount,
        vendor_name=request.vendor_name,
        entity_id=str(entity_id)
    )
    
    return prediction.__dict__


@router.post("/ai/train")
async def train_ml_model(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Train ML model on historical transactions"""
    from app.services.ai_labelling import ai_labelling_service
    
    success = await ai_labelling_service.train_from_historical_data(
        db=db,
        entity_id=entity_id
    )
    
    return {
        "success": success,
        "message": "Model trained successfully" if success else "Insufficient data for training"
    }


# ============================================================================
# Immutable Ledger Endpoints
# ============================================================================

@router.get("/ledger/verify")
async def verify_ledger_integrity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Verify hash chain integrity of ledger"""
    from app.services.immutable_ledger import immutable_ledger_service
    
    is_valid, message = await immutable_ledger_service.verify_chain_integrity(
        db=db,
        entity_id=entity_id
    )
    
    return {
        "is_valid": is_valid,
        "message": message
    }


@router.get("/ledger/audit-report")
async def generate_ledger_audit_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: UUID = Depends(get_current_entity_id)
):
    """Generate comprehensive ledger audit report"""
    from app.services.immutable_ledger import immutable_ledger_service
    
    return await immutable_ledger_service.generate_audit_report(
        db=db,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date
    )
